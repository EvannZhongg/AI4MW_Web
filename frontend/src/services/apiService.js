import axios from 'axios';
import { useAuthStore } from '@/stores/auth';
import { ElMessage } from 'element-plus';

// baseURL 保持不变，它会根据您的 .env 文件自动切换
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'https://70418b8712f4.ngrok-free.app/api/';

// 1. 创建并配置一个 Axios 实例
const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 10000, // 请求超时时间
  headers: {
    'Content-Type': 'application/json',
    // 核心修复：添加此请求头以跳过 ngrok 的浏览器警告页面
    'ngrok-skip-browser-warning': 'true'
  },
});

// 2. 添加请求拦截器 (Request Interceptor)
apiClient.interceptors.request.use(
  (config) => {
    const authStore = useAuthStore();
    // 如果用户已登录，则在每个请求的头部自动附加 Token
    if (authStore.isAuthenticated) {
      config.headers['Authorization'] = `Bearer ${authStore.token}`;
    }
    return config;
  },
  (error) => {
    // 对请求错误做些什么
    return Promise.reject(error);
  }
);

// 3. 添加响应拦截器 (Response Interceptor)
apiClient.interceptors.response.use(
  (response) => {
    return response;
  },
  (error) => {
    if (error.response) {
        if (error.response.status === 401) {
            const authStore = useAuthStore();
            authStore.logout();
            ElMessage.error('您的登录已过期，请重新登录。');
        }
    }
    return Promise.reject(error);
  }
);


// 4. 定义并导出所有 API 调用函数 (保持不变)
export default {
    // --- 器件相关 ---
    getDevices(params) {
        return apiClient.get('devices/', { params });
    },
      getDeviceById(id) {
    return apiClient.get(`devices/${id}/`);
  },
    createDevice(data) {
        return apiClient.post('devices/', data);
    },
    updateDevice(id, data) {
        return apiClient.patch(`devices/${id}/`, data);
    },
    deleteDevice(id) {
        return apiClient.delete(`devices/${id}/`);
    },
    compareDevices(data) {
        return apiClient.post('compare/', data);
    },

    // --- 认证相关 ---
    login(username, password) {
        return apiClient.post('token/', { username, password });
    },
    register(username, password) {
        return apiClient.post('register/', { username, password });
    },
    getProfile() {
        return apiClient.get('profile/');
    },
    updateProfile(data) {
        return apiClient.patch('profile/', data);
    },

    // --- 评估与计算 ---
    assessDamage(data) {
        return apiClient.post('assess/damage/', data);
    },
    assessLink(data) {
        return apiClient.post('assess/link/', data);
    },
    calculateFailureProbability(data) {
        return apiClient.post('probability/calculate/', data);
    },

    // --- 失效概率数据集 ---
    getProbabilityDatasets() {
        return apiClient.get('probability-datasets/');
    },
    createProbabilityDataset(data) {
        return apiClient.post('probability-datasets/', data);
    }
};
