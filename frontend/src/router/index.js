import { createRouter, createWebHistory } from 'vue-router'
import HomeView from '../views/HomeView.vue'
import AssessmentView from '../views/AssessmentView.vue'
import FailureProbabilityView from '../views/FailureProbabilityView.vue'
import LoginView from '../views/LoginView.vue'
import RegisterView from '../views/RegisterView.vue'
import DeviceManagementView from '../views/DeviceManagementView.vue'
import DeviceAnalysisView from '../views/DeviceAnalysisView.vue'
import DeviceComparisonView from '../views/DeviceComparisonView.vue'
// 导入新的 SettingsView 组件
import SettingsView from '../views/SettingsView.vue'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      name: 'home',
      component: HomeView
    },
    {
      path: '/device-management',
      name: 'device-management',
      component: DeviceManagementView
    },
    // :id? 表示 id 参数是可选的
    {
      path: '/device-analysis/:id?',
      name: 'device-analysis',
      component: DeviceAnalysisView,
      props: true
    },
    {
      path: '/device-comparison',
      name: 'device-comparison',
      component: DeviceComparisonView
    },
    {
      path: '/assessment',
      name: 'assessment',
      component: AssessmentView
    },
    {
      path: '/failure-probability',
      name: 'failure-probability',
      component: FailureProbabilityView
    },
    {
      path: '/login',
      name: 'login',
      component: LoginView
    },
    {
      path: '/register',
      name: 'register',
      component: RegisterView
    },
    // 新增: 为 SettingsView 添加路由
    {
      path: '/settings',
      name: 'settings',
      component: SettingsView
    }
  ]
})

export default router

