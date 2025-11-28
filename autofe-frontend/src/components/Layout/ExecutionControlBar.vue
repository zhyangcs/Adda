<template>
  <div class="execution-control-bar" :class="{ 'is-loading': isNextStepLoading, collapsed: isCollapsed }">
    <template v-if="isCollapsed">
      <button class="collapse-toggle floating-toggle" @click="toggleCollapse(false)" title="Show controls">
        <ChevronRight :size="16" />
      </button>
    </template>
    <template v-else>
      <div class="bar-content">
        <button class="collapse-toggle inline-toggle" @click="toggleCollapse(true)" title="Hide controls">
          <ChevronLeft :size="16" />
        </button>

        <!-- 端到端模式按钮 -->
        <div v-if="isEndToEndPage" class="button-group">
          <button
            class="btn btn-success btn-sm"
            @click="handleStart"
            :disabled="!taskStore.canStartTask || taskStore.isRunning"
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
            :disabled="!taskStore.canDoNextStep || isNextStepLoading"
          >
            <div v-if="isNextStepLoading" class="spinner-border spinner-border-sm me-1" role="status">
              <span class="visually-hidden">Loading...</span>
            </div>
            <SkipForward v-else :size="16" class="me-1" />
            {{ isNextStepLoading ? 'Processing...' : 'Next Step' }}
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
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRoute } from 'vue-router'
import {
  Play, Square, Download, SkipForward, BarChart, Brain, ChevronRight, ChevronLeft
} from 'lucide-vue-next'
import { useTaskStore } from '@/stores/task'
import { useFeatureTreeStore } from '@/stores/featureTree'
import { useWorkspaceStore } from '@/stores/workspace'

const route = useRoute()
const taskStore = useTaskStore()
const featureTreeStore = useFeatureTreeStore()
const workspaceStore = useWorkspaceStore()

// Next step loading状态
const isNextStepLoading = ref(false)
const isCollapsed = ref(false)

const toggleCollapse = (state?: boolean) => {
  if (typeof state === 'boolean') {
    isCollapsed.value = state
  } else {
    isCollapsed.value = !isCollapsed.value
  }
}

// 根据路由判断当前页面模式
const isEndToEndPage = computed(() => route.path === '/end-to-end')
const isStepByStepPage = computed(() => route.path === '/step-by-step')

// 执行按钮事件处理函数
async function handleStart() {
  // 如果是端到端页面，传入配置进行初始化
  const success = await taskStore.autoStep(isEndToEndPage.value)
  if (success) {
    await featureTreeStore.loadTreeData()
  }
}

async function handleStop() {
  await taskStore.stopTask()
  featureTreeStore.clearSelection()
}

async function handleNextStep() {
  try {
    // 设置loading状态
    isNextStepLoading.value = true

    // 真实调用next step API
    console.log('Next Step clicked - calling real API')

    const success = await taskStore.nextStep()
    if (success) {
      taskStore.addNotification('Next step completed successfully', 'success')
      // 成功后重新加载树数据
      await featureTreeStore.loadTreeData()
    } else {
      taskStore.addNotification('Next step failed', 'fail')
    }
  } catch (error) {
    console.error('Next step failed:', error)
    taskStore.addNotification('Next step execution failed', 'fail')
  } finally {
    // 清除loading状态
    isNextStepLoading.value = false
  }
}

async function handleTestPerformance() {
  if (featureTreeStore.selectedNodeIds.length === 0) {
    taskStore.addNotification('Please select at least one feature to test performance', 'info')
    return
  }

  // 发射全局事件，让MainContent组件接收
  window.dispatchEvent(new CustomEvent('test-performance', {
    detail: { features: featureTreeStore.selectedNodeIds }
  }))
}

async function handleGenerateModel() {
  if (featureTreeStore.selectedNodeIds.length === 0) {
    taskStore.addNotification('Please select at least one feature to generate model', 'info')
    return
  }

  await taskStore.generateModel(featureTreeStore.selectedNodeIds)
}

async function handleDownload() {
  if (featureTreeStore.selectedNodeIds.length === 0) {
    taskStore.addNotification('Please select at least one feature to download', 'info')
    return
  }

  await taskStore.downloadModel(featureTreeStore.selectedNodeIds)
}

function handleShowThinking() {
  // 显示Agent思考过程的逻辑
  workspaceStore.toggleAgentThinking()
}
</script>

<style scoped>
.execution-control-bar {
  background: var(--bg-primary);
  border-bottom: 1px solid var(--border-color);
  padding: var(--spacing-md) var(--spacing-xl);
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: var(--control-bar-height);
  position: sticky;
  top: 0;
  z-index: 10;
  box-shadow: none;
  gap: var(--spacing-sm);
}

.execution-control-bar.collapsed {
  padding: 0;
  min-height: 0;
  height: 0;
  border: none;
  background: transparent;
  justify-content: center;
  overflow: visible;
}

.bar-content {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  flex-wrap: wrap;
}

.collapse-toggle {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  border: none;
  background: #fff;
  color: #64748b;
  border: 1px solid #cbd5e1;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all 0.2s ease;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1), 0 1px 2px rgba(0, 0, 0, 0.06);
}

.collapse-toggle:hover {
  background: #f8fafc;
  transform: scale(1.05);
  box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1), 0 2px 4px rgba(0, 0, 0, 0.06);
}

.floating-toggle {
  position: absolute;
  top: 8px;
  left: 12px;
  z-index: 20;
}

.button-group {
  display: flex;
  gap: var(--spacing-sm);
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
  font-size: 16px;
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

/* Loading状态样式 */
.execution-control-bar.is-loading {
  position: relative;
}

.execution-control-bar.is-loading::after {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(255, 255, 255, 0.1);
  pointer-events: none;
}

.execution-control-bar.is-loading .btn:not(:disabled) {
  filter: grayscale(30%);
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
