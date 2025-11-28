<template>
  <div class="feature-performance-container">
    <div class="component-header">
      <div class="title">
        <i class="bi bi-graph-up"></i>
        Feature Performance
      </div>
      <div class="actions">
        <button class="btn-icon" @click="refreshData" :disabled="props.isLoading || isRefreshing">
          <i class="bi bi-arrow-clockwise" :class="{ 'spinning': props.isLoading || isRefreshing }"></i>
        </button>
        <button class="btn-icon" @click="exportData" :disabled="!hasData || props.isLoading">
          <i class="bi bi-download"></i>
        </button>
      </div>
    </div>

    <div class="performance-content">
      <!-- Loading State -->
      <div v-if="props.isLoading" class="loading-state">
        <div class="loading-content">
          <div class="spinner-border text-primary" role="status">
            <span class="visually-hidden">Loading performance data...</span>
          </div>
          <p class="mt-3 mb-0">Testing performance...</p>
          <small>Please wait while we analyze your features</small>
        </div>
      </div>

      <div v-else-if="hasData" class="metrics-grid">
        <!-- Performance Metrics -->
        <div class="metric-card performance">
          <div class="metric-header">
            <i class="bi bi-speedometer2"></i>
            <h6>Performance</h6>
          </div>
          <div class="metric-value">
            <span class="value">{{ formatPerformance(performanceData?.accuracy || 0) }}</span>
            <span class="unit">accuracy</span>
          </div>
          <div class="metric-details">
            <div class="detail-item">
              <span>Precision:</span>
              <strong>{{ formatPerformance(performanceData?.precision || 0) }}</strong>
            </div>
            <div class="detail-item">
              <span>Recall:</span>
              <strong>{{ formatPerformance(performanceData?.recall || 0) }}</strong>
            </div>
            <div class="detail-item">
              <span>F1-Score:</span>
              <strong>{{ formatPerformance(performanceData?.f1Score || 0) }}</strong>
            </div>
          </div>
        </div>

        <!-- Time Usage -->
        <div class="metric-card time">
          <div class="metric-header">
            <i class="bi bi-clock"></i>
            <h6>Time Usage</h6>
          </div>
          <div class="metric-value">
            <span class="value">{{ formatTime(timeData?.total || 0) }}</span>
            <span class="unit">total</span>
          </div>
          <div class="metric-details">
            <div class="detail-item">
              <span>Generation:</span>
              <strong>{{ formatTime(timeData?.generation || 0) }}</strong>
            </div>
            <div class="detail-item">
              <span>Evaluation:</span>
              <strong>{{ formatTime(timeData?.evaluation || 0) }}</strong>
            </div>
            <div class="detail-item">
              <span>Selection:</span>
              <strong>{{ formatTime(timeData?.selection || 0) }}</strong>
            </div>
          </div>
        </div>

        <!-- SHAP Values -->
        <div class="metric-card shap">
          <div class="metric-header">
            <i class="bi bi-bar-chart"></i>
            <h6>SHAP Analysis</h6>
          </div>
          <div class="shap-summary">
            <div class="shap-info">
              <span class="shap-label">Mean |SHAP|</span>
              <span class="shap-value">{{ formatShap(shapData?.meanShap || 0) }}</span>
            </div>
            <div class="shap-chart">
              <div class="shap-bar-container">
                <div
                  v-for="(feature, index) in topFeatures"
                  :key="index"
                  class="shap-bar-item"
                >
                  <span class="feature-name">{{ feature.name }}</span>
                  <div class="shap-bar">
                    <div
                      class="shap-bar-fill"
                      :style="{ width: `${feature.percentage}%` }"
                    ></div>
                  </div>
                  <span class="shap-bar-value">{{ formatShap(feature.value) }}</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Empty State -->
      <div v-else class="empty-state">
        <i class="bi bi-graph-up-arrow"></i>
        <h3>No Performance Data</h3>
        <p>Execute feature generation and evaluation to see performance metrics</p>
        <button class="btn btn-primary" @click="$emit('generateFeatures')">
          <i class="bi bi-play-circle"></i>
          Generate Features
        </button>
      </div>
    </div>

    <!-- Detailed Modal -->
    <div class="modal fade" v-if="showDetails" @click.self="showDetails = false">
      <div class="modal-dialog modal-lg">
        <div class="modal-content">
          <div class="modal-header">
            <h5 class="modal-title">
              <i class="bi bi-graph-up"></i>
              Detailed Performance Analysis
            </h5>
            <button type="button" class="btn-close" @click="showDetails = false"></button>
          </div>
          <div class="modal-body">
            <div class="detailed-metrics">
              <!-- Performance Charts -->
              <div class="chart-section">
                <h6>Performance Metrics</h6>
                <div class="chart-placeholder">
                  <i class="bi bi-bar-chart-line"></i>
                  <p>Performance charts will be displayed here</p>
                </div>
              </div>

              <!-- Time Analysis -->
              <div class="chart-section">
                <h6>Time Analysis</h6>
                <div class="chart-placeholder">
                  <i class="bi bi-clock-history"></i>
                  <p>Time breakdown charts will be displayed here</p>
                </div>
              </div>

              <!-- SHAP Analysis -->
              <div class="chart-section">
                <h6>Feature Importance (SHAP)</h6>
                <div class="chart-placeholder">
                  <i class="bi bi-tornado"></i>
                  <p>SHAP visualization will be displayed here</p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'

interface PerformanceData {
  accuracy: number
  precision: number
  recall: number
  f1Score: number
  auc?: number
}

interface TimeData {
  total: number
  generation: number
  evaluation: number
  selection: number
}

interface ShapFeature {
  name: string
  value: number
  percentage: number
}

interface ShapData {
  meanShap: number
  features: ShapFeature[]
}

const props = defineProps<{
  performanceData?: PerformanceData
  timeData?: TimeData
  shapData?: ShapData
  isLoading?: boolean
}>()

const emit = defineEmits<{
  generateFeatures: []
  refreshData: []
}>()

const isRefreshing = ref(false)
const showDetails = ref(false)

const hasData = computed(() => {
  return props.performanceData || props.timeData || props.shapData
})

const topFeatures = computed(() => {
  if (!props.shapData?.features) return []
  return props.shapData.features.slice(0, 5)
})

const formatPerformance = (value: number): string => {
  return (value * 100).toFixed(2) + '%'
}

const formatTime = (value: number): string => {
  if (value < 60) {
    return `${value.toFixed(1)}s`
  } else if (value < 3600) {
    return `${(value / 60).toFixed(1)}m`
  } else {
    return `${(value / 3600).toFixed(2)}h`
  }
}

const formatShap = (value: number): string => {
  return value.toFixed(4)
}

const refreshData = async () => {
  isRefreshing.value = true
  try {
    await new Promise(resolve => setTimeout(resolve, 1000))
    emit('refreshData')
  } finally {
    isRefreshing.value = false
  }
}

const exportData = () => {
  const data = {
    performance: props.performanceData,
    time: props.timeData,
    shap: props.shapData,
    timestamp: new Date().toISOString()
  }

  const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `feature-performance-${Date.now()}.json`
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}
</script>

<style scoped>
.feature-performance-container {
  background: #fff;
  border-radius: 12px;
  box-shadow: none;
  border: none;
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
}

.component-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 14px;
  border-bottom: 2px solid var(--accent-blue, #2a7de1);
  background: transparent;
}

.title {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  font-weight: 600;
  color: var(--text-primary);
  font-size: var(--font-size-md);
}

.actions {
  display: flex;
  gap: 4px;
}

.btn-icon {
  background: none;
  border: none;
  padding: 6px;
  border-radius: 6px;
  cursor: pointer;
  color: var(--text-secondary);
  transition: all 0.2s ease;
  display: flex;
  align-items: center;
  justify-content: center;
}

.btn-icon:hover:not(:disabled) {
  background: rgba(42, 125, 225, 0.08);
  color: var(--accent-blue, #2a7de1);
}

.btn-icon:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-icon.spinning i {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.performance-content {
  flex: 1;
  padding: 0.95rem;
  overflow-y: auto;
  min-height: 0;
}

.metrics-grid {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.metric-card {
  background: #fff;
  border-radius: 10px;
  padding: 0.85rem;
  border: none;
  box-shadow: none;
  transition: all 0.2s ease;
}

.metric-card:hover {
  box-shadow: none;
  transform: translateY(-1px);
}

.metric-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
}

.metric-header i {
  font-size: 18px;
  color: var(--primary-color);
}

.metric-header h6 {
  margin: 0;
  font-size: var(--font-size-sm);
  font-weight: 600;
  color: var(--text-primary);
}

.metric-value {
  display: flex;
  align-items: baseline;
  gap: 8px;
  margin-bottom: 12px;
}

.metric-value .value {
  font-size: 36px;
  font-weight: 700;
  color: var(--text-primary);
}

.metric-value .unit {
  font-size: 18px;
  color: var(--text-secondary);
  text-transform: uppercase;
}

.metric-details {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.detail-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 18px;
}

.detail-item span {
  color: var(--text-secondary);
}

.detail-item strong {
  color: var(--text-primary);
  font-weight: 500;
}

/* Performance specific styling */
.metric-card.performance .metric-header i {
  color: #10b981;
}

.metric-card.performance .metric-value .value {
  color: #10b981;
}

/* Time specific styling */
.metric-card.time .metric-header i {
  color: #3b82f6;
}

.metric-card.time .metric-value .value {
  color: #3b82f6;
}

/* SHAP specific styling */
.metric-card.shap .metric-header i {
  color: #f59e0b;
}

.shap-summary {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.shap-info {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 12px;
  background: rgba(245, 158, 11, 0.1);
  border-radius: 6px;
  border: 1px solid rgba(245, 158, 11, 0.2);
}

.shap-label {
  font-size: 12px;
  color: var(--text-secondary);
  font-weight: 500;
}

.shap-value {
  font-size: 20px;
  font-weight: 600;
  color: #f59e0b;
}

.shap-bar-container {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.shap-bar-item {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  font-size: 16px;
}

.feature-name {
  flex: 0 0 120px;
  color: var(--text-secondary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.shap-bar {
  flex: 1;
  height: 6px;
  background: var(--border-color);
  border-radius: 3px;
  overflow: hidden;
}

.shap-bar-fill {
  height: 100%;
  background: linear-gradient(90deg, #f59e0b, #f97316);
  border-radius: 3px;
  transition: width 0.3s ease;
}

.shap-bar-value {
  flex: 0 0 40px;
  text-align: right;
  color: var(--text-primary);
  font-weight: 500;
}

.empty-state {
  text-align: center;
  padding: 40px 20px;
  color: var(--text-secondary);
}

.empty-state i {
  font-size: 48px;
  color: var(--text-placeholder);
  margin-bottom: 16px;
  display: block;
}

.loading-state {
  text-align: center;
  padding: 40px 20px;
  color: var(--text-secondary);
}

.loading-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
}

.loading-content p {
  margin: 8px 0 4px 0;
  font-size: 16px;
  font-weight: 500;
  color: var(--text-primary);
}

.loading-content small {
  font-size: 14px;
  color: var(--text-secondary);
}

.empty-state h3 {
  margin: 8px 0 4px 0;
  font-size: 18px;
  font-weight: 600;
  color: var(--text-primary);
}

.empty-state p {
  margin: 0 0 20px 0;
  font-size: 14px;
}

.btn-primary {
  background: var(--primary-color);
  color: white;
  border: none;
  padding: 10px 20px;
  border-radius: 6px;
  font-weight: 500;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  transition: all 0.2s ease;
}

.btn-primary:hover {
  background: var(--primary-hover);
  transform: translateY(-1px);
}

/* Modal styles */
.modal {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  padding: 20px;
}

.modal-dialog {
  background: var(--bg-white);
  border-radius: 12px;
  width: 100%;
  max-width: 800px;
  max-height: 90vh;
  display: flex;
  flex-direction: column;
  box-shadow: none;
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px;
  border-bottom: 1px solid var(--border-color);
}

.modal-title {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
  color: var(--text-primary);
  display: flex;
  align-items: center;
  gap: 8px;
}

.btn-close {
  background: none;
  border: none;
  font-size: 24px;
  cursor: pointer;
  color: var(--text-secondary);
  padding: 4px;
  border-radius: 4px;
}

.btn-close:hover {
  background: var(--bg-light);
  color: var(--text-primary);
}

.modal-body {
  flex: 1;
  padding: 20px;
  overflow-y: auto;
}

.detailed-metrics {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.chart-section {
  border: 1px solid var(--border-color);
  border-radius: 8px;
  padding: 16px;
}

.chart-section h6 {
  margin: 0 0 12px 0;
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}

.chart-placeholder {
  height: 200px;
  background: var(--bg-light);
  border-radius: 6px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: var(--text-secondary);
  border: 2px dashed var(--border-color);
}

.chart-placeholder i {
  font-size: 32px;
  margin-bottom: 8px;
  color: var(--text-placeholder);
}

.chart-placeholder p {
  margin: 0;
  font-size: 14px;
}

/* Responsive */
@media (max-width: 768px) {
  .component-header {
    padding: 10px 12px;
  }

  .title {
    font-size: 13px;
  }

  .performance-content {
    padding: 12px;
  }

  .metric-card {
    padding: 12px;
  }

  .metric-value .value {
    font-size: 20px;
  }

  .feature-name {
    flex: 0 0 80px;
  }

  .modal-dialog {
    margin: 10px;
    max-height: calc(100vh - 20px);
  }
}
</style>
