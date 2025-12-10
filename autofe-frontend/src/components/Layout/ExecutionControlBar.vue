<template>
  <div class="execution-control-bar" :class="{ collapsed: isCollapsed }">
    <div class="control-slot">
      <button
        class="control-pill"
        :class="{ 'is-visible': isCollapsed }"
        @click="toggleCollapse(false)"
        title="Show controls"
        aria-hidden="false"
      >
        Control
      </button>

      <div
        class="bar-card"
        :class="[{ 'is-visible': !isCollapsed }, { 'is-loading': isNextStepLoading }]"
        aria-hidden="false"
      >
        <div class="bar-content">
          <button class="collapse-toggle inline-toggle" @click="toggleCollapse(true)" title="Hide controls">
            <ChevronLeft :size="16" />
          </button>

          <!-- Performance 页面按钮（沿用原 End-to-End 自动流程） -->
          <div v-if="isPerformancePage" class="button-group">
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
          </div>

          <!-- Agent-driven 页面按钮（沿用原 Next Step 接口） -->
          <div v-else-if="isAgentPage" class="button-group">
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
              class="btn btn-outline-secondary btn-sm"
              @click="handleShowThinking"
            >
              <Brain :size="16" class="me-1" />
              Show Agent Thinking
            </button>
          </div>

          <!-- In-DB 页面暂留空 -->
          <div v-else class="button-group">
            <span class="text-muted">Controls will appear here once the in-database flow is ready.</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRoute } from 'vue-router'
import {
  Play, Square, SkipForward, Brain, ChevronLeft
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
const isPerformancePage = computed(() => route.path === '/performance')
const isAgentPage = computed(() => route.path === '/agent-feature-generation')

// 执行按钮事件处理函数
async function handleStart() {
  // Performance 页面使用自动流程
  const success = await taskStore.autoStep(isPerformancePage.value)
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

function handleShowThinking() {
  // 显示Agent思考过程的逻辑
  workspaceStore.toggleAgentThinking()
}
</script>

<style scoped>
.execution-control-bar {
  position: fixed;
  bottom: 0.35rem;
  left: 0;
  right: 0;
  display: flex;
  justify-content: center;
  align-items: flex-end;
  z-index: 200;
  pointer-events: none;
  padding: 0 1rem;
}

.control-slot {
  position: relative;
  width: min(1100px, calc(100% - 3rem));
  min-height: 110px;
}

.bar-card,
.control-pill {
  pointer-events: none;
  opacity: 0;
  transition: opacity 0.28s ease, transform 0.28s ease;
  position: absolute;
  left: 50%;
  bottom: 0;
  transform: translate(-50%, 30px);
}

.bar-card.is-visible,
.control-pill.is-visible {
  pointer-events: auto;
  opacity: 1;
  transform: translate(-50%, 0);
}

.bar-card {
  width: min(1100px, calc(100% - 3rem));
  background: rgba(255, 255, 255, 0.95);
  border: 1px solid #e2e8f0;
  border-radius: 1rem;
  padding: 1rem 1.5rem;
  box-shadow: 0 12px 30px rgba(15, 23, 42, 0.2);
  backdrop-filter: blur(12px);
}

.bar-content {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  flex-wrap: wrap;
  width: 100%;
  justify-content: center;
}

.control-pill {
  min-width: 110px;
  height: 20px;
  border-radius: 999px;
  border: 1px solid #cbd5e1;
  background: rgba(15, 23, 42, 0.8);
  color: white;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  font-weight: 600;
  font-size: 0.7rem;
  cursor: pointer;
  transition: transform 0.2s ease, box-shadow 0.2s ease, background 0.2s ease;
  padding: 0 1.25rem;
  box-shadow: 0 6px 15px rgba(15, 23, 42, 0.25);
}

.control-pill:hover {
  transform: translate(-50%, -10px);
  background: rgba(59, 130, 246, 0.9);
}

.collapse-toggle {
  width: 32px;
  height: 32px;
  border-radius: 999px;
  border: 1px solid #cbd5e1;
  background: white;
  color: #475569;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all 0.2s ease;
  box-shadow: 0 4px 10px rgba(15, 23, 42, 0.15);
}

.collapse-toggle:hover {
  background: #f8fafc;
  transform: translateY(-2px);
}

.inline-toggle {
  margin-right: 0.5rem;
}

.button-group {
  display: flex;
  gap: 0.75rem;
  align-items: center;
  flex-wrap: wrap;
  justify-content: center;
}

.btn {
  transition: all 0.2s ease-in-out;
  font-weight: 500;
  border-radius: 8px;
  padding: 0.6rem 1.4rem;
  display: flex;
  align-items: center;
  white-space: nowrap;
  font-size: 1rem;
}

.btn:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 4px 8px rgba(0, 0, 0, 0.15);
}

.btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
  transform: none;
}

.btn .me-1 {
  margin-right: 6px;
}

@media (max-width: 1200px) {
  .bar-card {
    width: min(960px, calc(100% - 2rem));
  }

  .btn {
    font-size: 0.9rem;
    padding: 0.5rem 1rem;
  }
}

@media (max-width: 768px) {
.bar-card {
    width: calc(100% - 1.5rem);
    padding: 0.75rem 1rem;
  }

  .button-group {
    gap: 0.5rem;
  }

  .btn {
    width: 100%;
    justify-content: center;
  }
}

@media (max-width: 480px) {
  .bar-card {
    width: calc(100% - 1rem);
    border-radius: 0.75rem;
  }

  .button-group {
    flex-direction: column;
    align-items: stretch;
  }
}

.bar-card.is-loading {
  position: relative;
}

.bar-card.is-loading::after {
  content: '';
  position: absolute;
  inset: 0;
  background: rgba(255, 255, 255, 0.35);
  border-radius: inherit;
}

.bar-card.is-loading .btn:not(:disabled) {
  filter: grayscale(30%);
}

/* 移除 Vue Transition 针对类的定义，使用上面的显隐控制 */
</style>
