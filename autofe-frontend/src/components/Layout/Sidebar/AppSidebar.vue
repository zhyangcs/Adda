<template>
  <aside class="app-sidebar" :class="{ collapsed: isCollapsed }">
    <!-- 折叠按钮 -->
    <button
      class="collapse-toggle"
      @click="toggleCollapse"
      :title="isCollapsed ? 'Expand Sidebar' : 'Collapse Sidebar'"
    >
      <ChevronLeft v-if="!isCollapsed" :size="16" />
      <ChevronRight v-else :size="16" />
    </button>

    <!-- 展开时的内容 -->
    <div v-show="!isCollapsed" class="sidebar-content">
      <!-- 独立组件1：任务配置 -->
      <div class="task-config-component">
        <div class="component-header">
          <h6 class="component-title">
            <Settings :size="16" class="me-1" />
            Configuration
          </h6>
        </div>

        <div class="component-content">
          <!-- 任务描述 -->
          <div class="mb-3">
            <label class="form-label">Task Description</label>
            <textarea
              v-model="taskStore.config.description"
              class="form-control"
              rows="3"
              placeholder="Enter machine learning task description..."
            ></textarea>
          </div>

          <!-- 数据集选择 -->
          <div class="mb-3">
            <label class="form-label">Dataset</label>
            <select
              v-model="taskStore.config.dataset"
              class="form-select"
            >
              <option value="" disabled>Select Dataset</option>
              <option value="1">Titanic</option>
              <option value="2">Heart</option>
              <option value="3">Bank</option>
              <option value="4">Diabetes</option>
              <option value="5">Bike</option>
              <option value="6">House</option>
              <option value="7">Adult</option>
            </select>
          </div>

          <!-- Agent模型选择 -->
          <div class="mb-3">
            <label class="form-label">Agent Model</label>
            <select
              v-model="taskStore.config.model"
              class="form-select form-select-sm"
            >
              <option value="" disabled>Select Model</option>
              <option value="1">Openai-gpt4-turbo</option>
              <option value="2">Openai-gpt4o</option>
              <option value="3">Openai-gpt4o-mini</option>
              <option value="4">Deepseek-v3</option>
            </select>
          </div>

          <!-- 下游ML模型选择 -->
          <div class="mb-3">
            <label class="form-label">Downstream ML Model</label>
            <select
              v-model="taskStore.config.mlModel"
              class="form-select form-select-sm"
            >
              <option value="" disabled>Select ML Model</option>
              <option value="RF">Random Forest (RF)</option>
              <option value="XGB">XGBoost (XGB)</option>
              <option value="LightGBM">LightGBM</option>
            </select>
          </div>

          <!-- Methods -->
          <div class="mb-3">
            <label class="form-label">Methods</label>
            <div class="comparison-grid">
              <div class="form-check comparison-locked">
                <input
                  class="form-check-input"
                  type="checkbox"
                  id="cmp-Adda"
                  checked
                  disabled
                />
                <label class="form-check-label" for="cmp-Adda">Adda</label>
              </div>

              <div class="form-check" v-for="method in comparisonOptions" :key="method.value">
                <input
                  class="form-check-input"
                  type="checkbox"
                  :id="`cmp-${method.value}`"
                  :value="method.value"
                  :checked="isComparisonSelected(method.value)"
                  @change="toggleComparisonMethod(method.value)"
                />
                <label class="form-check-label" :for="`cmp-${method.value}`">
                  {{ method.label }}
                </label>
              </div>
            </div>
          </div>

        </div>
      </div>

      <!-- 状态指示器 -->
      <div class="sidebar-status-indicator w-100 px-3 mt-auto">
        <div class="status-card" role="status" aria-live="polite">
          <div class="status-row">
            <div class="status-dot me-2" :class="statusDotClass"></div>
            <span class="status-text">{{ sidebarStatusText }}</span>
          </div>
        </div>
      </div>
    </div>
  </aside>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { ChevronLeft, ChevronRight, Settings } from 'lucide-vue-next'
import { useTaskStore } from '@/stores/task'
import { useRoute } from 'vue-router'

const taskStore = useTaskStore()
const isCollapsed = ref(false)
const route = useRoute()

const isAgentPage = computed(() => route.path === '/agent-feature-generation')

const comparisonOptions = [
  { value: 'AutoFeat', label: 'AutoFeat' },
  { value: 'MADlib', label: 'MADlib' },
  { value: 'CAAFE', label: 'CAAFE' }
]

const REQUIRED_COMPARISON_METHOD = 'Adda'
const DISALLOWED_COMPARISON_METHODS = new Set(['Baseline', 'PGML'])

function normalizeComparisonMethods() {
  const list = taskStore.config.comparisonMethods

  for (let i = list.length - 1; i >= 0; i--) {
    const value = list[i]
    if (value && DISALLOWED_COMPARISON_METHODS.has(value)) list.splice(i, 1)
  }

  if (!list.includes(REQUIRED_COMPARISON_METHOD)) {
    list.unshift(REQUIRED_COMPARISON_METHOD)
  }

  // de-duplicate (preserve first occurrence)
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

// 折叠功能
function toggleCollapse() {
  isCollapsed.value = !isCollapsed.value
}

const statusDotClass = computed(() => {
  if (isAgentPage.value) {
    switch (taskStore.agentSearchStatus) {
      case 'idle':
        return 'status-ready'
      case 'running':
        return 'status-running'
      case 'paused':
        return 'status-paused'
      case 'stopping':
        return 'status-stopping'
      case 'clear':
        return 'status-idle'
      case 'error':
        return 'status-error'
      default:
        return 'status-idle'
    }
  }

  switch (taskStore.status) {
    case 'idle':
      return 'status-ready'
    case 'running':
    case 'initializing':
      return 'status-running'
    case 'completed':
      return 'status-completed'
    case 'error':
      return 'status-error'
    default:
      return 'status-idle'
  }
})

const sidebarStatusText = computed(() => {
  if (isAgentPage.value) {
    switch (taskStore.agentSearchStatus) {
      case 'idle':
        return 'Ready'
      case 'running':
        return 'Running...'
      case 'paused':
        return 'Paused'
      case 'stopping':
        return 'Stopping...'
      case 'clear':
        return 'Stopped'
      case 'error':
        return 'Error'
      default:
        return 'Ready'
    }
  }
  return taskStore.statusText
})

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

function isComparisonSelected(method: string) {
  return taskStore.config.comparisonMethods.includes(method)
}

</script>

<style scoped>
.app-sidebar {
  width: 340px;
  min-width: 340px;
  max-width: 340px;
  height: 100vh;
  padding-top: 1rem;
  background-color: rgb(245, 245, 245);
  border-right: 1px solid #e2e8f0;
  display: flex;
  flex-direction: column;
  overflow-y: auto;
  position: relative;
  transition: all 0.3s ease;
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

.app-sidebar.collapsed {
  width: 20px;
  min-width: 20px;
  max-width: 20px;
  overflow: visible;
  border: none;
  padding: 0;
  background-color: transparent;
}

/* 确保折叠状态下内容完全隐藏 */
.app-sidebar.collapsed .sidebar-content {
  display: none;
}

/* 确保折叠动画过渡平滑 */
.sidebar-content {
  transition: opacity 0.3s ease;
}

/* 折叠按钮样式 */
.collapse-toggle {
  position: absolute;
  right: -12px;
  top: 1.25rem;
  z-index: 50;
  border-radius: 50%;
  width: 24px;
  height: 24px;
  padding: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background-color: white;
  border: 1px solid #cbd5e1;
  color: #64748b;
  transition: all 0.2s ease;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1), 0 1px 2px rgba(0, 0, 0, 0.06);
  cursor: pointer;
}

.collapse-toggle:hover {
  background-color: #f8fafc;
  box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1), 0 2px 4px rgba(0, 0, 0, 0.06);
}

.task-config-component {
  padding: 1rem;
  margin-bottom: 1rem;
}

.component-title {
  font-size: 1.25rem;
  font-weight: 600;
  color: #0f172a;
  margin-bottom: 0.5rem;
  font-family: 'Inter', ui-sans-serif, system-ui, sans-serif;
}

.component-content {
  padding: 0.75rem;
}

.collapse-toggle:hover {
  background-color: #e9ecef !important;
  border-color: #adb5bd !important;
  color: #495057 !important;
  transform: scale(1.1) !important;
  box-shadow: 0 4px 8px rgba(0, 0, 0, 0.2) !important;
}

.collapse-toggle:focus {
  outline: none !important;
  box-shadow: 0 0 0 0.2rem rgba(0, 123, 255, 0.25) !important;
}

/* 确保折叠按钮在所有情况下都可见 */
:global(.app-sidebar .collapse-toggle) {
  z-index: 1001 !important;
}

.app-sidebar.collapsed .collapse-toggle {
  position: absolute !important;
  left: -12px !important;
  right: auto !important;
  top: 20px !important;
}

/* 侧边栏内容容器 */
.sidebar-content {
  display: flex;
  flex-direction: column;
  height: 100%;
  opacity: 1;
}

/* 独立组件通用样式 */
.task-config-component {
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
  padding-bottom: 1rem;
  margin-bottom: 1rem;
  width: 100%;
}

.component-header {
  /* Shift header content (icon + title) left */
  padding: 0 0.75rem 0 0.25rem;
  margin-bottom: var(--spacing-lg);
}

.component-header h6 {
  font-weight: 600;
  margin: 0;
  display: flex;
  align-items: center;
  /* Ensure larger Settings title */
  font-size: 1.25rem;
  color: #374151;
}

.component-content {
  width: 100%;
}

/* 任务配置组件样式 */
.task-config-component {
  flex-shrink: 0;
}

/* 响应式设计 */
@media (max-width: 768px) {
  .app-sidebar {
    width: 50px !important;
    min-width: 50px !important;
    max-width: 50px !important;
  }

  .app-sidebar.collapsed {
    width: 50px !important;
    min-width: 50px !important;
    max-width: 50px !important;
  }

  .sidebar-content {
    opacity: 0;
    pointer-events: none;
  }
}

/* 状态指示器样式 */
.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  display: inline-block;
}

/* 表单样式 */
.form-control,
.form-select {
  background-color: #ffffff;
  border: 1px solid #d1d5db;
  color: #374151;
  font-size: var(--font-size-base);
  width: 100%;
  padding: 0.5rem 0.75rem;
  border-radius: 6px;
}

.form-control:focus,
.form-select:focus {
  background-color: #ffffff;
  border-color: #3b82f6;
  box-shadow: 0 0 0 0.125rem rgba(59, 130, 246, 0.25);
  color: #374151;
}

.form-control::placeholder {
  color: #9ca3af;
}

.form-label {
  color: #4b5563;
  font-weight: 600;
  margin-bottom: 0.5rem;
  font-size: var(--font-size-base);
}

/* 标签页样式 */
.nav-pills {
  width: 100%;
  margin: 0;
  padding: 0;
}

.nav-pills .nav-item {
  flex: 1;
}

.nav-pills .nav-link {
  background-color: rgba(255, 255, 255, 0.1);
  border: 1px solid rgba(255, 255, 255, 0.2);
  color: rgba(255, 255, 255, 0.8);
  font-size: 0.8rem;
  padding: 0.25rem 0.5rem;
  border-radius: 0.25rem;
  transition: background-color 0.2s ease, color 0.2s ease;
  margin: 0;
  width: 100%;
  text-align: center;
}

.nav-pills .nav-link.active {
  background-color: #007bff;
  border-color: #007bff;
  color: white;
  padding: 0.25rem 0.5rem; /* 确保激活状态的padding一致 */
}

.nav-pills .nav-link:hover:not(.active) {
  background-color: rgba(255, 255, 255, 0.2);
  color: white;
}

/* 按钮容器 */
.control-buttons {
  display: flex;
  flex-direction: column;
  width: 100%;
}

.control-buttons .btn {
  width: 100%;
}

/* 状态指示器 */
.sidebar-status-indicator {
  position: sticky;
  /* 稍微上移一点，避免贴边过紧 */
  bottom: 30px;
  /* 与 Settings/Sidebar 背景保持一致 */
  background-color: rgb(245, 245, 245);
  padding: 0.5rem;
  border-top: none;
  margin-top: auto;
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  display: inline-block;
}

.status-idle {
  background-color: #6c757d;
}

.status-running {
  background-color: #007bff;
  animation: pulse 1.5s ease-in-out infinite alternate;
}

.status-paused {
  background-color: #f59e0b;
}

.status-stopping {
  background-color: #f59e0b;
  animation: pulse 1.1s ease-in-out infinite alternate;
}

.status-completed {
  background-color: #28a745;
}

.status-error {
  background-color: #dc3545;
}

/* 状态卡片：替换 alert-info（避免蓝色背景），更简洁 */
.status-card {
  background: rgb(255, 255, 255);
  border: none;
  border-radius: 10px;
  padding: 0.5rem 0.6rem;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.04);
}

.status-row {
  display: flex;
  align-items: center;
  gap: 0.25rem;
}

.status-text {
  color: #334155;
  font-weight: 600;
  font-size: 0.85rem;
  line-height: 1.1;
}

.status-subtext {
  margin-top: 0.25rem;
  color: #64748b;
  font-size: 0.78rem;
  display: flex;
  align-items: center;
}

.status-ready {
  background-color: #22c55e;
}

@keyframes pulse {
  from {
    opacity: 1;
  }
  to {
    opacity: 0.5;
  }
}

.navbar-brand h4 {
  font-weight: 600;
  letter-spacing: 0.5px;
}

.btn {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0.5rem 1rem;
  font-weight: 500;
  transition: all 0.2s ease-in-out;
  font-size: 0.875rem;
}

.btn:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 4px 8px rgba(0, 0, 0, 0.2);
}

.btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

/* 滚动条样式 */
.app-sidebar::-webkit-scrollbar {
  width: 6px;
}

.app-sidebar::-webkit-scrollbar-track {
  background: rgba(255, 255, 255, 0.1);
}

.app-sidebar::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.3);
  border-radius: 3px;
}

.app-sidebar::-webkit-scrollbar-thumb:hover {
  background: rgba(255, 255, 255, 0.5);
}

/* 确保所有内容都填满宽度 */
.task-config-component * {
  box-sizing: border-box;
}
</style>
