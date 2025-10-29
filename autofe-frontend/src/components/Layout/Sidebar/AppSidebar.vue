<template>
  <aside class="app-sidebar" :class="{ collapsed: isCollapsed }">
    <!-- 折叠按钮 -->
    <button
      class="collapse-toggle btn btn-sm btn-outline-light"
      @click="toggleCollapse"
      :title="isCollapsed ? '展开侧边栏' : '折叠侧边栏'"
    >
      <ChevronLeft v-if="!isCollapsed" :size="16" />
      <ChevronRight v-else :size="16" />
    </button>

    <!-- 展开时的内容 -->
    <div v-if="!isCollapsed" class="sidebar-content">
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
    </div>
  </aside>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { ChevronLeft, ChevronRight, Settings, CheckCircle } from 'lucide-vue-next'
import { useTaskStore } from '@/stores/task'

const taskStore = useTaskStore()
const isSubmitting = ref(false)
const isCollapsed = ref(false)

// 折叠功能
function toggleCollapse() {
  isCollapsed.value = !isCollapsed.value
}

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
    const success = await taskStore.checkFormat()
    if (success) {
      taskStore.addNotification('Task configuration validated successfully!', 'success')
    }
  } finally {
    isSubmitting.value = false
  }
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
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.app-sidebar.collapsed {
  width: 50px !important;
  min-width: 50px !important;
  max-width: 50px !important;
}

/* 折叠按钮样式 */
.collapse-toggle {
  position: absolute;
  top: 12px;
  right: 12px;
  z-index: 10;
  width: 28px;
  height: 28px;
  padding: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 4px;
  opacity: 0.8;
  transition: opacity 0.2s ease;
}

.collapse-toggle:hover {
  opacity: 1;
}

.collapsed .collapse-toggle {
  position: relative;
  top: auto;
  right: auto;
  margin: 8px auto;
}

/* 侧边栏内容容器 */
.sidebar-content {
  display: flex;
  flex-direction: column;
  height: 100%;
  opacity: 1;
  transition: opacity 0.3s ease;
}

.app-sidebar.collapsed .sidebar-content {
  opacity: 0;
  pointer-events: none;
}

/* 独立组件通用样式 */
.task-config-component {
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

  .collapse-toggle {
    position: relative;
    top: auto;
    right: auto;
    margin: 8px auto;
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
.task-config-component * {
  box-sizing: border-box;
}
</style>