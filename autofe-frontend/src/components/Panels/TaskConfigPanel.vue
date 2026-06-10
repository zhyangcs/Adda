<template>
  <div class="task-config-panel">
    <div class="card h-100">
      <div class="card-header">
        <h5 class="card-title mb-0">
          <Settings :size="20" class="me-2" />
          ① ML Analytics Tasks
        </h5>
      </div>
      <div class="card-body">
        <div class="mb-4">
          <label for="taskDescription" class="form-label fw-bold">
            Task Description
          </label>
          <textarea
            id="taskDescription"
            v-model="taskStore.config.description"
            class="form-control"
            rows="4"
            placeholder="Enter your machine learning task description..."
            required
          ></textarea>
          <div class="form-text">
            Describe the problem you want to solve using automated feature engineering.
          </div>
        </div>

        <!-- Comparison methods - only show on End-to-End page -->
        <div class="mb-4" v-if="isEndToEnd">
          <label class="form-label fw-bold">Comparison Methods (Adda always included)</label>
          <div class="comparison-grid">
            <div class="form-check comparison-locked">
              <input class="form-check-input" type="checkbox" id="cmp-panel-Adda" checked disabled />
              <label class="form-check-label" for="cmp-panel-Adda">Adda</label>
            </div>

            <div class="form-check" v-for="method in comparisonOptions" :key="method.value">
              <input
                class="form-check-input"
                type="checkbox"
                :id="`cmp-panel-${method.value}`"
                :value="method.value"
                :checked="taskStore.config.comparisonMethods.includes(method.value)"
                @change="toggleComparisonMethod(method.value)"
              />
              <label class="form-check-label" :for="`cmp-panel-${method.value}`">
                {{ method.label }}
              </label>
            </div>
          </div>
          <div class="form-text">
            Select additional comparison baselines. Adda runs by default.
          </div>
        </div>

        <div class="mb-4">
          <label for="dataset" class="form-label fw-bold">Dataset</label>
          <select
            id="dataset"
            v-model="taskStore.config.dataset"
            class="form-select"
            required
          >
            <option selected disabled value="">Choose Dataset of Task</option>
            <option value="1">Titanic</option>
            <option value="2">Heart</option>
            <option value="3">Bank</option>
            <option value="4">Diabetes</option>
            <option value="5">Bike</option>
            <option value="6">House</option>
          </select>
          <div class="form-text">
            Choose the dataset for feature engineering.
          </div>
        </div>

        <div class="mb-4">
          <label for="llmModel" class="form-label fw-bold">Agent Model</label>
          <select
            id="llmModel"
            v-model="taskStore.config.model"
            class="form-select"
            required
          >
            <option selected disabled value="">Foundation Model Agent</option>
            <option value="1">Openai-gpt4-turbo</option>
            <option value="2" selected>Openai-gpt4o</option>
            <option value="3">Openai-gpt4o-mini</option>
            <option value="4">Deepseek-v3</option>
          </select>
          <div class="form-text">
            Select the language model to power the feature engineering agents.
          </div>
        </div>

        <div class="mb-4">
          <label for="mlModel" class="form-label fw-bold">Downstream ML Model</label>
          <select
            id="mlModel"
            v-model="taskStore.config.mlModel"
            class="form-select"
            required
          >
            <option selected disabled value="">Choose ML model for training</option>
            <option value="RF">Random Forest (RF)</option>
            <option value="XGB">XGBoost (XGB)</option>
            <option value="LightGBM">LightGBM</option>
          </select>
          <div class="form-text">
            Choose the downstream ML model used for training/evaluation.
          </div>
        </div>

        <div class="alert alert-info d-flex align-items-start mt-4" role="alert">
          <Play :size="18" class="me-2 flex-shrink-0" />
          <div class="small text-start">
            Use the control bar: <strong>Next Step</strong> for agent-driven feature generation, or <strong>Start</strong> on the Performance page for the full pipeline. The system validates your configuration before running.
          </div>
        </div>

        <!-- 配置状态 -->
        <div v-if="taskStore.isInitialized" class="mt-4">
          <div class="alert alert-success" role="alert">
            <CheckCircle :size="16" class="me-2" />
            Task configuration validated successfully!
            <div class="small mt-2">
              You can now proceed to the Feature Generation panel to start building features.
            </div>
          </div>
        </div>

        <div v-if="taskStore.error" class="mt-4">
          <div class="alert alert-danger" role="alert">
            <XCircle :size="16" class="me-2" />
            <strong>Error:</strong> {{ taskStore.error }}
          </div>
        </div>

        <!-- 快速操作 -->
        <div class="mt-4 p-3 bg-light rounded">
          <h6 class="text-muted mb-3">Quick Actions</h6>
          <div class="d-flex gap-2 flex-wrap">
            <button
              class="btn btn-outline-secondary btn-sm"
              @click="loadExampleConfig"
            >
              <FileText :size="14" class="me-1" />
              Load Example
            </button>
            <button
              class="btn btn-outline-secondary btn-sm"
              @click="resetConfig"
            >
              <RotateCcw :size="14" class="me-1" />
              Reset Form
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { Settings, CheckCircle, XCircle, FileText, RotateCcw, Play } from 'lucide-vue-next'
import { useTaskStore } from '@/stores/task'

const taskStore = useTaskStore()
const route = useRoute()
const isEndToEnd = computed(() => route.path.includes('performance'))

const comparisonOptions = [
  { value: 'AutoFeat', label: 'AutoFeat' },
  { value: 'MADlib', label: 'MADlib' },
  { value: 'CAAFE', label: 'CAAFE' },
  { value: 'PGML', label: 'PGML' },
  { value: 'SmartFeat', label: 'SmartFeat' }
]

const REQUIRED_COMPARISON_METHOD = 'Adda'
const DISALLOWED_COMPARISON_METHODS = new Set(['Baseline'])

function normalizeComparisonMethods() {
  const list = taskStore.config.comparisonMethods

  for (let i = list.length - 1; i >= 0; i--) {
    const value = list[i]
    if (value && DISALLOWED_COMPARISON_METHODS.has(value)) list.splice(i, 1)
  }

  if (!list.includes(REQUIRED_COMPARISON_METHOD)) {
    list.unshift(REQUIRED_COMPARISON_METHOD)
  }

  const seen = new Set<string>()
  for (let i = list.length - 1; i >= 0; i--) {
    const v = list[i]
    if (!v) {
      list.splice(i, 1)
      continue
    }

    if (seen.has(v)) list.splice(i, 1)
    else seen.add(v)
  }
}

normalizeComparisonMethods()

function toggleComparisonMethod(method: string) {
  if (method === REQUIRED_COMPARISON_METHOD) return
  const list = taskStore.config.comparisonMethods
  const idx = list.indexOf(method)
  if (idx >= 0) {
    list.splice(idx, 1)
  } else {
    list.push(method)
  }

  normalizeComparisonMethods()
}

function loadExampleConfig() {
  taskStore.config.description = `Build machine learning features to predict customer churn for a telecommunications company. The dataset contains customer demographics, usage patterns, and service information. Create features that capture customer behavior, service utilization patterns, and risk indicators for churn prediction.`
  taskStore.config.dataset = '3'
  taskStore.config.model = '2'
  taskStore.config.mlModel = 'RF'
}

function resetConfig() {
  taskStore.config.description = ''
  taskStore.config.dataset = '2'
  taskStore.config.model = '2'
  taskStore.config.mlModel = 'RF'
}
</script>

<style scoped>
.task-config-panel {
  height: 100%;
  overflow-y: auto;
}

.card {
  border: none;
  box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
  border-radius: 8px;
}

.card-header {
  background-color: #f8f9fa;
  border-bottom: 1px solid #dee2e6;
  padding: 1rem 1.5rem;
}

.card-title {
  color: #495057;
  font-weight: 600;
  display: flex;
  align-items: center;
}

.form-label {
  color: #495057;
  font-weight: 600;
  margin-bottom: 0.5rem;
}

.form-control:focus,
.form-select:focus {
  border-color: #007bff;
  box-shadow: 0 0 0 0.2rem rgba(0, 123, 255, 0.25);
}

.btn {
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 500;
  transition: all 0.2s ease-in-out;
}

.btn:hover:not(:disabled) {
  transform: translateY(-1px);
}

.alert {
  border: none;
  border-radius: 6px;
}

.btn-outline-secondary:hover {
  background-color: #6c757d;
  border-color: #6c757d;
}

.bg-light {
  background-color: #f8f9fa !important;
}

.comparison-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.25rem 0.75rem;
}

.comparison-grid .form-check {
  margin-bottom: 0;
}

.comparison-locked {
  opacity: 0.85;
  margin-bottom: 0;
}

/* 动画效果 */
.spinner-border {
  animation: spinner-border 0.75s linear infinite;
}

@keyframes spinner-border {
  to {
    transform: rotate(360deg);
  }
}
</style>
