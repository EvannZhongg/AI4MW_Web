from rest_framework import serializers
from .models import Device, ProbabilityDataSet, Profile
from django.contrib.auth.models import User


# UserSerializer 保持不变
class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['username', 'password']
        extra_kwargs = {'password': {'write_only': True}}

    def create(self, validated_data):
        user = User.objects.create_user(
            username=validated_data['username'],
            password=validated_data['password']
        )
        return user


# 新增：用于设备列表的序列化器
class DeviceListSerializer(serializers.ModelSerializer):
    """
    专用于设备列表视图。
    动态生成一个 test_types_display 字段用于展示。
    """
    test_types_display = serializers.SerializerMethodField()

    class Meta:
        model = Device
        # 移除了 test_type 和大数据字段，添加了 test_types_display
        fields = [
            'id', 'name', 'device_type', 'substrate', 'device_number',
            'tech_description', 'created_at', 'test_types_display'
        ]

    def get_test_types_display(self, obj):
        """
        从 device_specific_data 中提取所有唯一的 experiment_type 并用 '/' 连接。
        """
        if not isinstance(obj.device_specific_data, list):
            return ""

        types = set()
        for table in obj.device_specific_data:
            if isinstance(table, dict) and table.get('experiment_type'):
                types.add(table['experiment_type'])

        return "/".join(sorted(list(types)))


# 更新：用于设备详情、创建和更新的序列化器
class DeviceSerializer(serializers.ModelSerializer):
    """
    用于设备的创建、检索、更新、删除操作。
    """

    class Meta:
        model = Device
        # 移除了 test_type
        fields = [
            'id', 'name', 'device_type', 'substrate', 'device_number',
            'tech_description', 'photo_data', 'created_at', 'device_specific_data'
        ]


# ProbabilityDataSetSerializer 保持不变
class ProbabilityDataSetSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProbabilityDataSet
        fields = '__all__'

class ProfileSerializer(serializers.ModelSerializer):
    """
    用于安全地更新用户的API配置。
    """
    class Meta:
        model = Profile
        # 修复：只允许用户通过API修改这两个字段，
        # 这两个字段现在直接对应 Profile 模型上的字段。
        fields = ['user_configs', 'active_config_id']
