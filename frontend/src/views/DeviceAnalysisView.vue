<script setup>
import { ref, reactive, onMounted, watch, computed } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { ElMessage, ElMessageBox } from 'element-plus';
import Papa from 'papaparse';
import { use } from 'echarts/core';
import { CanvasRenderer } from 'echarts/renderers';
import { LineChart } from 'echarts/charts';
import { TitleComponent, TooltipComponent, GridComponent, LegendComponent, DataZoomComponent } from 'echarts/components';
import VChart from 'vue-echarts';
import { useAuthStore } from '@/stores/auth';
import apiService from '@/services/apiService'; // 1. 导入新的 apiService

use([CanvasRenderer, LineChart, TitleComponent, TooltipComponent, GridComponent, LegendComponent, DataZoomComponent]);

const props = defineProps({ id: { type: String, required: false } });
const router = useRouter();
const authStore = useAuthStore();

// --- 核心状态 ---
const allDevices = ref([]);
const selectedDeviceId = ref(null);
const selectedDevice = ref(null);
const loading = ref(false);
const selectLoading = ref(false);

// --- 搜索与筛选状态 ---
const searchQuery = ref('');
const filterDeviceType = ref('');

// --- 分析模式状态 ---
const customTables = ref([])
const editorDialog = reactive({
  visible: false, isNew: false, title: '',
  data: { id: null, name: '', experiment_type: '', grid_data: [[]], csv_files: [] }
})
const csvMetadataDialog = reactive({
  visible: false, filename: '', parsedData: [], columns: []
})
const photoState = reactive({
    scale: 1, translateX: 0, translateY: 0, isDragging: false, lastX: 0, lastY: 0
})
const photoTransform = computed(() => `scale(${photoState.scale}) translate(${photoState.translateX}px, ${photoState.translateY}px)`);

// --- 图表状态 ---
const gridVisualization = reactive({ activeTableId: null, xAxisKey: '', yAxisKey: '' });
const waveform = reactive({ activeTableId: null, activeCsvId: null, availableCsvs: [], xAxisKey: '', yAxisKey: '' });

// --- 计算属性 ---
const filteredDevicesForSelect = computed(() => {
    return allDevices.value.filter(device => {
        const typeMatch = !filterDeviceType.value || device.device_type === filterDeviceType.value;
        const searchMatch = !searchQuery.value ||
            device.name.toLowerCase().includes(searchQuery.value.toLowerCase()) ||
            device.device_number.toLowerCase().includes(searchQuery.value.toLowerCase()) ||
            (device.tech_description && device.tech_description.toLowerCase().includes(searchQuery.value.toLowerCase()));
        return typeMatch && searchMatch;
    });
});

const gridChartAxisOptions = computed(() => {
    if (!gridVisualization.activeTableId) return [];
    const table = customTables.value.find(t => t.id === gridVisualization.activeTableId);
    return table?.grid_data?.[0] || [];
});

const gridChartOptions = computed(() => {
    if (!selectedDevice.value || !gridVisualization.activeTableId || !gridVisualization.xAxisKey || !gridVisualization.yAxisKey) {
        return { title: { text: '请选择数据表并配置X/Y轴', left: 'center', top: 'center' } };
    }
    const table = customTables.value.find(t => t.id === gridVisualization.activeTableId);
    if (!table || table.grid_data.length < 2) return { title: { text: '无可用数据', left: 'center', top: 'center' } };
    const headers = table.grid_data[0];
    const dataRows = table.grid_data.slice(1);
    const xIndex = headers.indexOf(gridVisualization.xAxisKey);
    const yIndex = headers.indexOf(gridVisualization.yAxisKey);
    if (xIndex === -1 || yIndex === -1) return { title: { text: '轴配置错误', left: 'center', top: 'center' } };
    const validData = dataRows
        .map(row => ({ x: row[xIndex], y: parseFloat(row[yIndex]) }))
        .filter(item => item.x != null && !isNaN(item.y));
    return {
        title: { text: `${table.name} - 数据可视化`, left: 'center' },
        tooltip: { trigger: 'axis' },
        xAxis: { type: 'category', name: headers[xIndex], data: validData.map(item => item.x) },
        yAxis: { type: 'value', name: headers[yIndex] },
        dataZoom: [{ type: 'inside' }, { type: 'slider' }],
        series: [{ data: validData.map(item => item.y), type: 'line', smooth: true }],
    };
});

const csvAxisOptions = computed(() => {
    if (!waveform.activeCsvId) return [];
    const table = customTables.value.find(t => t.id === waveform.activeTableId);
    const csv = table?.csv_files.find(f => f.id === waveform.activeCsvId);
    return csv ? csv.columns : [];
});

const waveformChartOptions = computed(() => {
    if (!waveform.activeCsvId) return { title: { text: '请选择一个包含CSV的数据表', left: 'center', top: 'center' } };
    const table = customTables.value.find(t => t.id === waveform.activeTableId);
    if (!table) return { title: { text: '数据表未找到', left: 'center', top: 'center' } };
    const csv = table.csv_files.find(f => f.id === waveform.activeCsvId);
    if (!csv || !csv.data || !waveform.xAxisKey || !waveform.yAxisKey) return { title: { text: '请选择X轴和Y轴', left: 'center', top: 'center' } };
    const xIndex = csv.columns.findIndex(c => c.key === waveform.xAxisKey);
    const yIndex = csv.columns.findIndex(c => c.key === waveform.yAxisKey);
    if (xIndex === -1 || yIndex === -1) return { title: { text: '轴配置错误', left: 'center', top: 'center' } };
    return {
      title: { text: `${table.name} - ${csv.filename}`, left: 'center' },
      tooltip: { trigger: 'axis' },
      xAxis: { type: 'value', name: `${csv.columns[xIndex].name} (${csv.columns[xIndex].unit})`, scale: true },
      yAxis: { type: 'value', name: `${csv.columns[yIndex].name} (${csv.columns[yIndex].unit})`, scale: true },
      dataZoom: [{ type: 'inside', filterMode: 'weakFilter' }, { type: 'slider', filterMode: 'weakFilter' }],
      series: [{ data: csv.data.map(row => [row[xIndex], row[yIndex]]), type: 'line', showSymbol: false }],
    }
});

// --- 业务逻辑 (已重构) ---
const fetchAllDevices = async () => {
  selectLoading.value = true;
  try {
    // 2. 使用 apiService
    const response = await apiService.getDevices();
    allDevices.value = response.data.results || response.data;
  } catch(error) {
    if (error.response?.status !== 401) {
        ElMessage.error('获取器件列表失败！');
    }
    console.error(error);
  } finally {
    selectLoading.value = false;
  }
};

const loadAnalysisData = async (deviceId) => {
  if (!deviceId) { selectedDevice.value = null; customTables.value = []; return; }
  loading.value = true;
  try {
    // 3. 使用 apiService
    const response = await apiService.getDeviceById(deviceId);
    selectedDevice.value = response.data;
    customTables.value = Array.isArray(response.data.device_specific_data) ? JSON.parse(JSON.stringify(response.data.device_specific_data)) : [];
    photoState.scale = 1; photoState.translateX = 0; photoState.translateY = 0;
    waveform.activeTableId = null; waveform.activeCsvId = null; waveform.availableCsvs = [];
    gridVisualization.activeTableId = null; gridVisualization.xAxisKey = ''; gridVisualization.yAxisKey = '';
  } catch(error) {
    if (error.response?.status !== 401) {
        ElMessage.error(`加载器件ID: ${deviceId} 的数据失败！`);
    }
    selectedDevice.value = null;
    router.replace({ name: 'device-analysis' });
    console.error(error);
  } finally {
    loading.value = false;
  }
};

onMounted(fetchAllDevices);

watch(() => props.id, (newId) => {
  const numId = newId ? parseInt(newId, 10) : null;
  if (selectedDeviceId.value !== numId) { selectedDeviceId.value = numId; }
  loadAnalysisData(numId);
}, { immediate: true });

const handleSelectChange = (newId) => {
  if (String(props.id || '') !== String(newId)) {
    router.push({ name: 'device-analysis', params: { id: newId } });
  }
};

// --- 事件处理 ---
const onPhotoWheel = (e) => { photoState.scale = Math.max(0.5, Math.min(5, photoState.scale + (e.deltaY > 0 ? -0.1 : 0.1))); };
const onPhotoMouseDown = (e) => { photoState.isDragging = true; photoState.lastX = e.clientX; photoState.lastY = e.clientY; };
const onPhotoMouseMove = (e) => {
    if (!photoState.isDragging) return;
    const dx = e.clientX - photoState.lastX;
    const dy = e.clientY - photoState.lastY;
    photoState.translateX += dx / photoState.scale;
    photoState.translateY += dy / photoState.scale;
    photoState.lastX = e.clientX;
    photoState.lastY = e.clientY;
};
const onPhotoMouseUp = () => { photoState.isDragging = false; };

const handleTableSelect = (activeName) => {
    const tableId = activeName;
    gridVisualization.activeTableId = tableId;
    waveform.activeTableId = tableId;
    if (!tableId) {
        waveform.activeCsvId = null; waveform.availableCsvs = [];
        gridVisualization.xAxisKey = ''; gridVisualization.yAxisKey = '';
        return;
    }
    const table = customTables.value.find(t => t.id === tableId);
    if (table) {
        if (table.grid_data && table.grid_data.length > 1 && table.grid_data[0].length > 0) {
            const headers = table.grid_data[0];
            gridVisualization.xAxisKey = headers[0] || '';
            gridVisualization.yAxisKey = headers.length > 1 ? headers[1] : headers[0];
        } else {
            gridVisualization.xAxisKey = ''; gridVisualization.yAxisKey = '';
        }
        waveform.availableCsvs = table.csv_files || [];
        if (waveform.availableCsvs.length > 0) { waveform.activeCsvId = waveform.availableCsvs[0].id; }
        else { waveform.activeCsvId = null; }
    }
}

watch(() => waveform.activeCsvId, (newCsvId) => {
    if (!newCsvId) { waveform.xAxisKey = ''; waveform.yAxisKey = ''; return; };
    const table = customTables.value.find(t => t.id === waveform.activeTableId);
    const csv = table?.csv_files.find(f => f.id === newCsvId);
    if (csv && csv.columns.length > 0) {
        waveform.xAxisKey = csv.columns[0].key;
        waveform.yAxisKey = csv.columns.length > 1 ? csv.columns[1].key : csv.columns[0].key;
    }
});

const openAddTableDialog = () => {
  editorDialog.isNew = true;
  editorDialog.title = '添加新实验数据表';
  editorDialog.data = { id: Date.now(), name: '新的实验数据', experiment_type: '', grid_data: [['参数'], ['']], csv_files: [] };
  editorDialog.visible = true;
};
const openEditTableDialog = (table) => {
  editorDialog.isNew = false;
  editorDialog.title = `编辑: ${table.name}`;
  editorDialog.data = JSON.parse(JSON.stringify(table));
  editorDialog.visible = true;
};
const triggerCsvUpload = () => { document.getElementById('csv-uploader').click(); };
const handleCsvFileChange = (event) => {
  const file = event.target.files[0];
  if (!file) return;
  Papa.parse(file, {
    header: false, skipEmptyLines: true, dynamicTyping: true,
    complete: (results) => {
      if (results.errors.length > 0) { ElMessage.error('CSV文件解析失败！'); console.error(results.errors); return; }
      csvMetadataDialog.parsedData = results.data;
      csvMetadataDialog.filename = file.name;
      csvMetadataDialog.columns = results.data[0].map((_, index) => ({ key: `col_${index}`, name: `列 ${index + 1}`, unit: '' }));
      csvMetadataDialog.visible = true;
    }
  });
  event.target.value = '';
};
const confirmCsvMetadata = () => {
  const newCsv = { id: Date.now(), filename: csvMetadataDialog.filename, columns: csvMetadataDialog.columns, data: csvMetadataDialog.parsedData };
  editorDialog.data.csv_files.push(newCsv);
  csvMetadataDialog.visible = false;
};
const deleteCsvInDialog = (csvId) => {
  const index = editorDialog.data.csv_files.findIndex(f => f.id === csvId);
  if (index !== -1) editorDialog.data.csv_files.splice(index, 1);
};

const persistCustomTables = async () => {
    if (!selectedDevice.value) return;
    try {
        const payload = { device_specific_data: JSON.parse(JSON.stringify(customTables.value)) };
        // 4. 使用 apiService (不再需要手动添加 headers)
        await apiService.updateDevice(selectedDevice.value.id, payload);
        ElMessage.success('更改已自动保存！');
    } catch(error) {
        if (error.response?.status !== 401) {
            ElMessage.error('自动保存失败！');
        }
        console.error(error);
    }
};

const handleSaveChangesInDialog = async () => {
  if (!editorDialog.data.name) { ElMessage.warning('表格名称不能为空！'); return; }
  const plainDataObject = JSON.parse(JSON.stringify(editorDialog.data));
  if (editorDialog.isNew) {
    customTables.value.push(plainDataObject);
  } else {
    const index = customTables.value.findIndex(t => t.id === plainDataObject.id);
    if (index !== -1) { customTables.value.splice(index, 1, plainDataObject); }
  }
  editorDialog.visible = false;
  await persistCustomTables();
};
const deleteCustomTable = (tableId) => {
    ElMessageBox.confirm('确定要删除这个数据表吗？此操作将立即生效。', '警告', { type: 'warning' })
        .then(async () => {
            const index = customTables.value.findIndex(t => t.id === tableId);
            if (index !== -1) {
                customTables.value.splice(index, 1);
                await persistCustomTables();
            }
        })
        .catch(() => {});
};
const addColumnInDialog = () => {
    const table = editorDialog.data.grid_data;
    if (table.length === 0) table.push([]);
    const newHeaderName = `新参数${table[0].length + 1}`;
    table.forEach(row => row.push(''));
    table[0][table[0].length - 1] = newHeaderName;
};
const deleteColumnInDialog = (index) => { editorDialog.data.grid_data.forEach(row => row.splice(index, 1)); };
const addRowInDialog = () => {
    const table = editorDialog.data.grid_data;
    const headerLength = table.length > 0 ? table[0].length : 0;
    const newRow = Array(headerLength).fill('');
    table.push(newRow);
};
const deleteRowInDialog = (rowIndex) => { editorDialog.data.grid_data.splice(rowIndex + 1, 1); };
</script>

<template>
  <div class="device-analysis-page">
    <!-- 顶部器件搜索器 -->
    <el-card shadow="never" class="selector-card">
      <el-form :inline="true" @submit.prevent>
        <el-form-item label="器件搜索">
          <el-input v-model="searchQuery" placeholder="名称/编号/技术说明" clearable style="width: 250px;" />
        </el-form-item>
        <el-form-item label="器件类型">
          <el-select v-model="filterDeviceType" placeholder="所有类型" clearable style="width: 150px;">
            <el-option label="PIN" value="PIN" />
            <el-option label="其他" value="其他" />
          </el-select>
        </el-form-item>
        <el-form-item label="选择器件">
          <el-select
            v-model="selectedDeviceId"
            filterable
            placeholder="请选择"
            style="width: 300px;"
            :loading="selectLoading"
            @change="handleSelectChange"
          >
            <el-option
              v-for="device in filteredDevicesForSelect"
              :key="device.id"
              :label="`${device.name} (${device.device_number})`"
              :value="device.id"
            />
          </el-select>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 分析内容区 -->
    <div v-if="selectedDevice" class="analysis-content" v-loading="loading">
      <el-row :gutter="20" class="main-content">
        <!-- 左侧: 照片与自定义数据 -->
        <el-col :span="14" class="full-height-col data-panel">
          <el-card shadow="never" class="photo-card-main">
             <template #header><strong>{{ selectedDevice.name }} 微观照片</strong></template>
               <div class="photo-container"
                    @wheel.prevent="onPhotoWheel"
                    @mousedown.prevent="onPhotoMouseDown"
                    @mousemove.prevent="onPhotoMouseMove"
                    @mouseup="onPhotoMouseUp"
                    @mouseleave="onPhotoMouseUp"
               >
                   <el-image v-if="selectedDevice && selectedDevice.photo_data"
                             :src="selectedDevice.photo_data"
                             fit="contain"
                             class="micro-photo"
                             :style="{ transform: photoTransform }"
                   />
                   <el-empty v-else description="暂无照片" />
               </div>
          </el-card>
          <el-card shadow="never" class="editable-table-card">
             <template #header>
              <div class="card-header">
                <strong>{{ selectedDevice.name }} 自定义数据</strong>
                <el-button type="success" size="small" @click="openAddTableDialog">添加新表格</el-button>
              </div>
            </template>
            <div class="custom-tables-container">
              <el-collapse accordion @change="handleTableSelect" v-if="customTables.length > 0">
                <el-collapse-item v-for="table in customTables" :key="table.id" :name="table.id">
                <template #title>
                    <div class="collapse-title-wrapper">
                        <span class="collapse-title">{{ table.name }}</span>
                        <div class="collapse-actions">
                            <el-button type="primary" link @click.stop="openEditTableDialog(table)">编辑</el-button>
                            <el-button type="danger" link @click.stop="deleteCustomTable(table.id)">删除</el-button>
                        </div>
                    </div>
                </template>
                <div class="table-meta"><strong>实验类型:</strong> {{ table.experiment_type || '未指定' }}</div>
                <table class="preview-table">
                    <thead>
                    <tr><th v-for="(header, index) in table.grid_data[0]" :key="index">{{ header }}</th></tr>
                    </thead>
                    <tbody>
                    <tr v-for="(row, rowIndex) in table.grid_data.slice(1)" :key="rowIndex">
                        <td v-for="(cell, colIndex) in row" :key="colIndex">{{ cell }}</td>
                    </tr>
                    </tbody>
                </table>
                </el-collapse-item>
              </el-collapse>
              <el-empty v-else description="暂无自定义数据表"></el-empty>
            </div>
          </el-card>
        </el-col>
        <!-- 右侧: 可视化与波形 -->
        <el-col :span="10" class="full-height-col visual-panel">
          <!-- 右上: 数据可视化 -->
          <el-card shadow="never" class="data-visualization-card">
            <template #header>
              <div class="card-header">
                <strong>数据可视化</strong>
                <div class="waveform-controls" v-if="gridVisualization.activeTableId">
                    <el-select v-model="gridVisualization.xAxisKey" placeholder="X轴" size="small" style="width: 120px;">
                       <el-option v-for="key in gridChartAxisOptions" :key="key" :label="key" :value="key" />
                    </el-select>
                    <el-select v-model="gridVisualization.yAxisKey" placeholder="Y轴" size="small" style="width: 120px;">
                        <el-option v-for="key in gridChartAxisOptions" :key="key" :label="key" :value="key" />
                    </el-select>
                </div>
              </div>
            </template>
            <v-chart class="waveform-chart" :option="gridChartOptions" autoresize />
          </el-card>
          <!-- 右下: CSV波形 -->
          <el-card shadow="never" class="waveform-card">
            <template #header>
              <div class="card-header">
                <strong>CSV波形窗口</strong>
                 <div class="waveform-controls" v-if="waveform.activeCsvId">
                    <el-select v-model="waveform.activeCsvId" placeholder="选择CSV文件" size="small" v-if="waveform.availableCsvs.length > 1" style="width: 150px;">
                        <el-option v-for="csv in waveform.availableCsvs" :key="csv.id" :label="csv.filename" :value="csv.id" />
                    </el-select>
                    <el-select v-model="waveform.xAxisKey" placeholder="X轴" size="small" style="width: 100px;">
                        <el-option v-for="col in csvAxisOptions" :key="col.key" :label="col.name" :value="col.key" />
                    </el-select>
                    <el-select v-model="waveform.yAxisKey" placeholder="Y轴" size="small" style="width: 100px;">
                        <el-option v-for="col in csvAxisOptions" :key="col.key" :label="col.name" :value="col.key" />
                    </el-select>
                </div>
              </div>
            </template>
            <v-chart class="waveform-chart" :option="waveformChartOptions" autoresize />
          </el-card>
        </el-col>
      </el-row>
    </div>

    <!-- 占位提示 -->
    <el-card v-else shadow="never" class="placeholder-card">
      <el-empty description="请从上方搜索并选择一个器件开始分析" />
    </el-card>

    <!-- 所有对话框 -->
     <el-dialog v-model="editorDialog.visible" :title="editorDialog.title" width="80%" top="5vh">
        <el-form :model="editorDialog.data" label-width="100px">
            <el-form-item label="表格名称"><el-input v-model="editorDialog.data.name" /></el-form-item>
            <el-form-item label="实验类型"><el-input v-model="editorDialog.data.experiment_type" placeholder="例如: 注入试验" /></el-form-item>
        </el-form>

        <el-divider content-position="left">关联的CSV波形文件</el-divider>
        <div class="csv-list">
            <el-tag v-for="csv in editorDialog.data.csv_files" :key="csv.id" closable @close="deleteCsvInDialog(csv.id)">{{ csv.filename }}</el-tag>
            <el-button @click="triggerCsvUpload" size="small" type="primary" link>+ 导入CSV</el-button>
            <input type="file" id="csv-uploader" @change="handleCsvFileChange" accept=".csv" style="display: none;" />
        </div>

        <el-divider content-position="left">备注数据网格</el-divider>
         <div class="table-controls-dialog">
            <el-button @click="addRowInDialog" size="small">添加行</el-button>
            <el-button @click="addColumnInDialog" size="small">添加列</el-button>
        </div>
        <div class="editable-table-container-dialog">
            <table class="editable-table">
                <thead>
                    <tr>
                        <th v-for="(header, index) in editorDialog.data.grid_data[0]" :key="index">
                            <el-input v-model="editorDialog.data.grid_data[0][index]" size="small" placeholder="参数名称" />
                            <el-button type="danger" circle size="small" class="delete-btn" @click="deleteColumnInDialog(index)">X</el-button>
                        </th>
                        <th></th>
                    </tr>
                </thead>
                <tbody>
                    <tr v-for="(row, rowIndex) in editorDialog.data.grid_data.slice(1)" :key="rowIndex">
                        <td v-for="(cell, colIndex) in row" :key="colIndex">
                            <el-input v-model="editorDialog.data.grid_data[rowIndex + 1][colIndex]" size="small" />
                        </td>
                        <td>
                            <el-button type="danger" circle size="small" class="delete-btn" @click="deleteRowInDialog(rowIndex)">X</el-button>
                        </td>
                    </tr>
                </tbody>
            </table>
        </div>

        <template #footer>
            <el-button @click="editorDialog.visible = false">取消</el-button>
            <el-button type="primary" @click="handleSaveChangesInDialog">确认保存</el-button>
        </template>
    </el-dialog>

    <el-dialog v-model="csvMetadataDialog.visible" :title="`定义CSV文件列: ${csvMetadataDialog.filename}`" width="60%">
        <p>请为导入的CSV文件每一列定义名称和单位。</p>
        <el-table :data="csvMetadataDialog.columns" border>
            <el-table-column label="原始列" type="index" width="80" />
            <el-table-column label="数据名称"><template #default="scope"><el-input v-model="scope.row.name" /></template></el-table-column>
            <el-table-column label="单位"><template #default="scope"><el-input v-model="scope.row.unit" /></template></el-table-column>
        </el-table>
        <template #footer>
            <el-button @click="csvMetadataDialog.visible = false">取消</el-button>
            <el-button type="primary" @click="confirmCsvMetadata">确认定义</el-button>
        </template>
    </el-dialog>
  </div>
</template>

<style scoped>
/* --- 页面与搜索栏 --- */
.device-analysis-page { display: flex; flex-direction: column; height: 100%; gap: 20px; }
.selector-card { flex-shrink: 0; }
.selector-card .el-form-item { margin-bottom: 0; }
.analysis-content { flex-grow: 1; min-height: 0; }
.main-content { height: 100%; }
.full-height-col { height: 100%; display: flex; flex-direction: column; }
.card-header { display: flex; justify-content: space-between; align-items: center; width: 100%; }
.placeholder-card { flex-grow: 1; display: flex; align-items: center; justify-content: center; }

/* --- 左右面板 --- */
.data-panel { gap: 20px; }
.visual-panel { gap: 20px; }

/* --- 左侧面板 --- */
.photo-card-main { flex: 1 1 40%; min-height: 0; display: flex; flex-direction: column; }
.photo-card-main :deep(.el-card__body) { flex: 1 1 auto; min-height: 0; padding: 10px; display: flex; align-items: center; justify-content: center; }
.photo-container { width: 100%; height: 100%; overflow: hidden; cursor: grab; }
.photo-container:active { cursor: grabbing; }
.micro-photo { width: 100%; height: 100%; transition: transform 0.1s ease-out; }


.editable-table-card { flex: 1 1 60%; min-height: 0; display: flex; flex-direction: column; }
.editable-table-card :deep(.el-card__body) { flex: 1 1 auto; min-height: 0; padding: 15px; display: flex; flex-direction: column; }
.custom-tables-container { flex: 1 1 auto; overflow-y: auto; }
.collapse-title-wrapper { display: flex; justify-content: space-between; align-items: center; width: 100%; }
.collapse-title { font-weight: bold; flex-grow: 1; }
.collapse-actions { margin-right: 10px; }
.table-meta { font-size: 12px; color: #909399; margin-bottom: 10px; }
.preview-table { width: 100%; border-collapse: collapse; font-size: 12px; }
.preview-table th, .preview-table td { border: 1px solid #ebeef5; padding: 6px 8px; text-align: center; }
.preview-table th { background-color: #fafafa; }


/* --- 右侧面板 --- */
.data-visualization-card, .waveform-card {
    flex: 1 1 50%; /* 各占一半高度 */
    min-height: 0;
    display: flex;
    flex-direction: column;
}
.data-visualization-card :deep(.el-card__body), .waveform-card :deep(.el-card__body) {
    flex: 1 1 auto;
    min-height: 0;
    padding: 10px;
    display: flex;
}
.waveform-chart { flex: 1 1 auto; min-height: 0; }
.waveform-controls { display: flex; gap: 10px; }

/* --- 编辑器对话框 --- */
.csv-list { display: flex; flex-wrap: wrap; gap: 10px; align-items: center; margin-bottom: 20px; }
.table-controls-dialog { margin-bottom: 10px; }
.editable-table-container-dialog { max-height: 50vh; overflow: auto; }
.editable-table { width: 100%; border-collapse: collapse; }
.editable-table th, .editable-table td { border: 1px solid #ebeef5; padding: 4px; text-align: center; }
.editable-table th { position: relative; background-color: #fafafa; }
.editable-table .delete-btn { position: absolute; top: 50%; transform: translateY(-50%); right: 4px; display: none; }
.editable-table th:hover .delete-btn, .editable-table tr:hover .delete-btn { display: inline-flex; }
.editable-table th:last-child, .editable-table td:last-child { border: none; background-color: transparent; width: 40px; position: relative; }
.editable-table td:last-child .delete-btn { position: static; transform: none; }
</style>

