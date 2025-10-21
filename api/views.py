from rest_framework import viewsets, filters, generics, status, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from django_filters.rest_framework import DjangoFilterBackend
import math
from django.conf import settings

from .models import Device, ProbabilityDataSet, Profile
from .serializers import (
    UserSerializer, DeviceSerializer, DeviceListSerializer, ProbabilityDataSetSerializer, ProfileSerializer
)
from django.contrib.auth.models import User
from rest_framework_simplejwt.views import TokenObtainPairView


# --- 认证视图 ---
class UserCreateView(generics.CreateAPIView):
    # 允许任何人访问以进行注册
    permission_classes = [permissions.AllowAny]
    queryset = User.objects.all()
    serializer_class = UserSerializer


# --- 评估与计算视图 (需要登录) ---
class DamageAssessmentView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        try:
            pt_gw = float(request.data.get('pt_gw', 0))
            gt_db = float(request.data.get('gt_db', 0))
            gr_db = float(request.data.get('gr_db', 0))
            f_ghz = float(request.data.get('f_ghz', 0))
            d_km = float(request.data.get('d_km', 0))
            lna_gain_db = float(request.data.get('lna_gain_db', 0))

            if pt_gw <= 0 or f_ghz <= 0 or d_km <= 0:
                return Response({'error': '功率、频率和距离必须为正数'}, status=status.HTTP_400_BAD_REQUEST)

            pt_dbm = 10 * math.log10(pt_gw * 1e9 * 1000)
            f_mhz = f_ghz * 1000
            ls_db = 20 * math.log10(d_km) + 20 * math.log10(f_mhz) + 32.45
            pr_dbm = pt_dbm + gt_db + gr_db - ls_db + lna_gain_db
            risk_level = "低危"
            if pr_dbm > -20:
                risk_level = "高危"
            elif pr_dbm > -40:
                risk_level = "中危"
            limiter_loss_db = 1.5
            response_data = {
                'ls_db': round(ls_db, 3), 'pr_dbm': round(pr_dbm, 3), 'lna_gain_db': lna_gain_db,
                'limiter_loss_db': limiter_loss_db, 'risk_level': risk_level
            }
            return Response(response_data)
        except (ValueError, TypeError) as e:
            return Response({'error': f'输入数据格式错误: {e}'}, status=status.HTTP_400_BAD_REQUEST)


class LinkAssessmentView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        try:
            pt2_kw = float(request.data.get('pt2_kw', 0))
            gt2_db = float(request.data.get('gt2_db', 0))
            gr2_db = float(request.data.get('gr2_db', 0))
            f2_ghz = float(request.data.get('f2_ghz', 0))
            d2_km = float(request.data.get('d2_km', 0))
            receiver_sensitivity_dbm = float(request.data.get('receiver_sensitivity_dbm', 0))

            if pt2_kw <= 0 or f2_ghz <= 0 or d2_km <= 0:
                return Response({'error': '功率、频率和距离必须为正数'}, status=status.HTTP_400_BAD_REQUEST)
            pt2_dbm = 10 * math.log10(pt2_kw * 1000 * 1000)
            f2_mhz = f2_ghz * 1000
            lp_db = 20 * math.log10(d2_km) + 20 * math.log10(f2_mhz) + 32.45
            pr2_dbm = pt2_dbm + gt2_db + gr2_db - lp_db
            link_margin_db = pr2_dbm - receiver_sensitivity_dbm
            link_status = "正常" if link_margin_db > 0 else "中断"
            response_data = {
                'lp_db': round(lp_db, 3), 'link_margin_db': round(link_margin_db, 3), 'link_status': link_status
            }
            return Response(response_data)
        except (ValueError, TypeError) as e:
            return Response({'error': f'输入数据格式错误: {e}'}, status=status.HTTP_400_BAD_REQUEST)


class SystemFailureProbabilityView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        components = request.data.get('components', [])
        if not components:
            return Response({'error': '缺少组件数据'}, status=status.HTTP_400_BAD_REQUEST)
        system_failure_probability = 0
        total_weight = sum(c.get('weight', 0) for c in components)
        if total_weight == 0:
            return Response({'system_failure_probability': 0})
        for component in components:
            weight = component.get('weight', 0)
            probability = component.get('probability', 0)
            system_failure_probability += (weight / total_weight) * probability
        return Response({'system_failure_probability': round(system_failure_probability, 6)})


# --- 器件与数据视图 (部分公开，部分需要登录) ---
class DeviceViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    queryset = Device.objects.all().order_by('-created_at')
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['device_type']
    search_fields = ['name', 'device_number', 'tech_description']

    def get_queryset(self):
        queryset = super().get_queryset()
        experiment_type = self.request.query_params.get('experiment_type')
        if experiment_type:
            queryset = queryset.filter(device_specific_data__contains=[{'experiment_type': experiment_type}])
        return queryset

    def get_serializer_class(self):
        if self.action == 'list':
            return DeviceListSerializer
        return DeviceSerializer


class DeviceComparisonView(APIView):
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    def post(self, request, *args, **kwargs):
        data = request.data
        device_type = data.get('device_type')
        experiment_type = data.get('experiment_type')

        if not device_type or not experiment_type:
            return Response({'error': '必须提供器件类型和实验类型'}, status=status.HTTP_400_BAD_REQUEST)

        # 1. 基础数据库查询
        base_queryset = Device.objects.filter(
            device_type=device_type,
            device_specific_data__contains=[{'experiment_type': experiment_type}]
        )

        # 2. 检查是否存在有效的固定参数
        # (过滤掉那些用户添加了但没填参数名的行)
        fixed_params = [p for p in data.get('fixed_params', []) if p.get('name')]

        filtered_devices_data = []
        all_available_params = set()

        for device in base_queryset:
            matching_table = None
            for table in device.device_specific_data:
                if table.get('experiment_type') == experiment_type:
                    matching_table = table
                    break

            if not matching_table:
                continue

            headers = matching_table.get('grid_data', [[]])[0]
            for header in headers:
                all_available_params.add(header)

            # 3. 优化点：如果没有固定参数，则直接将器件加入结果，跳过后续复杂计算
            if not fixed_params:
                filtered_devices_data.append({
                    'id': device.id,
                    'name': device.name,
                    'device_number': device.device_number,
                    'device_specific_data': [matching_table]
                })
                continue  # 继续处理下一个器件

            # --- 仅在有固定参数时，才执行耗时的行扫描筛选 ---
            rows = matching_table.get('grid_data', [[]])[1:]
            device_is_valid = True
            for param_filter in fixed_params:
                name = param_filter.get('name')
                min_val_str = param_filter.get('min')
                max_val_str = param_filter.get('max')

                try:
                    param_index = headers.index(name)
                except ValueError:
                    device_is_valid = False
                    break  # 如果器件连这个参数列都没有，则直接判定为不符

                min_val = float(min_val_str) if min_val_str and min_val_str.strip() else -float('inf')
                max_val = float(max_val_str) if max_val_str and max_val_str.strip() else float('inf')

                # 只要表格中有一行数据落在该参数的范围内，就算通过
                satisfies_current_filter = False
                for row in rows:
                    try:
                        cell_val = float(row[param_index])
                        if min_val <= cell_val <= max_val:
                            satisfies_current_filter = True
                            break
                    except (ValueError, TypeError, IndexError):
                        continue

                if not satisfies_current_filter:
                    device_is_valid = False
                    break

            if device_is_valid:
                filtered_devices_data.append({
                    'id': device.id,
                    'name': device.name,
                    'device_number': device.device_number,
                    'device_specific_data': [matching_table]
                })

        response_payload = {
            'filtered_devices': filtered_devices_data,
            'available_params': sorted(list(all_available_params))
        }
        return Response(response_payload)

class ProbabilityDataSetViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    queryset = ProbabilityDataSet.objects.all().order_by('-created_at')
    serializer_class = ProbabilityDataSetSerializer


# --- 用户Profile视图 (需要登录) ---
class ProfileView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, *args, **kwargs):
        profile, created = Profile.objects.get_or_create(user=request.user)

        default_config = {
            'llm_api_url': getattr(settings, 'DEFAULT_LLM_API_URL', ''),
            'llm_api_key': getattr(settings, 'DEFAULT_LLM_API_KEY', ''),
            'llm_model_name': getattr(settings, 'DEFAULT_LLM_MODEL_NAME', ''),
        }

        response_data = {
            'user_configs': profile.user_configs,
            'active_config_id': profile.active_config_id,
            'default_config': default_config,
        }
        return Response(response_data)

    def patch(self, request, *args, **kwargs):
        profile, created = Profile.objects.get_or_create(user=request.user)

        serializer = ProfileSerializer(profile, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()

            default_config = {
                'llm_api_url': getattr(settings, 'DEFAULT_LLM_API_URL', ''),
                'llm_api_key': getattr(settings, 'DEFAULT_LLM_API_KEY', ''),
                'llm_model_name': getattr(settings, 'DEFAULT_LLM_MODEL_NAME', ''),
            }
            response_data = serializer.data
            response_data['default_config'] = default_config
            return Response(response_data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

