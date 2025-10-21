from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    UserCreateView,
    DeviceViewSet,
    DamageAssessmentView,
    LinkAssessmentView,
    SystemFailureProbabilityView,
    ProbabilityDataSetViewSet,
    DeviceComparisonView,
    ProfileView  # 导入 ProfileView
)
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)

router = DefaultRouter()
router.register(r'devices', DeviceViewSet, basename='device')
router.register(r'probability-datasets', ProbabilityDataSetViewSet, basename='probabilitydataset')

urlpatterns = [
    # 1. 包含 router 生成的 URL
    path('', include(router.urls)),

    # 2. 用户认证
    path('register/', UserCreateView.as_view(), name='user_register'),
    path('token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),

    # 3. 评估模块
    path('assess/damage/', DamageAssessmentView.as_view(), name='assess_damage'),
    path('assess/link/', LinkAssessmentView.as_view(), name='assess_link'),

    # 4. 失效概率模块
    path('probability/calculate/', SystemFailureProbabilityView.as_view(), name='calculate_probability'),

    # 5. 器件对比
    path('compare/', DeviceComparisonView.as_view(), name='device_comparison'),

    # 6. 新增：用户Profile配置
    path('profile/', ProfileView.as_view(), name='user_profile'),
]
