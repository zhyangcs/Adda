<template>
  <nav class="app-sidebar">
    <!-- 标题 -->
    <div class="navbar-brand mb-3 text-center">
      <h4 class="text-white mb-0">Adda System</h4>
      <small class="text-white-50">ML Analytics Tasks</small>
    </div>

    <!-- 独立组件1：任务配置 -->
    <div class="task-config-component">
      <div class="component-header">
        <h6 class="text-white mb-2">
          <Settings :size="16" class="me-1" />
          任务配置
        </h6>
      </div>

      <div class="component-content px-3">
        <!-- 任务描述 -->
        <div class="mb-3">
          <label class="form-label text-white-50 small">任务描述</label>
          <textarea
            v-model="taskStore.config.description"
            class="form-control form-control-sm"
            rows="3"
            placeholder="输入机器学习任务描述..."
          ></textarea>
        </div>

        <!-- 数据集选择 -->
        <div class="mb-3">
          <label class="form-label text-white-50 small">数据集</label>
          <select
            v-model="taskStore.config.dataset"
            class="form-select form-select-sm"
          >
            <option value="" disabled>选择数据集</option>
            <option value="1">Titanic</option>
            <option value="2">Heart</option>
            <option value="3">Bank</option>
            <option value="4">Diabetes</option>
            <option value="5">Bike</option>
            <option value="6">House</option>
          </select>
        </div>

        <!-- Agent模型选择 -->
        <div class="mb-3">
          <label class="form-label text-white-50 small">Agent模型</label>
          <select
            v-model="taskStore.config.model"
            class="form-select form-select-sm"
          >
            <option value="" disabled>选择模型</option>
            <option value="1">Openai-gpt4-turbo</option>
            <option value="2">Openai-gpt4o</option>
            <option value="3">Openai-gpt4o-mini</option>
            <option value="4">Deepseek-v3</option>
          </select>
        </div>

        <!-- 检查格式按钮 -->
        <button
          class="btn btn-outline-light btn-sm w-100 mb-3"
          @click="handleCheckFormat"
          :disabled="isSubmitting"
        >
          <CheckCircle :size="14" class="me-1" />
          {{ isSubmitting ? '检查中...' : 'Check Format' }}
        </button>
      </div>
    </div>

    <!-- 独立组件2：系统运行模式 -->
    <div class="execution-mode-component">
      <div class="component-header">
        <h6 class="text-white mb-2">
          <Play :size="16" class="me-1" />
          系统运行模式
        </h6>
      </div>

      <!-- 标签页切换 -->
      <div class="tab-navigation px-3">
        <ul class="nav nav-pills nav-fill" role="tablist">
          <li class="nav-item">
            <button
              class="nav-link"
              :class="{ active: workspaceStore.executionMode === 'end-to-end' }"
              @click="workspaceStore.setExecutionMode('end-to-end')"
            >
              端到端
            </button>
          </li>
          <li class="nav-item">
            <button
              class="nav-link"
              :class="{ active: workspaceStore.executionMode === 'step-by-step' }"
              @click="workspaceStore.setExecutionMode('step-by-step')"
            >
              逐步执行
            </button>
          </li>
        </ul>
      </div>

      <!-- 标签页内容区域 -->
      <div class="tab-content px-3">
        <!-- 端到端模式内容 -->
        <div v-if="workspaceStore.executionMode === 'end-to-end'" class="mode-content">
          <div class="control-buttons">
            <button
              class="btn btn-success btn-sm w-100 mb-2"
              @click="handleStart"
              :disabled="!taskStore.canStartTask || taskStore.isLoading"
            >
              <Play :size="16" class="me-1" />
              Start
            </button>

            <button
              class="btn btn-danger btn-sm w-100 mb-2"
              @click="handleStop"
              :disabled="!taskStore.isRunning"
            >
              <Square :size="16" class="me-1" />
              End&Clear
            </button>

            <button
              class="btn btn-primary btn-sm w-100"
              @click="handleDownload"
              :disabled="!featureTreeStore.hasSelection"
            >
              <Download :size="16" class="me-1" />
              Download Model
            </button>
          </div>
        </div>

        <!-- 逐步执行模式内容 -->
        <div v-else class="mode-content">
          <div class="control-buttons">
            <button
              class="btn btn-success btn-sm w-100 mb-2"
              @click="handleNextStep"
              :disabled="!taskStore.canStartTask || taskStore.isLoading"
            >
              <SkipForward :size="16" class="me-1" />
              Next Step
            </button>

            <button
              class="btn btn-info btn-sm w-100 mb-2"
              @click="handleTestPerformance"
              :disabled="!featureTreeStore.hasSelection"
            >
              <BarChart :size="16" class="me-1" />
              Test Performance
            </button>

            <button
              class="btn btn-primary btn-sm w-100 mb-2"
              @click="handleGenerateModel"
              :disabled="!featureTreeStore.hasSelection"
            >
              <Download :size="16" class="me-1" />
              Generate & Download Model
            </button>

            <button
              class="btn btn-outline-light btn-sm w-100"
              @click="handleShowThinking"
            >
              <Brain :size="16" class="me-1" />
              Show Agent Thinking
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- 状态指示器 -->
    <div class="status-indicator w-100 px-3 mt-auto">
      <div class="alert alert-info py-2 px-2 small" role="alert">
        <div class="d-flex align-items-center mb-1">
          <div class="status-dot me-2" :class="statusDotClass"></div>
          <span class="text-white">{{ taskStore.statusText }}</span>
        </div>
        <div v-if="taskStore.isRunning" class="text-white-50 small">
          <div class="spinner-border spinner-border-sm me-1" role="status"></div>
          Processing...
        </div>
      </div>
    </div>
  </nav>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import {
  Play, Square, Download, Settings, CheckCircle, SkipForward,
  BarChart, Brain
} from 'lucide-vue-next'
import { useTaskStore } from '@/stores/task'
import { useFeatureTreeStore } from '@/stores/featureTree'
import { useWorkspaceStore } from '@/stores/workspace'

const taskStore = useTaskStore()
const featureTreeStore = useFeatureTreeStore()
const workspaceStore = useWorkspaceStore()

const isSubmitting = ref(false)

const statusDotClass = computed(() => {
  switch (taskStore.status) {
    case 'idle':
      return 'status-idle'
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

async function handleCheckFormat() {
  isSubmitting.value = true
  try {
    const success = await taskStore.startTask()
    if (success) {
      taskStore.addNotification('Task configuration validated successfully!', 'success')
    }
  } finally {
    isSubmitting.value = false
  }
}

async function handleStart() {
  await taskStore.startTask()
  if (taskStore.isInitialized) {
    await featureTreeStore.loadTreeData()
  }
}

async function handleStop() {
  await taskStore.stopTask()
  await taskStore.clearTask()
  featureTreeStore.clearSelection()
}

async function handleDownload() {
  if (featureTreeStore.hasSelection) {
    const success = await featureTreeStore.generateModel()
    if (success) {
      taskStore.addNotification('Model downloaded successfully', 'success')
    } else {
      taskStore.addNotification('Failed to download model', 'fail')
    }
  }
}

async function handleNextStep() {
  await taskStore.startTask()
  if (taskStore.isInitialized) {
    await featureTreeStore.loadTreeData()
  }
  taskStore.addNotification('Next step generated', 'success')
}

async function handleTestPerformance() {
  if (featureTreeStore.hasSelection) {
    const performance = await featureTreeStore.testPerformance()
    taskStore.addNotification(`Performance: AUC = ${performance.toFixed(4)}`, 'success')
  }
}

async function handleGenerateModel() {
  if (featureTreeStore.hasSelection) {
    const success = await featureTreeStore.generateModel()
    if (success) {
      taskStore.addNotification('Model generated and downloaded successfully', 'success')
    } else {
      taskStore.addNotification('Failed to generate model', 'fail')
    }
  }
}

function handleShowThinking() {
  taskStore.addNotification('Agent thinking details panel opened', 'success')
}
</script>

<style scoped>
.app-sidebar {
  width: 330px;
  min-width: 330px;
  max-width: 330px;
  height: 100vh;
  padding: 1rem 0;
  background-color: #343a40 !important;
  display: flex;
  flex-direction: column;
  overflow-y: auto;
  box-sizing: border-box;
}

/* 独立组件通用样式 */
.task-config-component,
.execution-mode-component {
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
  padding-bottom: 1rem;
  margin-bottom: 1rem;
  width: 100%;
}

.component-header {
  padding: 0 1rem;
  margin-bottom: 1rem;
}

.component-header h6 {
  font-weight: 600;
  margin: 0;
  display: flex;
  align-items: center;
}

.component-content {
  width: 100%;
}

/* 任务配置组件样式 */
.task-config-component {
  flex-shrink: 0;
}

/* 系统运行模式组件样式 */
.execution-mode-component {
  flex-shrink: 0;
}

.tab-navigation {
  margin-bottom: 1rem;
}

.tab-content {
  width: 100%;
  min-height: 220px; /* 固定高度，容纳两种模式的按钮 */
}

.mode-content {
  width: 100%;
  min-height: 180px; /* 确保两种模式的内容区域高度一致 */
}

/* 表单样式 */
.form-control,
.form-select {
  background-color: rgba(255, 255, 255, 0.1);
  border: 1px solid rgba(255, 255, 255, 0.2);
  color: white;
  font-size: 0.875rem;
  width: 100%;
}

.form-control:focus,
.form-select:focus {
  background-color: rgba(255, 255, 255, 0.15);
  border-color: #007bff;
  box-shadow: 0 0 0 0.2rem rgba(0, 123, 255, 0.25);
  color: white;
}

.form-control::placeholder {
  color: rgba(255, 255, 255, 0.6);
}

.form-label {
  color: rgba(255, 255, 255, 0.8);
  font-weight: 600;
  margin-bottom: 0.25rem;
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
.status-indicator {
  position: sticky;
  bottom: 0;
  background-color: rgba(0, 0, 0, 0.1);
  padding: 0.5rem;
  border-top: 1px solid rgba(255, 255, 255, 0.1);
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

.status-completed {
  background-color: #28a745;
}

.status-error {
  background-color: #dc3545;
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
.task-config-component *,
.execution-mode-component * {
  box-sizing: border-box;
}
</style>