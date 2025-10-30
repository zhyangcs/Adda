<template>
  <div class="agent-workflow-panel">
    <div class="info-card">
      <div class="info-header">
        <h6 class="info-title">
          <Workflow :size="18" class="me-2" />
          Agent Thinking Process
        </h6>
      </div>
      <div class="info-content">
        <!-- 工作流程图 -->
        <div class="workflow-container mb-4">
          <div class="workflow-header">
            <h6 class="mb-3">Agent Workflow</h6>
            <div class="workflow-controls">
              <button
                class="btn btn-sm btn-primary"
                @click="startWorkflow"
                :disabled="isWorkflowRunning"
              >
                <Play :size="14" class="me-1" />
                {{ isWorkflowRunning ? 'Running...' : 'Start Workflow' }}
              </button>
              <button
                class="btn btn-sm btn-secondary"
                @click="resetWorkflow"
              >
                <RotateCcw :size="14" class="me-1" />
                Reset
              </button>
            </div>
          </div>

          <div class="workflow-canvas">
            <svg
              ref="workflowSvg"
              class="workflow-svg"
              viewBox="0 0 800 300"
            >
              <!-- 连接线 -->
              <g class="connections">
                <path
                  v-for="connection in connections"
                  :key="`${connection.from}-${connection.to}`"
                  :d="getConnectionPath(connection)"
                  :class="['connection', connection.status]"
                  stroke="#666"
                  stroke-width="2"
                  fill="none"
                />
              </g>

              <!-- Agent节点 -->
              <g class="agent-nodes">
                <g
                  v-for="agent in agents"
                  :key="agent.id"
                  :transform="`translate(${agent.position.x}, ${agent.position.y})`"
                  :class="['agent-node', agent.status]"
                  @click="selectAgent(agent)"
                >
                  <!-- 节点背景 -->
                  <circle
                    r="35"
                    :class="['agent-circle', agent.status]"
                  />

                  <!-- 闪烁效果 -->
                  <circle
                    v-if="agent.status === 'running'"
                    r="40"
                    class="pulse-circle"
                  />

                  <!-- 节点图标 -->
                  <text
                    text-anchor="middle"
                    dominant-baseline="middle"
                    class="agent-icon"
                  >
                    {{ getAgentIcon(agent.id) }}
                  </text>

                  <!-- 节点标签 -->
                  <text
                    y="50"
                    text-anchor="middle"
                    class="agent-label"
                  >
                    {{ agent.name }}
                  </text>
                </g>
              </g>
            </svg>
          </div>
        </div>

        <!-- 当前Agent信息面板 -->
        <div class="agent-panel mb-4">
          <h6 class="mb-3">Current Agent Details</h6>
          <div
            v-if="selectedAgent"
            class="agent-details"
          >
            <div class="agent-header">
              <div class="agent-avatar">
                {{ getAgentIcon(selectedAgent.id) }}
              </div>
              <div class="agent-info">
                <h5>{{ selectedAgent.name }}</h5>
                <p class="text-muted mb-0">{{ selectedAgent.description }}</p>
                <div class="agent-status">
                  <span :class="['status-badge', selectedAgent.status]">
                    {{ getStatusText(selectedAgent.status) }}
                  </span>
                </div>
              </div>
            </div>

            <div class="agent-content">
              <div v-if="selectedAgent.status === 'running'">
                <div class="progress mb-3">
                  <div
                    class="progress-bar progress-bar-striped progress-bar-animated"
                    role="progressbar"
                    :style="{ width: (selectedAgent.progress || 0) + '%' }"
                  >
                    {{ selectedAgent.progress || 0 }}%
                  </div>
                </div>
                <p class="mb-0">
                  <strong>当前任务:</strong> {{ selectedAgent.currentTask || '处理中...' }}
                </p>
              </div>

              <div v-else-if="selectedAgent.status === 'completed'">
                <div class="alert alert-success">
                  <CheckCircle :size="16" class="me-2" />
                  Agent 任务完成
                </div>
                <p class="mb-0">{{ selectedAgent.result || '已成功完成处理' }}</p>
              </div>

              <div v-else-if="selectedAgent.status === 'error'">
                <div class="alert alert-danger">
                  <XCircle :size="16" class="me-2" />
                  执行出错
                </div>
                <p class="mb-0 text-danger">{{ selectedAgent.error || '处理过程中发生错误' }}</p>
              </div>

              <div v-else>
                <p class="text-muted mb-0">等待执行...</p>
              </div>
            </div>
          </div>

          <div v-else class="text-center text-muted py-4">
            <Bot :size="48" class="mb-3" />
            <p>点击Agent节点查看详细信息</p>
          </div>
        </div>

        <!-- 工作流历史 -->
        <div class="workflow-history">
          <h6 class="mb-3">执行历史</h6>
          <div
            v-if="workflowHistory.length > 0"
            class="history-list"
          >
            <div
              v-for="step in workflowHistory"
              :key="step.agentId + step.timestamp.getTime()"
              class="history-item"
            >
              <div class="history-agent">
                {{ getAgentName(step.agentId) }}
              </div>
              <div class="history-status">
                <span :class="['status-badge', step.status]">
                  {{ getStatusText(step.status) }}
                </span>
              </div>
              <div class="history-time">
                {{ formatTime(step.timestamp) }}
              </div>
              <div v-if="step.duration" class="history-duration">
                {{ step.duration.toFixed(2) }}s
              </div>
            </div>
          </div>

          <div v-else class="text-center text-muted py-3">
            <Clock :size="24" class="mb-2" />
            <p class="mb-0">暂无执行历史</p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import {
  Workflow,
  Play,
  RotateCcw,
  CheckCircle,
  XCircle,
  Bot,
  Clock
} from 'lucide-vue-next'
import { useTaskStore } from '@/stores/task'

const taskStore = useTaskStore()

// 工作流状态
const workflowSvg = ref<SVGElement>()
const selectedAgent = ref<any>(null)
const isWorkflowRunning = ref(false)

// Agent定义
const agents = ref([
  {
    id: 'analyzer',
    name: '分析Agent',
    description: '分析数据集和任务需求，确定特征工程方向',
    status: 'idle',
    position: { x: 150, y: 100 },
    progress: 0,
    currentTask: '',
    result: '',
    error: ''
  },
  {
    id: 'generator',
    name: '生成Agent',
    description: '基于分析结果生成新的特征候选',
    status: 'idle',
    position: { x: 400, y: 100 },
    progress: 0,
    currentTask: '',
    result: '',
    error: ''
  },
  {
    id: 'evaluator',
    name: '评估Agent',
    description: '评估生成特征的性能和有效性',
    status: 'idle',
    position: { x: 650, y: 100 },
    progress: 0,
    currentTask: '',
    result: '',
    error: ''
  }
])

// 连接线定义
const connections = computed(() => [
  {
    from: 'analyzer',
    to: 'generator',
    status: getConnectionStatus('analyzer', 'generator')
  },
  {
    from: 'generator',
    to: 'evaluator',
    status: getConnectionStatus('generator', 'evaluator')
  }
])

// 工作流历史
const workflowHistory = ref<any[]>([])

// 方法
function getAgentIcon(agentId: string): string {
  const icons = {
    analyzer: '📊',
    generator: '⚙️',
    evaluator: '🎯'
  }
  return icons[agentId as keyof typeof icons] || '🤖'
}

function getAgentName(agentId: string): string {
  const agent = agents.value.find(a => a.id === agentId)
  return agent ? agent.name : agentId
}

function getStatusText(status: string): string {
  const statusMap = {
    idle: '等待中',
    running: '运行中',
    completed: '已完成',
    error: '出错'
  }
  return statusMap[status as keyof typeof statusMap] || status
}

function getConnectionStatus(fromId: string, toId: string): string {
  const fromAgent = agents.value.find(a => a.id === fromId)
  const toAgent = agents.value.find(a => a.id === toId)

  if (fromAgent?.status === 'completed' && toAgent?.status !== 'idle') {
    return 'active'
  } else if (fromAgent?.status === 'completed' && toAgent?.status === 'idle') {
    return 'completed'
  } else if (fromAgent?.status === 'running') {
    return 'active'
  }
  return 'idle'
}

function getConnectionPath(connection: any): string {
  const fromAgent = agents.value.find(a => a.id === connection.from)
  const toAgent = agents.value.find(a => a.id === connection.to)

  if (!fromAgent || !toAgent) return ''

  const fromX = fromAgent.position.x + 35
  const fromY = fromAgent.position.y
  const toX = toAgent.position.x - 35
  const toY = toAgent.position.y

  return `M ${fromX} ${fromY} L ${toX} ${toY}`
}

function selectAgent(agent: any) {
  selectedAgent.value = agent
}

async function startWorkflow() {
  isWorkflowRunning.value = true
  taskStore.addNotification('Agent工作流开始执行', 'info')

  // 模拟工作流执行
  await executeAgent('analyzer', '分析数据集特征', 3000)
  await executeAgent('generator', '生成新特征候选', 4000)
  await executeAgent('evaluator', '评估特征性能', 2000)

  isWorkflowRunning.value = false
  taskStore.addNotification('Agent工作流执行完成', 'success')
}

async function executeAgent(agentId: string, task: string, duration: number) {
  const agent = agents.value.find(a => a.id === agentId)
  if (!agent) return

  // 开始执行
  agent.status = 'running'
  agent.currentTask = task
  agent.progress = 0
  agent.error = ''

  const startTime = Date.now()

  // 模拟进度更新
  const progressInterval = setInterval(() => {
    agent.progress = Math.min(100, agent.progress + 10)
  }, duration / 10)

  // 等待执行完成
  await new Promise(resolve => setTimeout(resolve, duration))

  clearInterval(progressInterval)

  // 完成执行
  agent.status = 'completed'
  agent.progress = 100
  agent.currentTask = ''
  agent.result = `${task} - 成功完成`

  const endTime = Date.now()
  const executionDuration = (endTime - startTime) / 1000

  // 添加到历史记录
  workflowHistory.value.unshift({
    agentId,
    status: 'completed',
    timestamp: new Date(),
    duration: executionDuration
  })

  taskStore.addNotification(`${agent.name} 执行完成`, 'success')
}

function resetWorkflow() {
  agents.value.forEach(agent => {
    agent.status = 'idle'
    agent.progress = 0
    agent.currentTask = ''
    agent.result = ''
    agent.error = ''
  })

  selectedAgent.value = null
  workflowHistory.value = []
  isWorkflowRunning.value = false

  taskStore.addNotification('工作流已重置', 'info')
}

function formatTime(date: Date): string {
  return date.toLocaleTimeString()
}

// 监听Agent状态变化，自动选中正在运行的Agent
watch(() => agents.value.map(a => a.status), () => {
  const runningAgent = agents.value.find(a => a.status === 'running')
  if (runningAgent) {
    selectedAgent.value = runningAgent
  }
})

onMounted(() => {
  // 初始化时选中第一个Agent
  selectedAgent.value = agents.value[0]
})
</script>

<style scoped>
.agent-workflow-panel {
  height: 100%;
  overflow: hidden;
}

.info-card {
  height: 100%;
  background-color: var(--bg-secondary);
  border-radius: 8px;
  border: 1px solid var(--border-color);
  display: flex;
  flex-direction: column;
  box-shadow: var(--shadow-sm);
  /* 确保样式优先级 */
  background-color: #fafafa !important;
  border: 1px solid #e0e0e0 !important;
}

.info-header {
  padding: var(--spacing-md) var(--spacing-lg);
  border-bottom: 1px solid var(--border-color);
  background-color: var(--bg-primary);
  border-radius: 8px 8px 0 0;
  /* 确保样式优先级 */
  background-color: #ffffff !important;
  border-bottom: 1px solid #e0e0e0 !important;
}

.info-title {
  color: var(--text-primary);
  font-weight: 600;
  margin: 0;
  font-size: var(--font-size-md);
  display: flex;
  align-items: center;
}

.info-content {
  flex: 1;
  padding: 1rem;
  overflow-y: auto;
}

.workflow-container {
  background-color: #f8f9fa;
  border-radius: 8px;
  padding: 1rem;
  border: 1px solid #dee2e6;
}

.workflow-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1rem;
}

.workflow-controls {
  display: flex;
  gap: 0.5rem;
}

.workflow-canvas {
  background-color: white;
  border-radius: 6px;
  border: 1px solid #e9ecef;
  overflow: hidden;
}

.workflow-svg {
  width: 100%;
  height: 300px;
}

/* Agent节点样式 */
.agent-node {
  cursor: pointer;
  transition: all 0.3s ease;
}

.agent-circle {
  stroke-width: 3px;
  transition: all 0.3s ease;
}

.agent-circle.idle {
  fill: #e9ecef;
  stroke: #6c757d;
}

.agent-circle.running {
  fill: #cce5ff;
  stroke: #007bff;
}

.agent-circle.completed {
  fill: #d4edda;
  stroke: #28a745;
}

.agent-circle.error {
  fill: #f8d7da;
  stroke: #dc3545;
}

/* 脉冲动画 */
.pulse-circle {
  fill: none;
  stroke: #007bff;
  stroke-width: 2;
  opacity: 0.6;
  animation: pulse 1.5s ease-in-out infinite;
}

@keyframes pulse {
  0% {
    transform: scale(1);
    opacity: 0.6;
  }
  50% {
    transform: scale(1.1);
    opacity: 0.3;
  }
  100% {
    transform: scale(1);
    opacity: 0.6;
  }
}

/* 连接线样式 */
.connection.idle {
  stroke: #6c757d;
  stroke-dasharray: 5, 5;
}

.connection.active {
  stroke: #007bff;
  stroke-width: 3;
  animation: flow-animation 1s ease-in-out infinite;
}

.connection.completed {
  stroke: #28a745;
}

@keyframes flow-animation {
  0% {
    stroke-dasharray: 5, 10;
    stroke-dashoffset: 0;
  }
  100% {
    stroke-dasharray: 5, 10;
    stroke-dashoffset: -15;
  }
}

.agent-icon {
  font-size: 20px;
  user-select: none;
}

.agent-label {
  font-size: 12px;
  font-weight: 600;
  fill: #495057;
  user-select: none;
}

/* Agent面板样式 */
.agent-panel {
  background-color: #f8f9fa;
  border-radius: 8px;
  padding: 1rem;
  border: 1px solid #dee2e6;
}

.agent-details {
  background-color: white;
  border-radius: 6px;
  padding: 1rem;
  border: 1px solid #e9ecef;
}

.agent-header {
  display: flex;
  align-items: center;
  margin-bottom: 1rem;
  padding-bottom: 1rem;
  border-bottom: 1px solid #dee2e6;
}

.agent-avatar {
  width: 48px;
  height: 48px;
  border-radius: 50%;
  background-color: #007bff;
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 20px;
  margin-right: 1rem;
}

.agent-info h5 {
  margin: 0 0 0.5rem 0;
  color: #495057;
}

.agent-info p {
  margin: 0;
  font-size: 0.9rem;
}

.status-badge {
  padding: 0.25rem 0.5rem;
  border-radius: 1rem;
  font-size: 0.75rem;
  font-weight: 600;
  text-transform: uppercase;
}

.status-badge.idle {
  background-color: #e9ecef;
  color: #6c757d;
}

.status-badge.running {
  background-color: #cce5ff;
  color: #004085;
}

.status-badge.completed {
  background-color: #d4edda;
  color: #155724;
}

.status-badge.error {
  background-color: #f8d7da;
  color: #721c24;
}

/* 历史记录样式 */
.workflow-history {
  margin-top: auto;
  max-height: 200px;
  overflow-y: auto;
}

.history-list {
  background-color: white;
  border-radius: 6px;
  border: 1px solid #e9ecef;
}

.history-item {
  display: flex;
  align-items: center;
  padding: 0.5rem 1rem;
  border-bottom: 1px solid #f1f3f4;
}

.history-item:last-child {
  border-bottom: none;
}

.history-agent {
  flex: 1;
  font-weight: 600;
  color: #495057;
}

.history-status {
  margin-right: 1rem;
}

.history-time {
  color: #6c757d;
  font-size: 0.8rem;
  margin-right: 0.5rem;
}

.history-duration {
  color: #007bff;
  font-size: 0.8rem;
  font-weight: 600;
}

.btn {
  display: flex;
  align-items: center;
  font-weight: 500;
  transition: all 0.2s ease-in-out;
}

.btn:hover:not(:disabled) {
  transform: translateY(-1px);
}

.btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

/* 响应式设计 */
@media (max-width: 768px) {
  .workflow-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 1rem;
  }

  .agent-header {
    flex-direction: column;
    text-align: center;
  }

  .agent-avatar {
    margin-right: 0;
    margin-bottom: 0.5rem;
  }

  .history-item {
    flex-direction: column;
    align-items: flex-start;
    gap: 0.25rem;
  }
}
</style>