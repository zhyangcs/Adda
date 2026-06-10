<template>
  <div class="performance-snapshot-page">
    <header class="page-header">
      <div class="title">
        <div class="title-row">
          <i class="bi bi-camera"></i>
          <h1>Performance Snapshot</h1>
        </div>
        <p class="subtitle">
          This page fetches results from <span class="mono">http://localhost:5000/performance-evaluation/</span>.
        </p>
      </div>
    </header>

    <section class="controls card">
      <div class="controls-header">
        <div class="controls-title">
          <i class="bi bi-sliders"></i>
          Controls
        </div>
        <div class="controls-actions">
          <button class="btn btn-primary" :disabled="isLoading" @click="runEvaluation">
            <i class="bi" :class="isLoading ? 'bi-arrow-repeat spinning' : 'bi-play-fill'"></i>
            {{ isLoading ? 'Running...' : 'Run Evaluation' }}
          </button>
        </div>
      </div>

      <div class="controls-grid">
        <div class="field">
          <label>Dataset</label>
          <select v-model="selectedDataset" :disabled="isLoading">
            <option v-for="d in datasets" :key="d.value" :value="d.value">
              {{ d.label }}
            </option>
          </select>
        </div>

        <div class="field">
          <label>Downstream ML model</label>
          <select v-model="mlModelType" :disabled="isLoading">
            <option value="RF">Random Forest (RF)</option>
            <option value="XGB">XGBoost (XGB)</option>
            <option value="LightGBM">LightGBM</option>
          </select>
        </div>

        <div class="field wide">
          <label>Comparison methods (Adda is always included)</label>
          <div class="method-list">
            <label class="method-item locked">
              <input type="checkbox" checked disabled />
              <span class="method-name">Adda</span>
              <span class="pill">required</span>
            </label>

            <label
              v-for="m in availableComparisonMethods"
              :key="m"
              class="method-item"
            >
              <input
                type="checkbox"
                :value="m"
                v-model="selectedMethods"
                :disabled="isLoading"
              />
              <span class="method-name">{{ m }}</span>
            </label>
          </div>
        </div>
      </div>

      <div v-if="errorMessage" class="error">
        <i class="bi bi-exclamation-triangle"></i>
        <div class="error-text">{{ errorMessage }}</div>
      </div>
    </section>

    <section class="charts-grid">
      <div class="chart-card">
        <PerformanceSnapshotPerformanceComparisonChart :performance-data="filteredPerformanceData" />
      </div>
      <div class="chart-card">
        <PerformanceSnapshotPerformanceComparisonChartHorizontal :performance-data="filteredPerformanceData" />
      </div>
      <div class="chart-card">
        <PerformanceSnapshotTimeComparisonChart :time-data="filteredTimeData" />
      </div>
      <div class="chart-card">
        <PerformanceSnapshotTimeComparisonChartVertical :time-data="filteredTimeData" />
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import type { PerformanceData, TimeData } from '@/types'
import PerformanceSnapshotPerformanceComparisonChart from './PerformanceSnapshotPerformanceComparisonChart.vue'
import PerformanceSnapshotPerformanceComparisonChartHorizontal from './PerformanceSnapshotPerformanceComparisonChartHorizontal.vue'
import PerformanceSnapshotTimeComparisonChart from './PerformanceSnapshotTimeComparisonChart.vue'
import PerformanceSnapshotTimeComparisonChartVertical from './PerformanceSnapshotTimeComparisonChartVertical.vue'

type PerformanceEvaluationApiResponse = {
  status?: 'success' | 'fail' | string
  message?: string
  data?: {
    performanceData?: {
      methods?: string[]
      auc?: number[]
      f1?: number[]
      accuracy?: number[]
      precision?: number[]
      recall?: number[]
    }
    timeData?: {
      methods?: string[]
      totalTime?: number[]
      trainingTime?: number[]
      featureGenerationTime?: number[]
    }
    [key: string]: any
  }
  [key: string]: any
}

const API_URL = 'http://localhost:5000/performance-evaluation/'

const datasets = [
  { label: 'Heart', value: 'heart' },
  { label: 'Titanic', value: 'titanic' },
  { label: 'Bank', value: 'bank' },
  { label: 'Diabetes', value: 'diabetes' },
  { label: 'Bike', value: 'bike' },
  { label: 'House', value: 'house' }
]

const availableComparisonMethods = ['CAAFE', 'MADlib', 'AutoFeat'] as const

const selectedDataset = ref<string>('heart')
const mlModelType = ref<'RF' | 'XGB' | 'LightGBM'>('RF')
const selectedMethods = ref<string[]>(['CAAFE', 'MADlib'])

const isLoading = ref(false)
const errorMessage = ref<string | null>(null)
const apiResponse = ref<PerformanceEvaluationApiResponse | null>(null)

const includedMethods = computed(() => {
  const set = new Set<string>(['Adda'])
  for (const m of selectedMethods.value) set.add(m)
  return set
})

const normalizeNumberArray = (arr: any[] | undefined): number[] => {
  if (!Array.isArray(arr)) return []
  return arr.map(v => (typeof v === 'number' ? v : Number(v) || 0))
}

const rawPerformanceData = computed<PerformanceData | null>(() => {
  const d = apiResponse.value?.data?.performanceData
  if (!d) return null
  return {
    methods: Array.isArray(d.methods) ? d.methods : [],
    auc: normalizeNumberArray(d.auc),
    f1: normalizeNumberArray(d.f1),
    accuracy: normalizeNumberArray(d.accuracy),
    precision: normalizeNumberArray(d.precision),
    recall: normalizeNumberArray(d.recall)
  }
})

const rawTimeData = computed<TimeData | null>(() => {
  const d = apiResponse.value?.data?.timeData
  if (!d) return null
  return {
    methods: Array.isArray(d.methods) ? d.methods : [],
    totalTime: normalizeNumberArray(d.totalTime),
    trainingTime: normalizeNumberArray(d.trainingTime),
    featureGenerationTime: normalizeNumberArray(d.featureGenerationTime)
  }
})

function filterByMethods<T extends { methods: string[] }>(
  data: T | null,
  getterMap: Record<string, (idx: number) => any>
): T | null {
  if (!data) return null

  const methods: string[] = []
  const indices: number[] = []
  data.methods.forEach((m, idx) => {
    if (includedMethods.value.has(m)) {
      methods.push(m)
      indices.push(idx)
    }
  })

  const out: any = { ...data, methods }
  for (const [key, getter] of Object.entries(getterMap)) {
    out[key] = indices.map(i => getter(i))
  }

  return out as T
}

const filteredPerformanceData = computed<PerformanceData | null>(() => {
  const d = rawPerformanceData.value
  if (!d) return null
  return filterByMethods<PerformanceData>(d, {
    auc: (i) => d.auc?.[i] ?? 0,
    f1: (i) => d.f1?.[i] ?? 0
  })
})

const filteredTimeData = computed<TimeData | null>(() => {
  const d = rawTimeData.value
  if (!d) return null
  return filterByMethods<TimeData>(d, {
    totalTime: (i) => d.totalTime?.[i] ?? 0,
    trainingTime: (i) => d.trainingTime?.[i] ?? 0,
    featureGenerationTime: (i) => d.featureGenerationTime?.[i] ?? 0
  })
})

const runEvaluation = async () => {
  errorMessage.value = null
  isLoading.value = true

  try {
    const payloadMethods = ['Adda', ...selectedMethods.value.filter(m => m !== 'Adda')]
    const formData = new FormData()
    formData.append('dataset', selectedDataset.value)
    formData.append('ml_model_type', mlModelType.value)
    formData.append('comparison_methods', JSON.stringify(payloadMethods))
    formData.append('use_performance_test', 'true')
    formData.append('paper_top_k', '7')

    const res = await fetch(API_URL, { method: 'POST', body: formData })
    if (!res.ok) throw new Error(`HTTP ${res.status}`)

    const json = (await res.json()) as PerformanceEvaluationApiResponse
    if (json?.status !== 'success') {
      // Do not surface backend messages directly (they may not be English-only).
      throw new Error('Backend returned a failure status')
    }

    apiResponse.value = json
  } catch (e) {
    console.error('[performance-snapshot] performance-evaluation failed', e)
    const msg = e instanceof Error ? e.message : String(e)

    if (msg.includes('Failed to fetch') || msg.includes('NetworkError')) {
      errorMessage.value = 'Cannot reach the backend at http://localhost:5000. Please make sure it is running.'
    } else {
      errorMessage.value =
        'Performance evaluation failed. Please ensure feature search has been run for this dataset and try again.'
    }
  } finally {
    isLoading.value = false
  }
}

onMounted(() => {
  runEvaluation()
})
</script>

<style scoped>
.performance-snapshot-page {
  min-height: 100vh;
  padding: 18px;
  background: #f8fafc;
  color: #0f172a;
}

.page-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 14px;
}

.title-row {
  display: flex;
  align-items: center;
  gap: 10px;
}

.title-row i {
  font-size: 22px;
  color: #2563eb;
}

.title-row h1 {
  margin: 0;
  font-size: 22px;
  font-weight: 800;
  letter-spacing: -0.01em;
}

.subtitle {
  margin: 6px 0 0 0;
  font-size: 13px;
  color: #64748b;
}

.mono {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace;
}

.card {
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  box-shadow: none;
}

.controls {
  padding: 12px 14px;
  margin-bottom: 14px;
}

.controls-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding-bottom: 10px;
  border-bottom: 1px solid #eef2f7;
}

.controls-title {
  display: flex;
  align-items: center;
  gap: 10px;
  font-weight: 800;
  color: #0f172a;
  font-size: 16px;
}

.controls-title i {
  color: #2563eb;
}

.controls-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}

.controls-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
  padding-top: 12px;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.field.wide {
  grid-column: 1 / -1;
}

.field label {
  font-size: 12px;
  color: #475569;
  font-weight: 700;
}

select {
  height: 38px;
  border-radius: 10px;
  border: 1px solid #e2e8f0;
  background: #fff;
  padding: 0 12px;
  font-size: 14px;
  color: #0f172a;
  outline: none;
}

select:focus {
  border-color: #60a5fa;
  box-shadow: 0 0 0 3px rgba(96, 165, 250, 0.25);
}

.method-list {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
}

.method-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 10px;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  background: #fff;
  user-select: none;
}

.method-item.locked {
  background: #f8fafc;
}

.method-name {
  font-size: 14px;
  font-weight: 700;
  color: #0f172a;
}

.pill {
  margin-left: auto;
  font-size: 11px;
  font-weight: 700;
  padding: 2px 8px;
  border-radius: 999px;
  border: 1px solid rgba(37, 99, 235, 0.25);
  background: rgba(37, 99, 235, 0.08);
  color: #2563eb;
}

.btn {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  border-radius: 10px;
  padding: 10px 14px;
  font-size: 14px;
  font-weight: 700;
  border: 1px solid transparent;
  cursor: pointer;
}

.btn:disabled {
  opacity: 0.65;
  cursor: not-allowed;
}

.btn-primary {
  background: #2563eb;
  border-color: #2563eb;
  color: #fff;
}

.btn-primary:hover:not(:disabled) {
  background: #1d4ed8;
  border-color: #1d4ed8;
}

.spinning {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.error {
  margin-top: 12px;
  display: flex;
  gap: 10px;
  align-items: flex-start;
  padding: 10px 12px;
  border: 1px solid rgba(220, 38, 38, 0.3);
  background: rgba(220, 38, 38, 0.05);
  border-radius: 12px;
  color: #b91c1c;
}

.error i {
  margin-top: 2px;
}

.error-text {
  font-size: 13px;
  font-weight: 600;
  line-height: 1.3;
}

.charts-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 14px;
  align-items: stretch;
}

.chart-card {
  min-height: 560px;
  border-radius: 12px;
  overflow: hidden;
  background: #fff;
  border: 1px solid #e2e8f0;
}

@media (max-width: 1100px) {
  .method-list {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (min-width: 1200px) {
  .charts-grid {
    grid-template-columns: 1fr 1fr;
  }
}

@media (max-width: 640px) {
  .controls-grid {
    grid-template-columns: 1fr;
  }

  .method-list {
    grid-template-columns: 1fr;
  }
}
</style>

