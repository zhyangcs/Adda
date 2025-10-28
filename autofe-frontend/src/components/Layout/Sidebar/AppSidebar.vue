<template>
  <nav class="app-sidebar navbar navbar-dark bg-dark flex-column align-items-center">
    <div class="navbar-brand mb-4">
      <h4 class="text-white mb-0">Adda System</h4>
    </div>

    <div class="button-container w-100 px-3">
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
        End
      </button>

      <button
        class="btn btn-secondary btn-sm w-100 mb-2"
        @click="handleClear"
      >
        <Trash2 :size="16" class="me-1" />
        Clear
      </button>

      <button
        class="btn btn-primary btn-sm w-100 mb-3"
        @click="handleDownload"
        :disabled="!featureTreeStore.hasSelection"
      >
        <Download :size="16" class="me-1" />
        Download Model
      </button>
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
import { computed } from 'vue'
import { Play, Square, Trash2, Download } from 'lucide-vue-next'
import { useTaskStore } from '@/stores/task'
import { useFeatureTreeStore } from '@/stores/featureTree'

const taskStore = useTaskStore()
const featureTreeStore = useFeatureTreeStore()

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

async function handleStart() {
  await taskStore.startTask()
  if (taskStore.isInitialized) {
    await featureTreeStore.loadTreeData()
  }
}

async function handleStop() {
  await taskStore.stopTask()
}

async function handleClear() {
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
</script>

<style scoped>
.app-sidebar {
  width: 330px;
  padding: 1rem 0;
  background-color: #343a40 !important;
}

.button-container {
  display: flex;
  flex-direction: column;
}

.status-indicator {
  position: sticky;
  bottom: 0;
  background-color: rgba(0, 0, 0, 0.1);
  padding: 0.5rem;
  border-top: 1px solid rgba(255, 255, 255, 0.1);
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
}

.btn:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 4px 8px rgba(0, 0, 0, 0.2);
}

.btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
</style>