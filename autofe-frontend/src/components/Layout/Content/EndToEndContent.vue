<template>
  <div class="end-to-end-content">
    <!-- 页面标题和状态 -->
    <div class="page-header">
      <div class="header-content">
        <div class="header-title">
          <i class="bi bi-lightning-charge"></i>
          <h2>End-to-End Feature Engineering</h2>
        </div>
        <div class="header-status">
          <div class="status-badge" :class="executionStatus">
            <span class="status-dot"></span>
            {{ getStatusText() }}
          </div>
          <button
            class="btn-primary"
            @click="runEndToEndExecution"
            :disabled="executionStatus === 'running'"
          >
            <i class="bi bi-play-circle" v-if="executionStatus !== 'running'"></i>
            <i class="bi bi-arrow-repeat spinning" v-else></i>
            {{ executionStatus === 'running' ? 'Running...' : 'Run End-to-End' }}
          </button>
        </div>
      </div>
    </div>

    <!-- 主要内容区域：四部分布局 -->
    <div class="main-grid">
      <!-- 左上：特征信息展示 -->
      <div class="grid-section feature-info-section">
        <FeatureInfoPanel :feature-data="mockFeatureInfo" />
      </div>

      <!-- 右上：性能对比图表 -->
      <div class="grid-section performance-section">
        <PerformanceComparisonChart :performance-data="mockPerformanceData" />
      </div>

      <!-- 右下：用时对比图表 -->
      <div class="grid-section time-section">
        <TimeComparisonChart :time-data="mockTimeData" />
      </div>

      <!-- 右下：特征重要性可视化 -->
      <div class="grid-section importance-section">
        <FeatureImportancePanel :importance-data="mockImportanceData" />
      </div>
    </div>

    <!-- 加载遮罩 -->
    <div v-if="executionStatus === 'running'" class="loading-overlay">
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
import { ref, onMounted } from 'vue'
import FeatureInfoPanel from '../../EndToEnd/FeatureInfoPanel.vue'
import PerformanceComparisonChart from '../../EndToEnd/PerformanceComparisonChart.vue'
import TimeComparisonChart from '../../EndToEnd/TimeComparisonChart.vue'
import FeatureImportancePanel from '../../EndToEnd/FeatureImportancePanel.vue'
import {
  mockFeatureInfo,
  mockPerformanceData,
  mockTimeData,
  mockImportanceData
} from '../../EndToEnd/mockData'

// 端到端执行相关的状态管理
const executionStatus = ref<'idle' | 'running' | 'completed' | 'error'>('completed') // 默认显示完成状态
const progressPercentage = ref(0)
const loadingMessage = ref('Initializing feature engineering pipeline...')
const showSuccessNotification = ref(false)

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
  executionStatus.value = 'running'
  progressPercentage.value = 0
  showSuccessNotification.value = false

  const steps = [
    { message: 'Loading dataset...', duration: 800 },
    { message: 'Analyzing data patterns...', duration: 1200 },
    { message: 'Generating features...', duration: 1500 },
    { message: 'Training models...', duration: 2000 },
    { message: 'Evaluating performance...', duration: 1000 },
    { message: 'Computing feature importance...', duration: 800 },
    { message: 'Finalizing results...', duration: 500 }
  ]

  const stepIncrement = 100 / steps.length

  for (let i = 0; i < steps.length; i++) {
    const step = steps[i]
    loadingMessage.value = step.message

    // 模拟进度更新
    await new Promise(resolve => {
      const startTime = Date.now()
      const updateProgress = () => {
        const elapsed = Date.now() - startTime
        const progress = Math.min((elapsed / step.duration) * stepIncrement, stepIncrement)
        progressPercentage.value = Math.min(
          progressPercentage.value + progress,
          (i + 1) * stepIncrement
        )

        if (elapsed < step.duration) {
          requestAnimationFrame(updateProgress)
        } else {
          resolve(true)
        }
      }
      updateProgress()
    })
  }

  // 完成执行
  executionStatus.value = 'completed'
  progressPercentage.value = 100
  loadingMessage.value = 'Analysis complete!'

  // 显示成功通知
  setTimeout(() => {
    showSuccessNotification.value = true
    setTimeout(() => {
      showSuccessNotification.value = false
    }, 5000)
  }, 500)
}

onMounted(() => {
  // 初始化端到端执行页面
  console.log('End-to-end execution page loaded with mock data')
})
</script>

<style scoped>
.end-to-end-content {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--bg-light);
  overflow: hidden;
}

/* 页面头部 */
.page-header {
  background: var(--bg-white);
  border-bottom: 1px solid var(--border-color);
  padding: 16px 20px;
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
  align-items: center;
  gap: 12px;
}

.header-title i {
  font-size: 28px;
  color: var(--primary-color);
}

.header-title h2 {
  margin: 0;
  font-size: 24px;
  font-weight: 700;
  color: var(--text-primary);
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
  font-size: 13px;
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
  font-size: 14px;
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
  padding: 20px;
  display: grid;
  grid-template-columns: 1fr 1fr;
  grid-template-rows: 1fr 1fr;
  gap: 20px;
  overflow: hidden;
  min-height: 0;
}

.grid-section {
  background: var(--bg-white);
  border-radius: 12px;
  box-shadow: var(--shadow-sm);
  border: 1px solid var(--border-color);
  overflow: hidden;
  display: flex;
  flex-direction: column;
  min-height: 0;
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
  font-size: 20px;
  font-weight: 600;
  color: var(--text-primary);
}

.loading-content p {
  margin: 0 0 24px 0;
  color: var(--text-secondary);
  font-size: 14px;
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
  font-size: 13px;
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
  font-size: 16px;
  font-weight: 600;
}

.notification-content p {
  margin: 0;
  font-size: 13px;
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