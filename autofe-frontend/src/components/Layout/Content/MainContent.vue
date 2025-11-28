<template>
  <div
    class="main-content"
    :class="{ 'splitter-collapsed': rightPanelCollapsed }"
    :data-display-mode="displayMode"
  >
    <!-- 使用Splitpanes实现左右分区布局 -->
    <splitpanes class="default-theme" @resize="handleResize" :push-other-panes="false">
      <!-- 左侧面板：Agent流程图（上方） + Node Information（下方） -->
      <pane :size="leftPaneSize" min="15" max="70">
        <div class="left-panel">
          <!-- 上方：Agent协作流程图 -->
          <div class="agent-flow-section">
            <div class="info-card">
              <div class="info-header">
                <h6 class="info-title">
                  <Users :size="18" class="me-2" />
                  Agent Thinking Process
                  <button
                    class="btn btn-sm btn-info ms-2"
                    @click="testAgentStatus"
                    style="font-size: 0.75rem; padding: 0.25rem 0.5rem;"
                  >
                    Test Queue
                  </button>
                  <button
                    class="btn btn-sm btn-warning ms-1"
                    @click="testWebSocketMessage"
                    style="font-size: 0.75rem; padding: 0.25rem 0.5rem;"
                  >
                    Test WS
                  </button>
                </h6>
              </div>
              <div class="info-content agent-process-content">
                <div class="agent-flow-diagram">
                  <!-- 环形布局的Agent协作图 -->
                  <div class="flow-container">
                    <!-- Agent图标正方形布局 -->
                    <div class="agents-container">
                      <!-- System Agent (左上角) -->
                      <div
                        class="agent-node system-agent"
                        :class="{ active: activeAgent === 'system', working: workingAgents.includes('system') }"
                        @click="setActiveAgent('system')"
                      >
                        <div class="agent-icon">
                          <Monitor :size="32" />
                        </div>
                        <div class="agent-label">System</div>
                        <div v-if="workingAgents.includes('system')" class="working-indicator"></div>

                        <!-- System Agent思考气泡 -->
                        <div
                          v-if="getVisibleThinking('system')"
                          class="thinking-bubble left-bubble"
                          :class="{ 'bubble-disappearing': isBubbleDisappearing('system') }"
                        >
                          <pre>{{ getCurrentThinkingMessage('system') }}</pre>
                        </div>
                      </div>

                      <!-- Main Agent (右上角) -->
                      <div
                        class="agent-node main-agent"
                        :class="{ active: activeAgent === 'main', working: workingAgents.includes('main') }"
                        @click="setActiveAgent('main')"
                      >
                        <div class="agent-icon">
                          <img src="/demo_main.png" alt="Main Agent" class="agent-image" />
                        </div>
                        <div class="agent-label">Main Agent</div>
                        <div v-if="workingAgents.includes('main')" class="working-indicator"></div>

                        <!-- Main Agent思考气泡 -->
                        <div
                          v-if="getVisibleThinking('main')"
                          class="thinking-bubble right-bubble"
                          :class="{ 'bubble-disappearing': isBubbleDisappearing('main') }"
                        >
                          <pre>{{ getCurrentThinkingMessage('main') }}</pre>
                        </div>
                      </div>

                      <!-- Optimization Agent (右下角) -->
                      <div
                        class="agent-node opt-agent"
                        :class="{ active: activeAgent === 'optimization', working: workingAgents.includes('optimization') }"
                        @click="setActiveAgent('optimization')"
                      >
                        <div class="agent-icon">
                          <img src="/demo_opt.png" alt="Optimization Agent" class="agent-image" />
                        </div>
                        <div class="agent-label">Opt Agent</div>
                        <div v-if="workingAgents.includes('optimization')" class="working-indicator"></div>

                        <!-- Optimization Agent思考气泡 -->
                        <div
                          v-if="getVisibleThinking('optimization')"
                          class="thinking-bubble right-bubble"
                          :class="{ 'bubble-disappearing': isBubbleDisappearing('optimization') }"
                        >
                          <pre>{{ getCurrentThinkingMessage('optimization') }}</pre>
                        </div>
                      </div>

                      <!-- Node Validation Process (左下角) -->
                      <div
                        class="agent-node validation-agent"
                        :class="{ active: activeAgent === 'validation', working: workingAgents.includes('validation') }"
                        @click="setActiveAgent('validation')"
                      >
                        <div class="agent-icon">
                          <Cog :size="32" />
                        </div>
                        <div class="agent-label">Node Validation</div>
                        <div v-if="workingAgents.includes('validation')" class="working-indicator"></div>

                        <!-- Node Validation Agent思考气泡 -->
                        <div
                          v-if="getVisibleThinking('validation')"
                          class="thinking-bubble left-bubble"
                          :class="{ 'bubble-disappearing': isBubbleDisappearing('validation') }"
                        >
                          <pre>{{ getCurrentThinkingMessage('validation') }}</pre>
                        </div>
                      </div>

                      <!-- CSS箭头 - 相对中心定位，在同一容器内 -->
                      <div class="arrow-horizontal top-arrow" :class="{ active: connectionActive }"></div>
                      <div class="arrow-vertical right-arrow" :class="{ active: connectionActiveReverse }"></div>
                      <div class="arrow-horizontal bottom-arrow" :class="{ active: connectionActiveValidation }"></div>
                      <div class="arrow-vertical left-arrow" :class="{ active: connectionActiveSystem }"></div>
                    </div>
                  </div>
                </div>
                <div class="agent-chat-panel">
                  <div class="chat-panel-header">
                    <div class="chat-panel-icon">
                      <Bot :size="18" />
                    </div>
                    <div class="chat-panel-title">
                      <span>Live Agent Feed</span>
                      <small>Streaming thinking updates</small>
                    </div>
                  </div>
                  <div class="chat-panel-body" ref="chatListRef">
                    <div v-if="!chatMessages.length" class="chat-empty-state">
                      Agent thinking updates will appear here in real time.
                    </div>
                    <div v-else>
                      <div
                        v-for="message in chatMessages"
                        :key="message.id"
                        class="chat-message"
                        :class="`agent-${message.agent}`"
                      >
                        <div class="chat-avatar" :class="`agent-${message.agent}`">
                          {{ agentDisplayConfig[message.agent].initial }}
                        </div>
                        <div class="chat-bubble">
                          <div class="chat-meta">
                            <span class="chat-author">{{ agentDisplayConfig[message.agent].label }}</span>
                            <span class="chat-time">{{ formatChatTime(message.timestamp) }}</span>
                          </div>
                          <p class="chat-text">{{ message.content }}</p>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <!-- 下方：左右分列的Node Information和Feature Generation -->
          <div class="lower-section">
            <!-- 左边：Node Information -->
            <div class="node-info-section">
              <div class="info-card">
                <div class="info-header">
                  <h6 class="info-title">Node Information</h6>
                </div>
                <div class="info-content">
                  <div v-if="featureTreeStore.selectedNode" class="node-details">
                    <div class="node-detail">
                      <span class="detail-label">Node ID:</span>
                      <span class="detail-value">{{ featureTreeStore.selectedNode.node_id }}</span>
                    </div>
                    <div class="node-detail">
                      <span class="detail-label">Feature Name:</span>
                      <span class="detail-value">{{ featureTreeStore.selectedNode.feature_name }}</span>
                    </div>
                    <div class="node-detail">
                      <span class="detail-label">Task Code:</span>
                      <span class="detail-value">{{ featureTreeStore.selectedNode.task_code }}</span>
                    </div>
                    <div class="node-detail">
                      <span class="detail-label">Operation:</span>
                      <span class="detail-value">{{ featureTreeStore.selectedNode.op_type }}</span>
                    </div>
                    <div class="node-detail">
                      <span class="detail-label">Description:</span>
                      <span class="detail-value">{{ featureTreeStore.selectedNode.operation_desc }}</span>
                    </div>
                    <div class="node-detail">
                      <span class="detail-label">Score:</span>
                      <span class="detail-value">{{ featureTreeStore.selectedNode.score?.toFixed(4) }}</span>
                    </div>
                  </div>
                  <div v-else class="no-node-info">
                    Hover over a node to see details.
                  </div>
                </div>
              </div>
            </div>

            <!-- 右边：Feature Generation -->
            <div class="feature-tree-section">
              <FeatureTreePanel />
            </div>
          </div>
        </div>
      </pane>


      <!-- 右侧面板：SQL Code组件（上方） + Feature Performance组件（下方） -->
      <pane :size="rightPaneSize" min="20" max="60" v-if="!rightPanelCollapsed">
        <div class="right-panel-content">
          <!-- 上方：SQL Code组件 -->
          <div class="sql-code-section">
            <SQLCode :sql-code="sqlCode" />
          </div>

  
          <!-- 下方：Feature Performance组件 -->
          <div class="feature-performance-section">
            <FeaturePerformance
              :performance-data="performanceData"
              :time-data="timeData"
              :shap-data="shapData"
              :is-loading="isLoadingPerformance"
              @generate-features="handleGenerateFeatures"
              @refresh-data="handleRefreshData"
            />
          </div>
        </div>
      </pane>

      <!-- 折叠按钮（当右侧面板隐藏时显示） -->
      <div v-if="rightPanelCollapsed" class="expand-button-container" @click="toggleRightPanel">
        <div class="expand-button">
          <span class="expand-arrow">‹</span>
          <span class="expand-tooltip">Expand Panel (Ctrl+→)</span>
        </div>
      </div>
    </splitpanes>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, nextTick, watch } from 'vue'
import { storeToRefs } from 'pinia'
import { Users, Cog, Monitor, Bot } from 'lucide-vue-next'
import { useTaskStore } from '@/stores/task'
import { useFeatureTreeStore } from '@/stores/featureTree'
import { useAgentStore } from '@/stores/agent'
import type { AgentType, AgentState } from '@/types/websocket'
import SQLCode from '@/components/Features/SQLCode.vue'
import FeaturePerformance from '@/components/Features/FeaturePerformance.vue'
import FeatureTreePanel from '@/components/Features/FeatureTreePanel.vue'

const taskStore = useTaskStore()
const featureTreeStore = useFeatureTreeStore()
const agentStore = useAgentStore()
const { currentAgentThinking, allAgentStates } = storeToRefs(agentStore)

type AgentKey = 'system' | 'main' | 'optimization' | 'validation'
type DisplayMode = 'paper'

const agentDisplayConfig: Record<AgentKey, { label: string; initial: string }> = {
  system: { label: 'System', initial: 'S' },
  main: { label: 'Main Agent', initial: 'M' },
  optimization: { label: 'Opt Agent', initial: 'O' },
  validation: { label: 'Node Validation', initial: 'NV' }
}

const activeAgent = ref<AgentKey>('main')
const workingAgents = ref<AgentKey[]>([])
const connectionActive = ref(false)
const connectionActiveReverse = ref(false)
const connectionActiveValidation = ref(false)
const connectionActiveSystem = ref(false)
const displayMode = ref<DisplayMode>('paper')

// 右侧面板数据
const sqlCode = ref('')
const performanceData = ref<any>(null)
const timeData = ref<any>(null)
const shapData = ref<any>(null)
const isLoadingPerformance = ref(false)

// Splitpanes 相关状态
const leftPaneSize = ref(75) // 左侧面板默认占75%
const rightPaneSize = ref(25) // 右侧面板默认占25%（留空）
const rightPanelCollapsed = ref(false) // 右侧面板折叠状态

// 处理分隔条拖动
function handleResize(event: any) {
  console.log('Resize event:', event)
  // splitpanes 的事件参数可能是单个对象或数组
  if (Array.isArray(event)) {
    const [leftPane] = event
    leftPaneSize.value = leftPane.size
    rightPaneSize.value = 100 - leftPane.size
    localStorage.setItem('main-content-split-ratio', leftPane.size.toString())
  } else if (event && event[0]) {
    // 如果event是类数组对象
    const leftPane = event[0]
    leftPaneSize.value = leftPane.size
    rightPaneSize.value = 100 - leftPane.size
    localStorage.setItem('main-content-split-ratio', leftPane.size.toString())
  } else if (event && event.size !== undefined) {
    // 如果event直接包含size信息
    leftPaneSize.value = event.size
    rightPaneSize.value = 100 - event.size
    localStorage.setItem('main-content-split-ratio', event.size.toString())
  }
}


// 切换右侧面板折叠状态
function toggleRightPanel() {
  console.log('toggleRightPanel called, current collapsed state:', rightPanelCollapsed.value)
  rightPanelCollapsed.value = !rightPanelCollapsed.value

  if (rightPanelCollapsed.value) {
    // 折叠右侧面板，左侧占满
    console.log('Collapsing right panel')
    leftPaneSize.value = 100
    rightPaneSize.value = 0
  } else {
    // 展开右侧面板，恢复之前比例
    console.log('Expanding right panel')
    const savedRatio = localStorage.getItem('main-content-split-ratio')
    if (savedRatio) {
      leftPaneSize.value = parseFloat(savedRatio)
      rightPaneSize.value = 100 - leftPaneSize.value
    } else {
      leftPaneSize.value = 75
      rightPaneSize.value = 25
    }
  }

  // 保存折叠状态
  localStorage.setItem('right-panel-collapsed', rightPanelCollapsed.value.toString())
  console.log('New sizes - left:', leftPaneSize.value, 'right:', rightPaneSize.value)
}

// Agent interaction
function setActiveAgent(agent: AgentKey) {
  activeAgent.value = agent
  taskStore.addNotification(`Selected ${agent} agent`, 'info')
}

// WebSocket相关
const currentThinkingText = computed(() => {
  // 映射activeAgent到agent store中的agent类型
  const agentTypeMap: Record<string, AgentType> = {
    'system': 'system',
    'main': 'mainagent',
    'optimization': 'optimizationagent',
    'validation': 'nodevalidator'
  }

  const agentType = agentTypeMap[activeAgent.value]
  if (agentType) {
    const thinking = agentStore.getLatestThinking(agentType)
    return thinking
  }
  return ''
})

// 消息队列管理
interface QueuedMessage {
  id: string
  content: string
  agent: AgentKey
  timestamp: number
  displayStart?: number
  displayDuration?: number
  status?: 'pending' | 'displaying' | 'disappearing' | 'completed'
}

interface ChatMessage {
  id: string
  agent: AgentKey
  content: string
  timestamp: number
}

// 每个Agent的消息队列
const agentMessageQueues = ref<Map<AgentKey, QueuedMessage[]>>(new Map())
const currentDisplayedMessage = ref<Map<AgentKey, QueuedMessage | null>>(new Map())
const disappearingTimers = ref<Map<string, number>>(new Map())
const chatMessages = ref<ChatMessage[]>([])
const chatListRef = ref<HTMLElement | null>(null)
const MAX_CHAT_HISTORY = 200

// 初始化消息队列
const agentTypes: AgentKey[] = ['system', 'main', 'optimization', 'validation']
agentTypes.forEach(agent => {
  agentMessageQueues.value.set(agent, [])
  currentDisplayedMessage.value.set(agent, null)
})

// 全局消息队列 - 用于处理所有Agent的消息排队
const globalMessageQueue = ref<QueuedMessage[]>([])
const isProcessingGlobalQueue = ref(false)

// 处理全局消息队列
function processGlobalMessageQueue() {
  if (isProcessingGlobalQueue.value || globalMessageQueue.value.length === 0) {
    return
  }

  isProcessingGlobalQueue.value = true
  const message = globalMessageQueue.value.shift()!

  console.log('Processing message for', message.agent, ':', message.content.substring(0, 30) + '...')

  // 显示消息
  displayMessage(message)

  // 确保气泡框至少留存5秒 - 避免一闪而过
  const contentLength = message.content.length
  let displayDuration: number

  if (contentLength < 100) {
    // 短消息：最少5秒
    displayDuration = Math.max(5000, contentLength * 25)
  } else if (contentLength < 300) {
    // 中等消息：最少5秒，最多6秒
    displayDuration = Math.max(5000, Math.min(6000, contentLength * 20))
  } else {
    // 长消息：最少5秒，最多8秒
    displayDuration = Math.max(5000, Math.min(8000, contentLength * 15))
  }

  // 设置消失定时器
  setTimeout(() => {
    hideMessage(message)

    // 减少消息间隔时间
    setTimeout(() => {
      isProcessingGlobalQueue.value = false
      processGlobalMessageQueue()
    }, 200) // 减少到200ms
  }, displayDuration)
}

// 显示消息
function displayMessage(message: QueuedMessage) {
  console.log('Displaying message:', message.id, 'for agent:', message.agent)
  message.status = 'displaying'
  message.displayStart = Date.now()
  currentDisplayedMessage.value.set(message.agent, message)
}

// 隐藏消息
function hideMessage(message: QueuedMessage) {
  console.log('Hiding message:', message.id)
  message.status = 'disappearing'

  // 设置消失动画完成后的清理
  const timer = setTimeout(() => {
    console.log('Message cleanup completed:', message.id)
    message.status = 'completed'
    currentDisplayedMessage.value.set(message.agent, null)
    disappearingTimers.value.delete(message.id)
  }, 200) // 减少动画时间到200ms

  disappearingTimers.value.set(message.id, timer)
}

// 获取当前可见的思考消息
function getVisibleThinking(agent: AgentKey): boolean {
  const current = currentDisplayedMessage.value.get(agent)
  return current !== null && current !== undefined &&
         (current.status === 'displaying' || current.status === 'disappearing')
}

// 获取当前思考消息内容
function getCurrentThinkingMessage(agent: AgentKey): string {
  const current = currentDisplayedMessage.value.get(agent)
  return current?.content || ''
}

// 判断气泡是否正在消失
function isBubbleDisappearing(agent: AgentKey): boolean {
  const current = currentDisplayedMessage.value.get(agent)
  return current?.status === 'disappearing' || false
}

// 获取特定Agent的思考内容
function getAgentThinking(agent: AgentKey): string {
  const agentTypeMap: Record<string, AgentType> = {
    'system': 'system',
    'main': 'mainagent',
    'optimization': 'optimizationagent',
    'validation': 'nodevalidator'
  }

  const agentType = agentTypeMap[agent]
  if (agentType) {
    const thinking = agentStore.getLatestThinking(agentType)
    console.log(`getAgentThinking called for ${agent} (${agentType}):`, thinking)
    return thinking
  }
  console.log(`No agent type found for ${agent}`)
  return ''
}

// 添加消息到队列 - 优化为允许同agent消息快速替换
function addThinkingMessageToQueue(agent: AgentKey, content: string) {
  console.log(`Adding ${agent} message to queue:`, content.substring(0, 50) + '...')

  const messageId = `${agent}-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`
  const message: QueuedMessage = {
    id: messageId,
    content,
    agent,
    timestamp: Date.now(),
    status: 'pending'
  }

  // 检查是否替换当前同agent的消息
  const currentMessage = currentDisplayedMessage.value.get(agent)
  if (currentMessage && currentMessage.status === 'displaying') {
    // 立即替换当前显示的消息（适用于连续更新）
    console.log(`Replacing current message for ${agent}`)
    hideMessage(currentMessage)
  }

  globalMessageQueue.value.push(message)
  appendChatMessage(message)

  // 如果队列没有在处理，开始处理
  if (!isProcessingGlobalQueue.value) {
    processGlobalMessageQueue()
  }
}

function appendChatMessage(message: QueuedMessage) {
  chatMessages.value.push({
    id: message.id,
    agent: message.agent,
    content: message.content,
    timestamp: message.timestamp
  })

  if (chatMessages.value.length > MAX_CHAT_HISTORY) {
    chatMessages.value.splice(0, chatMessages.value.length - MAX_CHAT_HISTORY)
  }
}

function formatChatTime(timestamp: number): string {
  return new Date(timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

// 监听agent store中的thinking消息变化
watch(currentAgentThinking, (thinkingMap) => {
  if (!(thinkingMap instanceof Map)) {
    console.warn('Agent thinking payload is not a Map, skipping update')
    return
  }

  console.log('Agent thinking map changed, size:', thinkingMap.size)

  thinkingMap.forEach((thinking, agentType) => {
    const agentTypeMap: Record<string, AgentKey> = {
      'system': 'system',
      'mainagent': 'main',
      'optimizationagent': 'optimization',
      'nodevalidator': 'validation'
    }

    const agent = agentTypeMap[agentType as string]

    if (agent && thinking.thinking) {
      console.log(`Processing thinking for ${agent}:`, thinking.thinking.substring(0, 50) + '...')

      // 检查是否是新的thinking消息（避免重复添加）
      const currentMessage = currentDisplayedMessage.value.get(agent)

      if (!currentMessage || currentMessage.content !== thinking.thinking) {
        console.log(`Adding new thinking message for ${agent}`)
        addThinkingMessageToQueue(agent, thinking.thinking)
      } else {
        console.log(`Skipping duplicate thinking message for ${agent}`)
      }
    }
  })
}, { deep: true })

watch(() => chatMessages.value.length, () => {
  nextTick(() => {
    const container = chatListRef.value
    if (container) {
      container.scrollTop = container.scrollHeight
    }
  })
})

// 测试Agent状态
function testAgentStatus() {
  console.log('Test Agent Status clicked!')

  // 直接添加测试消息到队列
  addThinkingMessageToQueue(activeAgent.value, `这是一个测试思考消息：${activeAgent.value} Agent正在分析数据集特征，准备生成新的特征组合...`)

  // 添加多个测试消息
  setTimeout(() => {
    addThinkingMessageToQueue('system', 'System Agent 正在生成节点样例，包括数据预处理和特征转换逻辑...')
  }, 1000)

  setTimeout(() => {
    addThinkingMessageToQueue('main', 'Main Agent 正在生成特征：max(age, salary) - min(age, salary) 作为新的数值特征...')
  }, 2000)

  setTimeout(() => {
    addThinkingMessageToQueue('optimization', 'Optimization Agent 正在评估特征性能，准确率提升预期：15%...')
  }, 3000)

  taskStore.addNotification(`Test ${activeAgent.value} Agent消息已添加到队列`, 'info')
  console.log('Test message added to queue successfully')
}

// 测试WebSocket消息接收
function testWebSocketMessage() {
  console.log('Test WebSocket Message clicked!')

  // 直接调用agent store的updateAgentThinking来模拟WebSocket消息
  const testThinkingMessage = {
    type: 'agent_thinking' as const,
    agent: 'mainagent' as const,
    thinking: '这是一个通过WebSocket模拟的思考消息：Main Agent正在分析数据特征并准备生成新的组合特征...',
    category: undefined,
    timestamp: Date.now() / 1000
  }

  console.log('Simulating WebSocket thinking message:', testThinkingMessage)
  agentStore.updateAgentThinking(testThinkingMessage)
}

// 模拟agent工作状态（保持原有逻辑）
function simulateAgentWork() {
  if (taskStore.status === 'running') {
    workingAgents.value = ['system']
    connectionActive.value = true

    setTimeout(() => {
      workingAgents.value = ['main']
      connectionActive.value = false
      connectionActiveReverse.value = true

      setTimeout(() => {
        workingAgents.value = ['optimization']
        connectionActiveReverse.value = false
        connectionActiveValidation.value = true

        setTimeout(() => {
          workingAgents.value = ['validation']
          connectionActiveValidation.value = false
          connectionActiveSystem.value = true

          setTimeout(() => {
            workingAgents.value = []
            connectionActiveSystem.value = false
          }, 2000)
        }, 2000)
      }, 2000)
    }, 2000)
  }
}

// 监听任务状态变化
watch(() => taskStore.status, (newStatus) => {
  if (newStatus === 'running') {
    simulateAgentWork()
  } else {
    workingAgents.value = []
    connectionActive.value = false
    connectionActiveReverse.value = false
    connectionActiveValidation.value = false
    connectionActiveSystem.value = false
  }
})

// 监听任务初始化状态变化
watch(() => taskStore.isInitialized, (isInitialized) => {
  if (isInitialized) {
    // 当任务初始化后，加载特征树数据
    featureTreeStore.loadTreeData()
  }
})

// 监听Agent状态变化，更新工作状态
watch(allAgentStates, (states) => {
  const stateList = states || []
  const agentTypeMap: Record<string, AgentKey> = {
    'system': 'system',
    'mainagent': 'main',
    'optimizationagent': 'optimization',
    'nodevalidator': 'validation'
  }

  const newWorkingAgents: AgentKey[] = []

  stateList.forEach((state: AgentState) => {
    const shortName = agentTypeMap[state.agent]
    if (shortName && state.status === 'working') {
      newWorkingAgents.push(shortName)
    }
  })

  workingAgents.value = newWorkingAgents

  // 更新连接状态
  const hasMainAgent = stateList.some((s: AgentState) => s.agent === 'mainagent' && s.status === 'working')
  const hasOptAgent = stateList.some((s: AgentState) => s.agent === 'optimizationagent' && s.status === 'working')
  const hasValidationAgent = stateList.some((s: AgentState) => s.agent === 'nodevalidator' && s.status === 'working')
  const hasSystemAgent = stateList.some((s: AgentState) => s.agent === 'system' && s.status === 'working')

  connectionActive.value = hasMainAgent || hasSystemAgent
  connectionActiveReverse.value = hasOptAgent
  connectionActiveValidation.value = hasValidationAgent
  connectionActiveSystem.value = hasSystemAgent
}, { deep: true })

// 键盘快捷键处理
const handleKeyDown = (event: KeyboardEvent) => {
  // Ctrl + → 或 Ctrl + ← 切换右侧面板
  if (event.ctrlKey && (event.key === 'ArrowRight' || event.key === 'ArrowLeft')) {
    event.preventDefault()
    toggleRightPanel()
  }
  // Esc 键也可以折叠右侧面板
  if (event.key === 'Escape' && !rightPanelCollapsed.value) {
    toggleRightPanel()
  }
}

onMounted(() => {
  // 从localStorage加载用户偏好
  const savedRatio = localStorage.getItem('main-content-split-ratio')
  const savedCollapsed = localStorage.getItem('right-panel-collapsed')

  if (savedRatio) {
    leftPaneSize.value = parseFloat(savedRatio)
    rightPaneSize.value = 100 - leftPaneSize.value
  }

  if (savedCollapsed) {
    rightPanelCollapsed.value = savedCollapsed === 'true'
    if (rightPanelCollapsed.value) {
      leftPaneSize.value = 100
      rightPaneSize.value = 0
    }
  }

  // 初始化WebSocket连接
  agentStore.initializeWebSocket()

  // 添加键盘事件监听器
  window.addEventListener('keydown', handleKeyDown)

  // 添加性能测试事件监听器
  window.addEventListener('test-performance', handleTestPerformanceEvent as EventListener)

  // 添加splitter点击事件监听器
  nextTick(() => {
    const splitters = document.querySelectorAll('.splitpanes__splitter')
    splitters.forEach((splitter) => {
      splitter.addEventListener('click', (event: Event) => {
        event.preventDefault()
        event.stopPropagation()
        toggleRightPanel()
      })

      splitter.addEventListener('mousedown', (event: Event) => {
        const mouseEvent = event as MouseEvent
        const splitterElement = mouseEvent.target as HTMLElement
        const rect = splitterElement.getBoundingClientRect()
        const centerY = rect.top + rect.height / 2
        const clickY = mouseEvent.clientY

        // 如果点击在中央区域（上下各20px范围内），阻止拖拽
        if (Math.abs(clickY - centerY) < 20) {
          mouseEvent.preventDefault()
          mouseEvent.stopPropagation()
        }
      })
    })
  })
})

onUnmounted(() => {
  // 移除事件监听器
  window.removeEventListener('keydown', handleKeyDown)
  window.removeEventListener('test-performance', handleTestPerformanceEvent as EventListener)

  // 清理所有定时器
  disappearingTimers.value.forEach(timer => {
    clearTimeout(timer)
  })
  disappearingTimers.value.clear()
})

// 处理性能测试事件
function handleTestPerformanceEvent(event: CustomEvent) {
  const { features } = event.detail

  // 确保右侧面板展开
  if (rightPanelCollapsed.value) {
    toggleRightPanel()
  }

  // 调用性能测试函数，传递选中的节点ID
  testPerformance(features)
}

// 右侧面板组件事件处理
async function handleGenerateFeatures() {
  // 处理测试性能请求，使用当前选中的节点ID
  await testPerformance(featureTreeStore.selectedNodeIds)
}

async function testPerformance(selectedNodeIds?: string[]) {
  if (isLoadingPerformance.value) {
    taskStore.addNotification('Performance test already in progress...', 'info')
    return
  }

  // 确定要使用的节点ID
  const nodeIds = selectedNodeIds || featureTreeStore.selectedNodeIds

  if (!nodeIds || nodeIds.length === 0) {
    taskStore.addNotification('Please select at least one feature to test performance', 'info')
    return
  }

  isLoadingPerformance.value = true
  taskStore.addNotification('Testing performance...', 'info')

  try {
    const response = await fetch('/test-performance/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        selectedNodeIds: nodeIds
      })
    })

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`)
    }

    const data = await response.json()

    if (data.status === 'success') {
      // 更新SQL代码（显示all_sql）
      if (data.sql_code && data.sql_code.all_sql) {
        sqlCode.value = data.sql_code.all_sql
      }

      // 更新性能数据
      if (data.performance_info) {
        const perf = data.performance_info

        // 转换性能数据格式
        performanceData.value = {
          accuracy: perf.accuracy || 0,
          precision: perf.precision || 0,
          recall: perf.recall || 0,
          f1Score: perf.f1_score || perf.f1Score || 0,
          auc: perf.auc || 0
        }

        // 转换时间数据（如果存在）
        timeData.value = {
          total: perf.total_time || perf.time_usage || 0,
          generation: perf.generation_time || 0,
          evaluation: perf.evaluation_time || 0,
          selection: perf.selection_time || 0
        }

        // 转换SHAP数据（如果存在）
        if (perf.shap_values && perf.shap_values.length > 0) {
          shapData.value = {
            meanShap: perf.mean_shap || 0,
            features: perf.shap_values.map((shap: any, index: number) => ({
              name: shap.feature_name || `feature_${index}`,
              value: shap.shap_value || shap.value || 0,
              percentage: Math.max(1, (shap.importance || shap.percentage || 1))
            })).sort((a: any, b: any) => b.value - a.value).slice(0, 5)
          }
        }
      }

      taskStore.addNotification('Performance test completed successfully!', 'success')
    } else {
      throw new Error(data.message || 'Performance test failed')
    }
  } catch (error) {
    console.error('Error testing performance:', error)
    taskStore.addNotification(`Error: ${error instanceof Error ? error.message : 'Unknown error'}`, 'fail')
  } finally {
    isLoadingPerformance.value = false
  }
}

function handleRefreshData() {
  // 处理刷新数据请求，重新调用测试性能API
  testPerformance()
}
</script>

<style scoped>
.main-content {
  display: flex;
  flex: 1;
  flex-direction: column;
  padding: 0.85rem 1rem;
  overflow: hidden;
  background-color: #f7f9fc;
  height: 100%;
  --font-size-sm: 1rem;
  --font-size-md: 1.25rem;
  --font-size-lg: 1.5rem;
  --font-size-xl: 1.9rem;
  --spacing-md: 0.7rem;
  --spacing-lg: 1rem;
  --spacing-xl: 1.35rem;
  --accent-blue: #2a7de1;
}

.main-content > .splitpanes {
  flex: 1;
  min-height: 0;
}

/* Scrollbar behavior - hidden until actively interacting */
.main-content,
.main-content * {
  scrollbar-width: none;
  scrollbar-color: transparent transparent;
}

.main-content *::-webkit-scrollbar {
  width: 0;
  height: 0;
  background: transparent;
}

.main-content *:hover {
  scrollbar-width: thin;
  scrollbar-color: rgba(0, 0, 0, 0.3) transparent;
}

.main-content *:hover::-webkit-scrollbar {
  width: 8px;
  height: 8px;
}

.main-content *:hover::-webkit-scrollbar-thumb {
  background: rgba(0, 0, 0, 0.3);
  border-radius: 8px;
}

.main-content *:hover::-webkit-scrollbar-track {
  background: transparent;
}

@media print {
  .main-content {
    background-color: #fff;
  }

  .info-card,
  .agent-chat-panel {
    box-shadow: none;
    border-color: #000;
  }
}

/* 左侧面板布局 */
.left-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  gap: 0;
  padding-right: 0.6rem;
}

.agent-flow-section {
  flex: 1;
  min-height: 200px;
  display: flex;
  flex-direction: column;
  padding-bottom: 0.3rem;
}

.agent-flow-section .info-card {
  flex: 1;
}

.agent-process-content {
  display: flex;
  gap: 0.85rem;
  height: 100%;
  padding: calc(var(--spacing-md) * 1.05);
}

.agent-process-content > .agent-flow-diagram,
.agent-process-content > .agent-chat-panel {
  flex: 1;
  min-width: 0;
}

.agent-chat-panel {
  display: flex;
  flex-direction: column;
  border-radius: 12px;
  border: none;
  background: #fff;
  padding: calc(var(--spacing-md) * 0.95);
  box-shadow: none;
}

.chat-panel-header {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding-bottom: 0.55rem;
  border-bottom: 2px solid var(--accent-blue);
}

.chat-panel-icon {
  width: 34px;
  height: 34px;
  border-radius: 10px;
  background-color: #dbeafe;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #2563eb;
}

.chat-panel-title {
  display: flex;
  flex-direction: column;
  font-weight: 600;
  color: #0f172a;
  font-size: var(--font-size-md);
}

.chat-panel-title small {
  font-weight: 400;
  color: #64748b;
  font-size: var(--font-size-sm);
}

.chat-panel-body {
  flex: 1;
  margin-top: 0.75rem;
  overflow-y: auto;
  padding-right: 0.25rem;
}

.chat-empty-state {
  text-align: center;
  color: #6c757d;
  padding: 2rem 0.5rem;
  font-size: 0.85rem;
}

.chat-message {
  display: flex;
  gap: 0.75rem;
  margin-bottom: 0.75rem;
  align-items: flex-start;
}

.chat-avatar {
  width: 44px;
  height: 44px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 600;
  font-size: var(--font-size-md);
  color: #fff;
  background-color: #adb5bd;
  letter-spacing: 0.5px;
}

.chat-bubble {
  flex: 1;
  padding: 0.5rem 0.75rem;
  border-radius: 12px;
  border: none;
  background-color: #fff;
  box-shadow: none;
}

.chat-meta {
  display: flex;
  justify-content: space-between;
  margin-bottom: 0.25rem;
  font-size: calc(var(--font-size-sm) * 0.9);
  color: #6c757d;
}

.chat-author {
  font-weight: 600;
  color: #1f2933;
}

.chat-time {
  font-size: calc(var(--font-size-sm) * 0.85);
  color: #94a3b8;
}

.chat-text {
  margin: 0;
  font-size: var(--font-size-md);
  color: #1f2933;
  line-height: 1.45;
  white-space: pre-wrap;
}

.chat-message.agent-system .chat-bubble {
  background-color: #edf2ff;
  border-color: #dbe4ff;
}

.chat-message.agent-main .chat-bubble {
  background-color: #e6fcf5;
  border-color: #c3fae8;
}

.chat-message.agent-optimization .chat-bubble {
  background-color: #fff4e6;
  border-color: #ffe8cc;
}

.chat-message.agent-validation .chat-bubble {
  background-color: #f3f0ff;
  border-color: #e5dbff;
}

.chat-avatar.agent-system {
  background-color: #4c6ef5;
}

.chat-avatar.agent-main {
  background-color: #12b886;
}

.chat-avatar.agent-optimization {
  background-color: #f76707;
}

.chat-avatar.agent-validation {
  background-color: #845ef7;
}

@media (max-width: 1280px) {
  .agent-process-content {
    flex-direction: column;
  }

  .agent-process-content > .agent-flow-diagram,
  .agent-process-content > .agent-chat-panel {
    min-height: 300px;
  }
}

/* 下方左右分列布局 */
.lower-section {
  display: flex;
  gap: 1.5rem;
  flex: 1;
  min-height: 200px;
  padding-top: 0.375rem;
}

.node-info-section {
  flex: 1;
  min-width: 200px;
  display: flex;
  flex-direction: column;
}

.feature-tree-section {
  flex: 1;
  min-width: 250px;
  display: flex;
  flex-direction: column;
}

/* 右侧面板布局 */
.right-panel-content {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  gap: 0;
  background-color: transparent;
  padding-left: 0.5rem;
}

.sql-code-section {
  flex: 1;
  min-height: 200px;
  display: flex;
  flex-direction: column;
  padding-bottom: 0.375rem;
}

.feature-performance-section {
  flex: 1;
  min-height: 200px;
  display: flex;
  flex-direction: column;
  padding-top: 0.375rem;
}


/* 展开按钮样式 */
.expand-button {
  position: absolute;
  right: 0;
  top: 50%;
  transform: translateY(-50%);
  background-color: #007bff;
  color: white;
  border: none;
  border-radius: 4px 0 0 4px;
  padding: 0.5rem;
  cursor: pointer;
  z-index: 1000;
  transition: all 0.3s ease;
}

.expand-button:hover {
  background-color: #0056b3;
  padding-left: 1rem;
}

/* Splitpanes 自定义样式 */
:deep(.splitpanes.default-theme .splitpanes__splitter) {
  background-color: transparent !important;
  border: none !important;
  position: relative;
  width: 12px !important;
  cursor: col-resize !important;
  transition: all 0.3s ease !important;
}

:deep(.splitpanes.default-theme .splitpanes__splitter:hover) {
  background-color: transparent !important;
}

/* 在splitter中添加可点击的折叠区域 */
:deep(.splitpanes.default-theme .splitpanes__splitter)::after {
  content: '';
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  width: 40px;
  height: 60px;
  background-color: transparent;
  cursor: default;
  transition: all 0.3s ease;
  z-index: 1;
  border-radius: 4px;
  pointer-events: none;
}

:deep(.splitpanes.default-theme .splitpanes__splitter:hover)::after {
  background-color: transparent;
}

/* 添加箭头 */
:deep(.splitpanes.default-theme .splitpanes__splitter)::before {
  content: '';
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  color: transparent;
  font-size: 0;
  font-weight: bold;
  transition: all 0.3s ease;
  z-index: 11;
  pointer-events: none;
  width: 0;
  height: 0;
  overflow: hidden;
}

:deep(.splitpanes.default-theme .splitpanes__splitter:hover)::before {
  color: transparent;
}

/* 当面板折叠时的箭头方向 - 使用数据属性 */
.splitter-collapsed :deep(.splitpanes.default-theme .splitpanes__splitter)::before {
  content: '';
  color: transparent;
  width: 0;
  height: 0;
  overflow: hidden;
}

:deep(.splitpanes.default-theme .splitpanes__pane) {
  background-color: transparent;
  overflow: hidden;
}

/* 响应式布局 */
@media (max-width: 1200px) {
  .left-panel,
  .right-panel {
    min-height: auto;
  }

  .agent-flow-section {
    min-height: 150px;
  }

  .enhanced-feature-tree-section {
    min-height: 250px;
  }

  .node-info-section {
    min-height: 120px;
  }
}

/* 通用样式 */
.section-header {
  margin-bottom: 0.75rem;
  padding-bottom: 0.45rem;
  border-bottom: 2px solid var(--accent-blue);
}

.section-title {
  color: var(--text-primary);
  font-weight: 600;
  margin: 0;
  display: flex;
  align-items: center;
  font-size: var(--font-size-xl);
}

.info-card {
  height: 100%;
  background-color: #fff;
  border-radius: 8px;
  border: none;
  display: flex;
  flex-direction: column;
  box-shadow: none;
}

.info-header {
  padding: 0.55rem 0.85rem 0.5rem;
  border-bottom: 2px solid var(--accent-blue);
  background-color: #fff;
  border-radius: 8px 8px 0 0;
}

.info-title {
  color: var(--text-primary);
  font-weight: 600;
  margin: 0;
  font-size: var(--font-size-md);
}

.info-content {
  flex: 1;
  padding: calc(var(--spacing-md) * 0.95);
  overflow-y: auto;
}

/* Agent Flow Diagram - 移除背景和边框，让组件自身样式生效 */
.agent-flow-diagram {
  flex: 1;
  position: relative;
  min-height: 350px; /* 增加最小高度以容纳所有节点 */
}

.flow-container {
  position: relative;
  width: 100%;
  height: 100%;
  /* 移除flex布局，使用绝对定位布局 */
}


.agents-container {
  position: relative;
  width: 100%;
  height: 100%;
  min-height: 400px; /* 确保有足够的高度 */
}

.agent-node {
  position: absolute;
  width: 90px;
  text-align: center;
  cursor: pointer;
  transition: all 0.3s ease;
  z-index: 2; /* 确保节点在连接线上方 */
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
}


/* 正方形布局 - 四个节点相对于容器中心的位置，考虑元素宽度 */
.system-agent {
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%) translate(-135px, -135px);
}

.main-agent {
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%) translate(135px, -135px);
}

.opt-agent {
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%) translate(135px, 135px);
}

.validation-agent {
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%) translate(-135px, 135px);
}

.agent-icon {
  width: 70px;
  height: 70px;
  background-color: transparent;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto;
  border: 3px solid transparent;
  transition: all 0.3s ease;
  color: #6c757d;
}

.agent-image {
  width: 100%;
  height: 100%;
  object-fit: contain;
  border-radius: 4px;
}

.agent-node.active .agent-icon {
  background-color: #007bff;
  color: white;
  border-color: #0056b3;
}

.agent-node.working .agent-icon {
  background-color: #28a745;
  color: white;
  animation: breathe 2s ease-in-out infinite;
}

.agent-label {
  font-weight: 600;
  font-size: var(--font-size-md);
  color: var(--text-primary);
  position: absolute;
  bottom: -25px;
  left: 50%;
  transform: translateX(-50%);
  text-align: center;
  white-space: nowrap;
}

.working-indicator {
  position: absolute;
  top: -5px;
  right: -5px;
  width: 12px;
  height: 12px;
  background-color: #ffc107;
  border-radius: 50%;
  animation: pulse 1.5s ease-in-out infinite;
}

.connection-lines {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
  width: 500px;
  height: 500px;
  left: 50%;
  top: 50%;
  transform: translate(-50%, -50%);
  z-index: 0; /* 确保连接线在节点下方 */
}

.connection-line {
  fill: none;
  stroke: #dee2e6;
  stroke-width: 4;
  stroke-dasharray: 5, 5;
  transition: all 0.3s ease;
}

.connection-line.curved {
  stroke-width: 4;
  fill: none;
}

.connection-line.active {
  stroke: #007bff;
  stroke-dasharray: none;
  animation: flow 2s ease-in-out;
}

.connection-line.curved.active {
  stroke: #007bff;
}

/* 节点信息 */
.node-details {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.node-detail {
  display: flex;
  align-items: flex-start;
  gap: 0.5rem;
}

.detail-label {
  font-weight: 600;
  color: var(--text-primary);
  min-width: 80px;
  flex-shrink: 0;
  font-size: var(--font-size-md);
}

.detail-value {
  color: var(--text-secondary);
  word-break: break-word;
  flex: 1;
  font-size: var(--font-size-md);
}

.no-node-info {
  color: #6c757d;
  font-style: italic;
  text-align: center;
  padding: 2rem 0;
  font-size: 14px;
}

/* 动画 */
@keyframes breathe {
  0%, 50%, 100% {
    box-shadow: none;
  }
}

@keyframes pulse {
  0%, 100% {
    opacity: 1;
  }
  50% {
    opacity: 0.5;
  }
}

@keyframes flow {
  0% {
    stroke-dashoffset: 10;
  }
  100% {
    stroke-dashoffset: 0;
  }
}

/* 展开按钮容器样式 */
.expand-button-container {
  position: absolute;
  right: 0;
  top: 50%;
  transform: translateY(-50%);
  z-index: 1000;
  cursor: pointer;
}

.expand-button {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  background-color: #6c757d;
  color: white;
  border: none;
  border-radius: 4px 0 0 4px;
  padding: 0.75rem 1rem;
  box-shadow: none;
  transition: all 0.3s ease;
  white-space: nowrap;
}

.expand-button:hover {
  background-color: #495057;
  transform: translateY(-50%) translateX(-4px);
  box-shadow: none;
}

.expand-arrow {
  font-size: 20px;
  font-weight: bold;
  margin-right: 0.5rem;
}

.expand-tooltip {
  font-size: 1rem;
  font-weight: 500;
}

/* CSS箭头直接在agents-container内，无需额外容器 */

/* 水平箭头基础样式 */
.arrow-horizontal {
  position: absolute;
  top: 50%;
  left: 50%;
  width: 130px;
  height: 4px;
  background-color: #dee2e6;
  transition: all 0.3s ease;
}

.arrow-horizontal::after {
  content: '';
  position: absolute;
  right: -8px;
  top: 50%;
  transform: translateY(-50%);
  width: 0;
  height: 0;
  border-left: 12px solid #dee2e6;
  border-top: 8px solid transparent;
  border-bottom: 8px solid transparent;
}

/* 垂直箭头基础样式 */
.arrow-vertical {
  position: absolute;
  top: 50%;
  left: 50%;
  width: 4px;
  height: 130px;
  background-color: #dee2e6;
  transition: all 0.3s ease;
}

.arrow-vertical::after {
  content: '';
  position: absolute;
  bottom: -8px;
  left: 50%;
  transform: translateX(-50%);
  width: 0;
  height: 0;
  border-top: 12px solid #dee2e6;
  border-left: 8px solid transparent;
  border-right: 8px solid transparent;
}

/* 上横箭头位置 - 匹配新的节点位置 */
.top-arrow {
  transform: translate(-50%, -50%) translateY(-135px);
}

/* 右纵箭头位置 - 匹配新的节点位置 */
.right-arrow {
  transform: translate(-50%, -50%) translateX(135px);
}

/* 下横箭头位置和方向 - 匹配新的节点位置 */
.bottom-arrow {
  transform: translate(-50%, -50%) translateY(135px) rotate(180deg);
}

/* 左纵箭头位置和方向 - 匹配新的节点位置 */
.left-arrow {
  transform: translate(-50%, -50%) translateX(-135px) rotate(180deg);
}

/* 激活状态样式 */
.arrow-horizontal.active,
.arrow-vertical.active {
  background-color: #007bff;
}

.arrow-horizontal.active::after,
.arrow-vertical.active::after {
  border-left-color: #007bff;
  border-top-color: #007bff;
}

.bottom-arrow.active::after {
  border-left-color: #007bff;
}

.left-arrow.active::after {
  border-top-color: #007bff;
}

/* 响应式设计 */
@media (max-width: 1200px) {
  .upper-section {
    flex-direction: column;
  }

  .lower-section {
    flex-direction: column;
    height: auto;
  }

  .agent-flow-section,
  .feature-tree-section {
    min-width: auto;
  }
}

/* Agent思考气泡样式 */
.thinking-bubble {
  position: absolute;
  background: white;
  border: 2px solid #e3f2fd;
  border-radius: 12px;
  padding: 14px 18px;
  box-shadow: none;
  color: #37474f;
  font-size: var(--font-size-md);
  line-height: 1.5;
  font-weight: 500;
  max-width: 400px;
  min-width: 200px;
  z-index: 100;
  animation: thinking-bubble-appear 0.3s ease-out;
}

.thinking-bubble pre {
  margin: 0;
  font-family: inherit;
  font-size: inherit;
  white-space: pre-wrap;
  word-wrap: break-word;
  color: inherit;
}

/* 左侧气泡 */
.left-bubble {
  right: calc(100% + 10px);
  top: 50%;
  transform: translateY(-50%);
}

/* 上方节点（system和main agent）的气泡特殊处理 */
.system-agent .left-bubble {
  top: -8px; /* 从图标顶部向上偏移8px，增加间距 */
  transform: translateY(0); /* 重置变换 */
}

.main-agent .right-bubble {
  top: -8px; /* 从图标顶部向上偏移8px，增加间距 */
  transform: translateY(0); /* 重置变换 */
}

/* 下方节点（optimization和validation）的气泡特殊处理 */
.opt-agent .right-bubble {
  top: auto; /* 取消top定位 */
  bottom: -8px; /* 从图标底部向下偏移8px，增加间距 */
  transform: translateY(0); /* 重置变换 */
}

.validation-agent .left-bubble {
  top: auto; /* 取消top定位 */
  bottom: -8px; /* 从图标底部向下偏移8px，增加间距 */
  transform: translateY(0); /* 重置变换 */
}

.left-bubble::before {
  content: '';
  position: absolute;
  top: 50%;
  right: -8px;
  transform: translateY(-50%);
  width: 0;
  height: 0;
  border-top: 8px solid transparent;
  border-bottom: 8px solid transparent;
  border-left: 8px solid white;
  z-index: 101;
}

.left-bubble::after {
  content: '';
  position: absolute;
  top: 50%;
  right: -10px;
  transform: translateY(-50%);
  width: 0;
  height: 0;
  border-top: 9px solid transparent;
  border-bottom: 9px solid transparent;
  border-left: 9px solid #e3f2fd;
  z-index: 100;
}

/* 上方节点气泡箭头特殊处理 */
.system-agent .left-bubble::before,
.system-agent .left-bubble::after {
  top: 35px; /* 从气泡上边缘往下1/2图标高度（70px/2 = 35px） */
  bottom: auto;
  transform: translateY(-50%);
}

.main-agent .right-bubble::before,
.main-agent .right-bubble::after {
  top: 35px; /* 从气泡上边缘往下1/2图标高度（70px/2 = 35px） */
  bottom: auto;
  transform: translateY(-50%);
}

/* 下方节点气泡箭头特殊处理 */
.opt-agent .right-bubble::before,
.opt-agent .right-bubble::after {
  top: auto;
  bottom: 35px; /* 从气泡下边缘往上1/2图标高度（70px/2 = 35px） */
  transform: translateY(50%);
}

.validation-agent .left-bubble::before,
.validation-agent .left-bubble::after {
  top: auto;
  bottom: 35px; /* 从气泡下边缘往上1/2图标高度（70px/2 = 35px） */
  transform: translateY(50%);
}

/* 右侧气泡 */
.right-bubble {
  left: calc(100% + 10px);
  top: 50%;
  transform: translateY(-50%);
}

.right-bubble::before {
  content: '';
  position: absolute;
  top: 50%;
  left: -8px;
  transform: translateY(-50%);
  width: 0;
  height: 0;
  border-top: 8px solid transparent;
  border-bottom: 8px solid transparent;
  border-right: 8px solid white;
  z-index: 101;
}

.right-bubble::after {
  content: '';
  position: absolute;
  top: 50%;
  left: -10px;
  transform: translateY(-50%);
  width: 0;
  height: 0;
  border-top: 9px solid transparent;
  border-bottom: 9px solid transparent;
  border-right: 9px solid #e3f2fd;
  z-index: 100;
}

@keyframes thinking-bubble-appear {
  0% {
    opacity: 0;
    transform: translateY(-50%) scale(0.8);
  }
  100% {
    opacity: 1;
    transform: translateY(-50%) scale(1);
  }
}

@keyframes thinking-bubble-disappear {
  0% {
    opacity: 1;
    transform: translateY(-50%) scale(1);
  }
  100% {
    opacity: 0;
    transform: translateY(-50%) scale(0.8);
  }
}

/* 为特殊定位的气泡提供不同的动画 */
@keyframes thinking-bubble-appear-top {
  0% {
    opacity: 0;
    transform: translateY(-10px) scale(0.8);
  }
  100% {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}

@keyframes thinking-bubble-disappear-top {
  0% {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
  100% {
    opacity: 0;
    transform: translateY(-10px) scale(0.8);
  }
}

@keyframes thinking-bubble-appear-bottom {
  0% {
    opacity: 0;
    transform: translateY(10px) scale(0.8);
  }
  100% {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}

@keyframes thinking-bubble-disappear-bottom {
  0% {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
  100% {
    opacity: 0;
    transform: translateY(10px) scale(0.8);
  }
}

.bubble-disappearing {
  animation: thinking-bubble-disappear 0.2s ease-in forwards;
}

/* 所有节点使用标准的气泡动画 */
.thinking-bubble {
  animation: thinking-bubble-appear 0.3s ease-out;
}

/* Test按钮样式 */
.btn-info {
  background-color: #17a2b8 !important;
  color: white !important;
  font-weight: 500;
  border: none;
  border-radius: 0.25rem;
  transition: all 0.2s ease;
}

.btn-info:hover:not(:disabled) {
  background-color: #138496 !important;
  transform: translateY(-1px);
}

.btn-info:focus {
  outline: none;
  box-shadow: none;
}
</style>
