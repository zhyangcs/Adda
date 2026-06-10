<template>
  <div class="snapshot-page">
    <div class="controls-card">
      <div class="controls-header">
        <!-- Title and subtitle removed for snapshot -->
        <button
          class="run-button"
          :disabled="loading"
          @click="fetchImportanceData"
        >
          <span v-if="loading" class="spinner"></span>
          <span>{{ loading ? 'Running…' : 'Run performance_evaluation' }}</span>
        </button>
      </div>

      <div class="form-row">
        <label class="field">
          <span>Dataset</span>
          <select v-model="dataset" :disabled="loading">
            <option value="heart">Heart</option>
            <option value="diabetes">Diabetes</option>
            <option value="titanic">Titanic</option>
            <option value="bank">Bank</option>
            <option value="bike">Bike</option>
            <option value="house">House</option>
          </select>
        </label>
        <label class="field">
          <span>Agent Model</span>
          <select v-model="agentModel" :disabled="loading">
            <option value="Openai-gpt4o">Openai-gpt4o</option>
            <option value="Openai-gpt4-turbo">Openai-gpt4-turbo</option>
            <option value="Openai-gpt4o-mini">Openai-gpt4o-mini</option>
            <option value="Deepseek-v3">Deepseek-v3</option>
          </select>
        </label>
        <label class="field">
          <span>ML Model</span>
          <select v-model="mlModel" :disabled="loading">
            <option value="RF">Random Forest</option>
            <option value="XGB">XGBoost</option>
            <option value="LightGBM">LightGBM</option>
          </select>
        </label>
      </div>

      <div class="status-row" v-if="errorMessage || successMessage">
        <div v-if="errorMessage" class="status-badge error">{{ errorMessage }}</div>
        <div v-else class="status-badge ok">{{ successMessage }}</div>
      </div>
    </div>

    <div class="panels-grid">
      <div class="panel-card">
        <FeatureImportancePanelLegacy :importance-data="importanceData" :is-snapshot="true" />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import FeatureImportancePanelLegacy from '@/components/EndToEnd/FeatureImportancePanelLegacy.vue'
import { apiService } from '@/services/APIService'
import type { ImportanceData } from '@/types'

const dataset = ref('heart')
const agentModel = ref('Openai-gpt4o')
const mlModel = ref('RF')
const loading = ref(false)
const importanceData = ref<ImportanceData | null>(null)
const errorMessage = ref('')
const successMessage = ref('')

const normalizeImportanceData = (raw: any): ImportanceData => {
  return {
    shap: Array.isArray(raw?.shap) ? raw.shap : [],
    ig: Array.isArray(raw?.ig) ? raw.ig : [],
    rfe: Array.isArray(raw?.rfe) ? raw.rfe : [],
    fi: Array.isArray(raw?.fi) ? raw.fi : [],
    paperMetrics: raw?.paperMetrics
  }
}

const fetchImportanceData = async () => {
  loading.value = true
  errorMessage.value = ''
  successMessage.value = ''

  try {
    const response = await apiService.runAutoPipeline({
      description: 'Feature importance snapshot',
      dataset: dataset.value,
      model: agentModel.value,
      mlModel: mlModel.value,
      comparisonMethods: []
    })

    const payload = (response as any)?.data
    const rawImportance = payload?.importanceData

    if (!rawImportance) {
      importanceData.value = null
      errorMessage.value = 'No importance data returned from API.'
      return
    }

    importanceData.value = normalizeImportanceData(rawImportance)
    successMessage.value = 'Loaded importance data from performance_evaluation.'
  } catch (err: any) {
    const message = err?.message || 'Failed to load importance data.'
    errorMessage.value = message
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.snapshot-page {
  /* background: rgb(0, 255, 0); */
  background: rgb(255, 255, 255);
  min-height: 100vh;
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.controls-card {
  background: rgba(255, 255, 255, 0.92);
  border: 1px solid #b6e3ac;
  border-radius: 16px;
  padding: 16px;
  box-shadow: none;
}

.controls-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.title {
  margin: 0;
  font-size: 24px;
  color: #0f5132;
}

.subtitle {
  margin: 4px 0 0;
  color: #1b4332;
  font-size: 14px;
}

.run-button {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  background: #198754;
  color: white;
  border: none;
  border-radius: 12px;
  padding: 10px 14px;
  font-weight: 700;
  cursor: pointer;
  box-shadow: 0 4px 10px rgba(0, 0, 0, 0.12);
  transition: transform 0.1s ease;
}

.run-button:disabled {
  opacity: 0.7;
  cursor: not-allowed;
}

.run-button:not(:disabled):hover {
  transform: translateY(-1px);
}

.spinner {
  width: 14px;
  height: 14px;
  border: 2px solid rgba(255, 255, 255, 0.6);
  border-top-color: #fff;
  border-radius: 50%;
  display: inline-block;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.form-row {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 12px;
  margin-top: 14px;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 6px;
  font-weight: 600;
  color: #0f5132;
}

.field select,
.field input {
  border: 1px solid #a5d6a7;
  border-radius: 10px;
  padding: 8px 10px;
  font-size: 14px;
  background: #f9fff5;
  color: #0f5132;
}

.status-row {
  margin-top: 12px;
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.status-badge {
  padding: 8px 12px;
  border-radius: 10px;
  font-weight: 700;
  font-size: 14px;
}

.status-badge.error {
  background: #f8d7da;
  color: #842029;
  border: 1px solid #f5c2c7;
}

.status-badge.ok {
  background: #d1e7dd;
  color: #0f5132;
  border: 1px solid #badbcc;
}

.panels-grid {
  display: flex;
  flex-direction: column;
  gap: 16px;
  width: 100%;
}

.panel-card {
  background: transparent;
  border: none;
  box-shadow: none;
  padding: 0;
  width: 100%;
}

</style>
