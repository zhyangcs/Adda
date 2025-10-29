<template>
  <div class="execution-control-bar">
    <!-- 端到端模式按钮 -->
    <div v-if="isEndToEndPage" class="button-group">
      <button
        class="btn btn-success btn-sm"
        @click="handleStart"
        :disabled="!taskStore.canStartTask || taskStore.isLoading"
      >
        <Play :size="16" class="me-1" />
        Start
      </button>

      <button
        class="btn btn-danger btn-sm"
        @click="handleStop"
        :disabled="!taskStore.isRunning"
      >
        <Square :size="16" class="me-1" />
        End&Clear
      </button>

      <button
        class="btn btn-primary btn-sm"
        @click="handleDownload"
        :disabled="!featureTreeStore.hasSelection"
      >
        <Download :size="16" class="me-1" />
        Download Model
      </button>
    </div>

    <!-- 逐步执行模式按钮 -->
    <div v-else class="button-group">
      <button
        class="btn btn-success btn-sm"
        @click="handleNextStep"
        :disabled="!taskStore.canStartTask || taskStore.isLoading"
      >
        <SkipForward :size="16" class="me-1" />
        Next Step
      </button>

      <button
        class="btn btn-info btn-sm"
        @click="handleTestPerformance"
        :disabled="!featureTreeStore.hasSelection"
      >
        <BarChart :size="16" class="me-1" />
        Test Performance
      </button>

      <button
        class="btn btn-primary btn-sm"
        @click="handleGenerateModel"
        :disabled="!featureTreeStore.hasSelection"
      >
        <Download :size="16" class="me-1" />
        Generate & Download Model
      </button>

      <button
        class="btn btn-outline-secondary btn-sm"
        @click="handleShowThinking"
      >
        <Brain :size="16" class="me-1" />
        Show Agent Thinking
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import {
  Play, Square, Download, SkipForward, BarChart, Brain
} from 'lucide-vue-next'
import { useTaskStore } from '@/stores/task'
import { useFeatureTreeStore } from '@/stores/featureTree'

const route = useRoute()
const taskStore = useTaskStore()
const featureTreeStore = useFeatureTreeStore()

// 根据路由判断当前页面模式
const isEndToEndPage = computed(() => route.path === '/end-to-end')
const isStepByStepPage = computed(() => route.path === '/step-by-step')

// 执行按钮事件处理函数
async function handleStart() {
  const success = await taskStore.autoStep()
  if (success) {
    await featureTreeStore.loadTreeData()
  }
}

async function handleStop() {
  await taskStore.stopTask()
  featureTreeStore.clearSelection()
}

async function handleNextStep() {
  const success = await taskStore.autoStep()
  if (success) {
    await featureTreeStore.loadTreeData()
  }
}

async function handleTestPerformance() {
  if (featureTreeStore.selectedFeatures.length === 0) {
    taskStore.addNotification('Please select at least one feature to test performance', 'warning')
    return
  }

  await taskStore.testPerformance(featureTreeStore.selectedFeatures)
}

async function handleGenerateModel() {
  if (featureTreeStore.selectedFeatures.length === 0) {
    taskStore.addNotification('Please select at least one feature to generate model', 'warning')
    return
  }

  await taskStore.generateModel(featureTreeStore.selectedFeatures)
}

async function handleDownload() {
  if (featureTreeStore.selectedFeatures.length === 0) {
    taskStore.addNotification('Please select at least one feature to download', 'warning')
    return
  }

  await taskStore.downloadModel(featureTreeStore.selectedFeatures)
}

function handleShowThinking() {
  // 显示Agent思考过程的逻辑
  taskStore.toggleAgentThinking()
}
</script>

<style scoped>
.execution-control-bar {
  background: #ffffff;
  border-bottom: 1px solid #e5e7eb;
  padding: 12px 20px;
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 60px;
  position: sticky;
  top: 0;
  z-index: 10;
}

.button-group {
  display: flex;
  gap: 8px;
  align-items: center;
  flex-wrap: wrap;
  justify-content: center;
}

/* 确保按钮样式与AppSidebar中保持一致 */
.btn {
  transition: all 0.2s ease-in-out;
  font-weight: 500;
  border-radius: 6px;
  padding: 6px 16px;
  display: flex;
  align-items: center;
  white-space: nowrap;
}

.btn:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
}

.btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
  transform: none;
}

/* 按钮图标样式 */
.btn .me-1 {
  margin-right: 4px;
}

/* 响应式设计 */
@media (max-width: 1200px) {
  .execution-control-bar {
    padding: 10px 16px;
  }

  .button-group {
    gap: 6px;
  }

  .btn {
    padding: 5px 12px;
    font-size: 0.875rem;
  }
}

@media (max-width: 768px) {
  .execution-control-bar {
    padding: 8px 12px;
    min-height: auto;
  }

  .button-group {
    gap: 4px;
    flex-wrap: wrap;
  }

  .btn {
    padding: 4px 8px;
    font-size: 0.8rem;
  }

  .btn .me-1 {
    margin-right: 2px;
  }
}

/* 移动端超小屏幕 */
@media (max-width: 480px) {
  .execution-control-bar {
    padding: 6px 8px;
  }

  .button-group {
    flex-direction: column;
    gap: 4px;
    width: 100%;
  }

  .btn {
    width: 100%;
    justify-content: center;
  }
}
</style>