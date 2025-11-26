<template>
  <div class="end-to-end-content">
    <!-- 主要内容区域：四部分布局 -->
    <div class="main-grid">
      <!-- 左上：特征信息展示 -->
      <div class="grid-section feature-info-section">
        <FeatureInfoPanel :feature-data="currentFeatureInfo" />
      </div>

      <!-- 右上：性能对比图表 -->
      <div class="grid-section performance-section">
        <PerformanceComparisonChart :performance-data="currentPerformanceData" />
      </div>

      <!-- 右下：用时对比图表 -->
      <div class="grid-section time-section">
        <TimeComparisonChart :time-data="currentTimeData" />
      </div>

      <!-- 右下：特征重要性可视化 -->
      <div class="grid-section importance-section">
        <FeatureImportancePanel :importance-data="currentImportanceData" />
      </div>
    </div>

    <!-- 加载遮罩 -->
    <div v-if="showLoadingOverlay && executionStatus === 'running'" class="loading-overlay">
      <div class="loading-content">
        <div class="loading-spinner">
          <i class="bi bi-arrow-repeat"></i>
        </div>
        <h4>Running End-to-End Analysis</h4>
        <p>{{ loadingMessage }}</p>
        <div class="progress-bar">
          <div
            class="progress-fill"
            :style="{ width: `${progressPercentage}%` }"
          ></div>
        </div>
        <span class="progress-text">{{ progressPercentage }}% Complete</span>
      </div>
    </div>

    <!-- 成功提示 -->
    <div v-if="showSuccessNotification" class="success-notification">
      <i class="bi bi-check-circle"></i>
      <div class="notification-content">
        <h5>Analysis Complete!</h5>
        <p>End-to-end feature engineering has been successfully completed.</p>
      </div>
      <button class="btn-close" @click="showSuccessNotification = false">
        <i class="bi bi-x"></i>
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { useTaskStore } from '@/stores/task'
import { apiService } from '@/services/APIService'
import FeatureInfoPanel from '../../EndToEnd/FeatureInfoPanel.vue'
import PerformanceComparisonChart from '../../EndToEnd/PerformanceComparisonChart.vue'
import TimeComparisonChart from '../../EndToEnd/TimeComparisonChart.vue'
import FeatureImportancePanel from '../../EndToEnd/FeatureImportancePanel.vue'
import type { FeatureInfo, PerformanceData, TimeData, ImportanceData } from '@/types'

// 获取任务store
const taskStore = useTaskStore()

// 从auto-step获取的真实数据（直接使用简化后的数据结构）
const realFeatureInfo = computed(() => {
  const data = taskStore.autoStepData?.featureInfo
  if (!data) return null

  return {
    description: data.description || 'No description available',
    pythonCode: data.pythonCode || '# No Python code available',
    sqlCode: data.sqlCode || '-- No SQL code available'
  } as FeatureInfo
})

const realPerformanceData = computed(() => {
  const data = taskStore.autoStepData?.performanceData
  if (!data) return null

  return {
    methods: data.methods || [],
    auc: data.auc || [],
    f1: data.f1 || []
  } as PerformanceData
})

const realTimeData = computed(() => {
  const data = taskStore.autoStepData?.timeData
  if (!data) return null

  // 将后端传来的时间统一转换为 number，避免字符串被过滤掉导致图表缺项
  const toNumberArray = (arr: any[] | undefined) =>
    Array.isArray(arr) ? arr.map(v => (typeof v === 'number' ? v : Number(v) || 0)) : []

  return {
    methods: data.methods || [],
    totalTime: toNumberArray(data.totalTime),
    trainingTime: toNumberArray(data.trainingTime)
  } as TimeData
})

const realImportanceData = computed(() => {
  const data = taskStore.autoStepData?.importanceData
  if (!data) return null

  // 基础重要性数据（兼容旧格式），添加数据验证
  const validateAndCleanData = (data: any[] | undefined): FeatureImportance[] => {
    if (!data || !Array.isArray(data)) return []

    return data
      .filter(item => item && typeof item === 'object')
      .map(item => ({
        feature: item.feature || 'unknown',
        importance: typeof item.importance === 'number' && !isNaN(item.importance) && isFinite(item.importance)
          ? item.importance
          : 0
      }))
      .filter(item => item.importance > 0) // 只保留有效的正数
      .sort((a, b) => b.importance - a.importance)
  }

  // 添加调试信息
  console.log('Raw importance data from backend:', {
    shap: data.shap,
    ig: data.ig,
    rfe: data.rfe,
    fi: data.fi
  })

  const importanceData: ImportanceData = {
    shap: validateAndCleanData(data.shap),
    ig: validateAndCleanData(data.ig),
    rfe: validateAndCleanData(data.rfe),
    fi: validateAndCleanData(data.fi)
  }

  console.log('Validated importance data:', {
    shap: importanceData.shap.length,
    ig: importanceData.ig.length,
    rfe: importanceData.rfe.length,
    fi: importanceData.fi.length
  })

  // 添加 paper metrics 数据（如果存在）
  if (data.paperMetrics) {
    importanceData.paperMetrics = data.paperMetrics

    // 只要有成功的 paper metrics 就进行转换，因为数据更完整
    const needsConversion = data.paperMetrics && data.paperMetrics.success

    console.log('Paper metrics conversion check:', {
      hasPaperMetrics: !!data.paperMetrics,
      isSuccess: data.paperMetrics?.success,
      shapLength: data.shap?.length || 0,
      needsConversion: needsConversion
    })

    if (needsConversion) {
      console.log('Converting paper metrics to importance data format...')
      console.log('Original data.shap:', data.shap)
      console.log('Original data.ig:', data.ig)
      console.log('Paper metrics:', data.paperMetrics)

      const metrics = data.paperMetrics.metrics

      // 转换每个方法的特征重要性数据
      const convertMethodData = (method: keyof typeof metrics): FeatureImportance[] => {
        const methodData = metrics[method]
        if (!methodData || !methodData.feature_importance || methodData.error) {
          return []
        }

        const rawFeatures = Object.entries(methodData.feature_importance)
          .map(([feature, importance]) => {
            // 数据验证和清理
            let numImportance: number

            // 处理各种类型的importance值
            if (Array.isArray(importance)) {
              // JavaScript数组
              numImportance = importance.reduce((sum, val) => sum + Math.abs(val), 0) / importance.length
            } else if (typeof importance === 'object' && importance !== null) {
              // 处理类似Python numpy数组的对象格式
              // 假设格式如 { "type": "numpy.ndarray", "data": [0.002, 0.003] }
              if (importance.type === 'numpy.ndarray' && Array.isArray(importance.data)) {
                numImportance = importance.data.reduce((sum, val) => sum + Math.abs(val), 0) / importance.data.length
              } else {
                console.warn(`Unsupported object type for feature ${feature}:`, importance)
                numImportance = Number(importance) || 0
              }
            } else {
              // 标量值（number, string等）
              numImportance = Number(importance)
            }

            // 检查是否为有效数字
            if (isNaN(numImportance) || !isFinite(numImportance)) {
              console.warn(`Invalid importance value for feature ${feature}:`, importance)
              return null
            }

            return {
              feature,
              importance: numImportance
            }
          })
          .filter(feature => feature !== null) // 过滤掉无效数据

        // 标准化特征重要性值以改进可视化
        // SHAP值通常在0-1范围，IG和FI值可能很小
        if (rawFeatures.length === 0) return []

        // 计算最大值进行归一化
        const maxImportance = rawFeatures.length > 0
          ? Math.max(...rawFeatures.map(f => f.importance))
          : 0

        // 不同方法使用不同的缩放策略
        let scaledFeatures = rawFeatures
        if (method === 'ig' && maxImportance < 0.1) {
          // 对于信息增益，如果值很小，进行缩放
          scaledFeatures = rawFeatures.map(f => ({
            ...f,
            importance: f.importance * 10, // 放大10倍
            rawImportance: f.importance,
            scalingFactor: 10
          }))
        } else if (method === 'fi' && maxImportance < 0.2) {
          // 对于特征重要性，如果值很小，进行缩放
          scaledFeatures = rawFeatures.map(f => ({
            ...f,
            importance: f.importance * 5, // 放大5倍
            rawImportance: f.importance,
            scalingFactor: 5
          }))
        } else if (method === 'shap') {
          // 对于SHAP值，总是进行适当缩放，因为SHAP值通常较小
          const scaleFactor = maxImportance < 0.01 ? 100 : maxImportance < 0.1 ? 10 : 1
          scaledFeatures = rawFeatures.map(f => ({
            ...f,
            importance: f.importance * scaleFactor,
            rawImportance: f.importance,
            scalingFactor: scaleFactor
          }))
        } else {
          // 即使不需要缩放，也保存原始值
          scaledFeatures = rawFeatures.map(f => ({
            ...f,
            rawImportance: f.importance,
            scalingFactor: 1
          }))
        }

        return scaledFeatures.sort((a, b) => b.importance - a.importance)
      }

      importanceData.shap = convertMethodData('shap')
      importanceData.ig = convertMethodData('ig')
      importanceData.rfe = convertMethodData('rfe')
      importanceData.fi = convertMethodData('fi')

      console.log('Converted importance data:', {
        shap: importanceData.shap.length,
        shapData: importanceData.shap.slice(0, 3), // 显示前3个数据
        ig: importanceData.ig.length,
        igData: importanceData.ig.slice(0, 3),
        rfe: importanceData.rfe.length,
        rfeData: importanceData.rfe.slice(0, 3),
        fi: importanceData.fi.length,
        fiData: importanceData.fi.slice(0, 3)
      })

      // 检查是否有NaN值
      const checkForNaN = (methodName: string, data: any[]) => {
        const nanCount = data.filter(item => isNaN(item.importance) || !isFinite(item.importance)).length
        if (nanCount > 0) {
          console.error(`${methodName} contains ${nanCount} NaN values:`, data.filter(item => isNaN(item.importance) || !isFinite(item.importance)))
        } else {
          console.log(`${methodName} data is valid, no NaN values found`)
        }
      }

      checkForNaN('SHAP', importanceData.shap)
      checkForNaN('IG', importanceData.ig)
      checkForNaN('RFE', importanceData.rfe)
      checkForNaN('FI', importanceData.fi)
    }
  }

  return importanceData
})

// 端到端执行相关的状态管理
const progressPercentage = ref(0)
const loadingMessage = ref('Initializing feature engineering pipeline...')
// 默认不展示运行遮罩层
const showLoadingOverlay = ref(false)
const showSuccessNotification = ref(false)
const executionTimeout = ref<number | null>(null)
const POLLING_INTERVAL = 5000 // 5秒轮询一次

// 计算属性 - 使用taskStore的状态或本地状态
const executionStatus = computed(() => {
  if (taskStore.isRunning) return 'running'
  if (taskStore.error) return 'error'
  if (taskStore.autoStepData) return 'completed'
  return 'idle'
})

// 计算属性 - 直接使用简化后的数据结构
const currentFeatureInfo = computed(() => realFeatureInfo.value)
const currentPerformanceData = computed(() => realPerformanceData.value)
const currentTimeData = computed(() => realTimeData.value)
const currentImportanceData = computed(() => realImportanceData.value)

const getStatusText = () => {
  switch (executionStatus.value) {
    case 'idle':
      return 'Ready'
    case 'running':
      return 'Running'
    case 'completed':
      return 'Completed'
    case 'error':
      return 'Error'
    default:
      return 'Unknown'
  }
}

const runEndToEndExecution = async () => {
  try {
    // 调试：打印当前配置
    console.log('EndToEnd Execution - Current Config:', {
      description: taskStore.config.description,
      descriptionLength: taskStore.config.description?.length || 0,
      dataset: taskStore.config.dataset,
      model: taskStore.config.model
    })

    // 检查配置是否有效
    if (!taskStore.config.description.trim()) {
      taskStore.addNotification('Please enter a task description', 'fail')
      return
    }

    // 重置状态
    progressPercentage.value = 0
    showSuccessNotification.value = false
    taskStore.error = null

    // 开始执行
    loadingMessage.value = 'Initializing end-to-end pipeline...'
    progressPercentage.value = 10

    // 调用autoStep，传入配置进行初始化
    const success = await taskStore.autoStep(true) // 使用配置

    if (!success) {
      throw new Error(taskStore.error || 'Failed to start end-to-end execution')
    }

    loadingMessage.value = 'Running end-to-end analysis...'
    progressPercentage.value = 30

    // 开始轮询检查任务状态
    await pollTaskStatus()

  } catch (error) {
    console.error('End-to-end execution failed:', error)
    taskStore.error = error instanceof Error ? error.message : 'Unknown error occurred'
    taskStore.addNotification(`End-to-end execution failed: ${taskStore.error}`, 'fail')
  }
}

// 轮询任务状态
const pollTaskStatus = async () => {
  let attempts = 0
  const maxAttempts = 120 // 最多轮询10分钟

  const poll = async () => {
    attempts++

    try {
      // 更新进度（模拟进度，实际应该基于后端状态）
      if (attempts <= 10) {
        progressPercentage.value = 30 + (attempts * 5)
        loadingMessage.value = 'Analyzing data patterns...'
      } else if (attempts <= 30) {
        progressPercentage.value = 50 + ((attempts - 10) * 1.5)
        loadingMessage.value = 'Generating features...'
      } else if (attempts <= 60) {
        progressPercentage.value = 70 + ((attempts - 30) * 0.5)
        loadingMessage.value = 'Training models and evaluating performance...'
      } else {
        progressPercentage.value = Math.min(90 + ((attempts - 60) * 0.2), 95)
        loadingMessage.value = 'Computing feature importance and finalizing results...'
      }

      // 检查是否有结果数据
      if (taskStore.autoStepData) {
        console.log('E2E execution completed:', taskStore.autoStepData)

        // 完成执行
        progressPercentage.value = 100
        loadingMessage.value = 'Analysis complete!'

        // 显示成功通知
        setTimeout(() => {
          showSuccessNotification.value = true
          setTimeout(() => {
            showSuccessNotification.value = false
          }, 5000)
        }, 500)

        return
      }

      // 继续轮询
      if (attempts < maxAttempts) {
        executionTimeout.value = setTimeout(poll, POLLING_INTERVAL)
      } else {
        // 超时
        throw new Error('End-to-end execution timed out after 10 minutes')
      }

    } catch (error) {
      console.error('Polling error:', error)
      throw error
    }
  }

  // 开始轮询
  executionTimeout.value = setTimeout(poll, POLLING_INTERVAL)
}

// 停止执行
const stopExecution = () => {
  if (executionTimeout.value) {
    clearTimeout(executionTimeout.value)
    executionTimeout.value = null
  }

  taskStore.stopTask()
  progressPercentage.value = 0
  loadingMessage.value = 'Execution stopped'
}

onMounted(() => {
  // 初始化端到端执行页面
  console.log('End-to-end execution page loaded')

  // 调试：打印初始配置
  console.log('Initial Task Config:', {
    description: taskStore.config.description,
    descriptionLength: taskStore.config.description?.length || 0,
    dataset: taskStore.config.dataset,
    model: taskStore.config.model
  })

  // 检查任务状态
  taskStore.checkTaskStatus()
})

onUnmounted(() => {
  // 清理定时器
  if (executionTimeout.value) {
    clearTimeout(executionTimeout.value)
    executionTimeout.value = null
  }
})
</script>

<style scoped>
.end-to-end-content {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: #fff;
  overflow: hidden;
  padding: var(--spacing-lg);
  gap: var(--spacing-md);
  --font-size-sm: 1rem;
  --font-size-md: 1.35rem;
  --font-size-lg: 1.65rem;
  --font-size-xl: 2.1rem;
  --spacing-md: 1.25rem;
  --spacing-lg: 2rem;
}

/* Scrollbar behavior - hidden by default, visible on interaction */
.end-to-end-content,
.end-to-end-content * {
  scrollbar-width: none;
  scrollbar-color: transparent transparent;
}

.end-to-end-content *::-webkit-scrollbar {
  width: 0;
  height: 0;
  background: transparent;
}

.end-to-end-content *:hover {
  scrollbar-width: thin;
  scrollbar-color: rgba(0, 0, 0, 0.3) transparent;
}

.end-to-end-content *:hover::-webkit-scrollbar {
  width: 8px;
  height: 8px;
}

.end-to-end-content *:hover::-webkit-scrollbar-thumb {
  background: rgba(0, 0, 0, 0.3);
  border-radius: 8px;
}

.end-to-end-content *:hover::-webkit-scrollbar-track {
  background: transparent;
}

@media print {
  .end-to-end-content {
    background: #fff;
    padding: 0.5in;
  }

  .end-to-end-content .grid-section {
    box-shadow: none;
    border-color: #000;
  }
}

/* 页面头部 */
.page-header {
  background: var(--bg-white);
  border-bottom: 1px solid var(--border-color);
  padding: var(--spacing-md) var(--spacing-lg);
  flex-shrink: 0;
}

.header-content {
  display: flex;
  justify-content: space-between;
  align-items: center;
  max-width: 1400px;
  margin: 0 auto;
}

.header-title {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.header-title-main {
  display: flex;
  align-items: center;
  gap: 12px;
}

.header-title i {
  font-size: 28px;
  color: var(--primary-color);
}

.header-title h2 {
  margin: 0;
  font-size: var(--font-size-xl);
  font-weight: 700;
  color: var(--text-primary);
}

.data-source-indicator {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 14px;
  padding: 4px 8px;
  border-radius: 12px;
  background: rgba(0, 123, 255, 0.1);
  border: 1px solid rgba(0, 123, 255, 0.2);
  color: var(--text-secondary);
  width: fit-content;
}

.data-source-indicator i {
  font-size: 16px;
}

.text-success {
  color: var(--success-color) !important;
}

.text-warning {
  color: var(--warning-color) !important;
}

.header-status {
  display: flex;
  align-items: center;
  gap: 16px;
}

.status-badge {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  border-radius: 20px;
  font-size: 15px;
  font-weight: 500;
  border: 1px solid var(--border-color);
}

.status-badge.completed {
  background: rgba(40, 167, 69, 0.1);
  color: var(--success-color, #28a745);
  border-color: rgba(40, 167, 69, 0.2);
}

.status-badge.running {
  background: rgba(255, 193, 7, 0.1);
  color: var(--warning-color, #ffc107);
  border-color: rgba(255, 193, 7, 0.2);
}

.status-badge.idle {
  background: rgba(108, 117, 125, 0.1);
  color: var(--text-secondary);
  border-color: rgba(108, 117, 125, 0.2);
}

.status-badge.error {
  background: rgba(220, 53, 69, 0.1);
  color: var(--danger-color, #dc3545);
  border-color: rgba(220, 53, 69, 0.2);
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: currentColor;
}

.status-badge.running .status-dot {
  animation: pulse 1.5s infinite;
}

.btn-primary {
  background: var(--primary-color);
  color: white;
  border: none;
  padding: 10px 20px;
  border-radius: 8px;
  font-weight: 500;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  transition: all 0.2s ease;
  font-size: 16px;
}

.btn-primary:hover:not(:disabled) {
  background: var(--primary-hover);
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(0, 123, 255, 0.3);
}

.btn-primary:disabled {
  opacity: 0.6;
  cursor: not-allowed;
  transform: none;
}

.btn-danger {
  background: var(--danger-color, #dc3545);
  color: white;
  border: none;
  padding: 10px 20px;
  border-radius: 8px;
  font-weight: 500;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  transition: all 0.2s ease;
  font-size: 16px;
}

.btn-danger:hover {
  background: #c82333;
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(220, 53, 69, 0.3);
}

.spinning {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.3; }
}

/* 主要网格布局 */
.main-grid {
  flex: 1;
  padding: var(--spacing-md);
  display: grid;
  grid-template-columns: 1fr 1fr;
  grid-template-rows: 1fr 1fr;
  gap: 28px;
  overflow: hidden;
  min-height: 0;
}

.grid-section {
  background: var(--bg-white);
  border-radius: 12px;
  box-shadow: var(--shadow-md);
  border: 2px solid var(--border-color);
  overflow: hidden;
  display: flex;
  flex-direction: column;
  min-height: 0;
  padding: 1.25rem;
}

/* 特定区域样式 */
.feature-info-section {
  grid-row: 1 / 2;
  grid-column: 1 / 2;
}

.performance-section {
  grid-row: 1 / 2;
  grid-column: 2 / 3;
}

.time-section {
  grid-row: 2 / 3;
  grid-column: 1 / 2;
}

.importance-section {
  grid-row: 2 / 3;
  grid-column: 2 / 3;
}

/* 加载遮罩 */
.loading-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.7);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  backdrop-filter: blur(4px);
}

.loading-content {
  background: var(--bg-white);
  border-radius: 16px;
  padding: 40px;
  text-align: center;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
  max-width: 400px;
  width: 90%;
}

.loading-spinner {
  margin-bottom: 20px;
}

.loading-spinner i {
  font-size: 48px;
  color: var(--primary-color);
  animation: spin 2s linear infinite;
}

.loading-content h4 {
  margin: 0 0 12px 0;
  font-size: var(--font-size-lg);
  font-weight: 600;
  color: var(--text-primary);
}

.loading-content p {
  margin: 0 0 24px 0;
  color: var(--text-secondary);
  font-size: var(--font-size-md);
}

.progress-bar {
  width: 100%;
  height: 8px;
  background: var(--bg-light);
  border-radius: 4px;
  overflow: hidden;
  margin-bottom: 12px;
}

.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, var(--primary-color), #4dabf7);
  border-radius: 4px;
  transition: width 0.3s ease;
}

.progress-text {
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
  font-weight: 500;
}

/* 成功通知 */
.success-notification {
  position: fixed;
  top: 20px;
  right: 20px;
  background: var(--success-color, #28a745);
  color: white;
  border-radius: 12px;
  padding: 16px 20px;
  box-shadow: 0 10px 30px rgba(40, 167, 69, 0.3);
  display: flex;
  align-items: center;
  gap: 12px;
  z-index: 1001;
  min-width: 320px;
  font-size: var(--font-size-md);
  animation: slideInRight 0.3s ease;
}

.success-notification i {
  font-size: 24px;
  flex-shrink: 0;
}

.notification-content {
  flex: 1;
}

.notification-content h5 {
  margin: 0 0 4px 0;
  font-size: var(--font-size-md);
  font-weight: 600;
}

.notification-content p {
  margin: 0;
  font-size: var(--font-size-sm);
  opacity: 0.9;
}

.btn-close {
  background: none;
  border: none;
  color: white;
  font-size: 20px;
  cursor: pointer;
  padding: 4px;
  border-radius: 4px;
  opacity: 0.8;
  transition: opacity 0.2s ease;
}

.btn-close:hover {
  opacity: 1;
}

@keyframes slideInRight {
  from {
    transform: translateX(100%);
    opacity: 0;
  }
  to {
    transform: translateX(0);
    opacity: 1;
  }
}

/* 响应式设计 */
@media (max-width: 1200px) {
  .main-grid {
    grid-template-columns: 1fr;
    grid-template-rows: auto auto auto auto;
    gap: 16px;
  }

  .feature-info-section {
    grid-row: 1 / 2;
    grid-column: 1 / 2;
  }

  .performance-section {
    grid-row: 2 / 3;
    grid-column: 1 / 2;
  }

  .time-section {
    grid-row: 3 / 4;
    grid-column: 1 / 2;
  }

  .importance-section {
    grid-row: 4 / 5;
    grid-column: 1 / 2;
  }
}

@media (max-width: 768px) {
  .page-header {
    padding: 12px 16px;
  }

  .header-content {
    flex-direction: column;
    gap: 16px;
    align-items: stretch;
  }

  .header-title h2 {
    font-size: 20px;
  }

  .header-status {
    justify-content: space-between;
  }

  .main-grid {
    padding: 12px;
    gap: 12px;
  }

  .loading-content {
    padding: 24px;
    margin: 20px;
  }

  .success-notification {
    right: 12px;
    left: 12px;
    min-width: auto;
  }
}

/* CSS变量支持 */
:root {
  --bg-light: #f8f9fa;
  --bg-white: #ffffff;
  --bg-primary: #e9ecef;
  --border-color: #dee2e6;
  --text-primary: #212529;
  --text-secondary: #6c757d;
  --text-placeholder: #adb5bd;
  --primary-color: #007bff;
  --primary-hover: #0056b3;
  --success-color: #28a745;
  --warning-color: #ffc107;
  --danger-color: #dc3545;
  --shadow-sm: 0 2px 4px rgba(0,0,0,0.1);
  --shadow-md: 0 4px 8px rgba(0,0,0,0.15);
}

/* 深色主题适配 */
@media (prefers-color-scheme: dark) {
  :root {
    --bg-light: #2d3748;
    --bg-white: #1a202c;
    --bg-primary: #4a5568;
    --border-color: #4a5568;
    --text-primary: #e2e8f0;
    --text-secondary: #a0aec0;
    --text-placeholder: #718096;
  }
}
</style>
