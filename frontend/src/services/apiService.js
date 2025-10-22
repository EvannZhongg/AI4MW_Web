import axios from 'axios';
import { useAuthStore } from '@/stores/auth';
import { ElMessage } from 'element-plus';

// baseURL 保持不变，它会根据您的 .env 文件自动切换
// 如果后端部署在 ngrok 或其他地方，请确保这里是正确的 API 基础 URL
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000/api/'; // 确保末尾有斜杠 '/'

// 1. 创建并配置一个 Axios 实例
const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 10000, // 请求超时时间
  headers: {
    'Content-Type': 'application/json',
    // 如果您仍然通过 ngrok 访问，保留此行
    'ngrok-skip-browser-warning': 'true'
  },
});

// 2. 添加请求拦截器 (Request Interceptor) - 无需修改
apiClient.interceptors.request.use(
  (config) => {
    const authStore = useAuthStore();
    // 如果用户已登录，则在每个请求的头部自动附加 Token
    if (authStore.isAuthenticated) {
      config.headers['Authorization'] = `Bearer ${authStore.token}`;
      // *** 重要：如果是 FormData 请求，让浏览器自动设置 Content-Type ***
      if (config.data instanceof FormData) {
        // 删除我们之前默认设置的 'application/json'，否则上传会失败
        delete config.headers['Content-Type'];
      }
    }
    return config;
  },
  (error) => {
    // 对请求错误做些什么
    return Promise.reject(error);
  }
);

// 3. 添加响应拦截器 (Response Interceptor) - 无需修改
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


// 4. 定义并导出所有 API 调用函数 (保留原有，新增 Experiment 相关)
export default {
    // --- 器件相关 (Device) ---
    getDevices(params) {
        return apiClient.get('devices/', { params });
    },
    getDeviceById(id) {
        // 这个接口现在会返回嵌套的 experiments 数据
        return apiClient.get(`devices/${id}/`);
    },
    createDevice(data) {
        // 创建器件基础信息
        return apiClient.post('devices/', data);
    },
    updateDevice(id, data) {
        // 更新器件基础信息
        return apiClient.patch(`devices/${id}/`, data);
    },
    deleteDevice(id) {
        // 删除器件及其所有关联数据 (experiments, parameters, datapoints)
        return apiClient.delete(`devices/${id}/`);
    },
    compareDevices(data) {
        // 器件对比接口 (后端逻辑已更新)
        return apiClient.post('compare/', data);
    },

    // --- 实验相关 (Experiment) ---
    getExperiment(id) {
        // 获取单个实验的详细信息（包括 parameters 和 datapoints）
        return apiClient.get(`experiments/${id}/`);
    },
    createExperiment(data) {
        // 创建一个新的实验记录 (基础信息)
        // 'data' 应包含 { device: deviceId, name: '...', experiment_type: '...' }
        return apiClient.post('experiments/', data);
    },
    updateExperiment(id, data) {
        // 更新实验的基础信息 (name, experiment_type)
        return apiClient.patch(`experiments/${id}/`, data);
    },
    deleteExperiment(id) {
        // 删除一个实验及其关联的 parameters 和 datapoints
        return apiClient.delete(`experiments/${id}/`);
    },
    updateExperimentGridData(id, data) {
        // 更新实验的表格数据 (覆盖式)
        // 'data' 应为 { parameters: [...], datapoints: [...] }
        return apiClient.patch(`experiments/${id}/grid_data/`, data);
    },
    updateExperimentCsvMetadata(id, data) {
        // 更新实验关联的 CSV 元数据
        // 'data' 应为 { csv_files_metadata: [...] }
        return apiClient.patch(`experiments/${id}/csv_metadata/`, data);
    },
    // --- !!! 新增：上传 CSV 文件 !!! ---
    uploadExperimentCsv(experimentId, formData) {
        // 发送 POST 请求到 upload_csv action
        // axios 会自动处理 FormData 的 Content-Type
        return apiClient.post(`experiments/${experimentId}/upload_csv/`, formData);
        // 注意：拦截器会自动处理 FormData 的 Content-Type
    },
    // --- 获取 CSV 文件内容 ---
    getExperimentCsvData(experimentId, metadataId) { // 参数名改为 metadataId 保持一致
        // 假设后端端点是 /api/experiments/{exp_id}/csv_data/{metadata_id}/
        // 并且后端返回的是 CSV 文件的原始文本内容
        return apiClient.get(`experiments/${experimentId}/csv_data/${metadataId}/`);
    },
    // --- (可选) 通过 Device 端点添加 Experiment ---
    addExperimentToDevice(deviceId, data) {
        // 'data' 应包含 { name: '...', experiment_type: '...' }
        // 注意：如果使用此方法创建，后续仍需调用 updateExperimentGridData/CsvMetadata 填充数据
        return apiClient.post(`devices/${deviceId}/add_experiment/`, data);
    },

    // --- 认证相关 (保持不变) ---
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

    // --- 评估与计算 (保持不变) ---
    assessDamage(data) {
        return apiClient.post('assess/damage/', data);
    },
    assessLink(data) {
        return apiClient.post('assess/link/', data);
    },
    calculateFailureProbability(data) {
        return apiClient.post('probability/calculate/', data);
    },

    // --- 失效概率数据集 (保持不变) ---
    getProbabilityDatasets() {
        return apiClient.get('probability-datasets/');
    },
    createProbabilityDataset(data) {
        return apiClient.post('probability-datasets/', data);
    }
};
