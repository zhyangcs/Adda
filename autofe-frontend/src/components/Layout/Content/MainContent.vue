<template>
  <div
    class="main-content"
    :class="{ 'splitter-collapsed': rightPanelCollapsed }"
    :data-display-mode="displayMode"
  >
    <!-- 使用Splitpanes实现左右分区布局 -->
    <splitpanes class="default-theme main-splitpanes" @resize="handleResize" :push-other-panes="false">
      <!-- Left pane: Agent thinking process + feature generation + agent thinking feed -->
      <pane :size="leftPaneSize" min="15" max="70">
        <div class="left-panel">
          <splitpanes class="default-theme left-inner-split" @resize="handleLeftInnerResize" :push-other-panes="false">
            <pane :size="leftInnerPaneSize" min="25" max="75">
            <div class="pane-fill">
            <div class="left-stack">
              <div class="agent-flow-section">
                <div class="info-card">
                  <div class="info-header">
                    <h6 class="info-title">
                      <Users :size="18" class="me-2" />
                      Agent-based feature generation
                    </h6>
                  </div>
                  <div class="info-content agent-process-content" ref="agentProcessScrollRef">
                    <div class="agent-flow-diagram">
                      <div class="flow-container">
                        <div class="agents-container">
                          <div
                            class="agent-node system-agent"
                            :class="{ working: workingAgents.includes('system') }"
                          >
                            <div class="agent-icon">
                              <img src="/dataset.png" alt="Dataset Info" class="agent-image" />
                            </div>
                            <div class="agent-label">System</div>
                            <div v-if="workingAgents.includes('system')" class="working-indicator"></div>
                          </div>

                          <div
                            class="agent-node main-agent"
                            :class="{ working: workingAgents.includes('mainagent') }"
                          >
                            <div class="agent-icon">
                              <img src="/robot2.png" alt="Main Agent" class="agent-image" />
                            </div>
                            <div class="agent-label">Main Agent</div>
                            <div v-if="workingAgents.includes('mainagent')" class="working-indicator"></div>
                          </div>

                          <div
                            class="agent-node opt-agent"
                            :class="{ working: workingAgents.includes('optimizationagent') }"
                          >
                            <div class="agent-icon">
                              <img src="/robot2.png" alt="Optimization Agent" class="agent-image" />
                            </div>
                            <div class="agent-label">Optimization Agent</div>
                            <div v-if="workingAgents.includes('optimizationagent')" class="working-indicator"></div>
                          </div>

                          <div
                            class="agent-node validation-agent"
                            :class="{ working: workingAgents.includes('nodevalidator') }"
                          >
                            <div class="agent-icon">
                              <img src="/val.png" alt="Validation" class="agent-image" />
                            </div>
                            <div class="agent-label">Validation</div>
                            <div v-if="workingAgents.includes('nodevalidator')" class="working-indicator"></div>
                          </div>

                          <div class="arrow-horizontal top-arrow" :class="{ active: connectionActive }"></div>
                          <div class="arrow-vertical right-arrow" :class="{ active: connectionActiveReverse }"></div>
                          <div class="arrow-horizontal bottom-arrow" :class="{ active: connectionActiveValidation }"></div>
                          <div class="arrow-vertical left-arrow" :class="{ active: connectionActiveSystem }"></div>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              <div class="feature-generation-section">
                <div class="feature-tree-section">
                  <FeatureTreePanel />
                </div>
              </div>

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
                        <span class="detail-label">Operation:</span>
                        <span class="detail-value">{{ featureTreeStore.selectedNode.op_type }}</span>
                      </div>
                      <div class="node-detail">
                        <span class="detail-label">Description:</span>
                        <span class="detail-value">{{ featureTreeStore.selectedNode.operation_desc }}</span>
                      </div>
                      <div class="node-detail">
                        <span class="detail-label">Score:</span>
                        <span class="detail-value">{{ formatScore(featureTreeStore.selectedNode.score) }}</span>
                      </div>
                      <div class="node-code">
                        <details v-if="featureTreeStore.selectedNode.task_code" class="code-block" open>
                          <summary class="code-summary">PYTHON code</summary>
                          <pre class="code-pre"><code class="code-code" v-html="highlightCode(featureTreeStore.selectedNode.task_code, 'python')"></code></pre>
                        </details>
                        <div v-else class="no-task-code">No task code available.</div>
                      </div>
                    </div>
                    <div v-else class="no-node-info">
                      Hover over a node to see details.
                    </div>
                  </div>
                </div>
              </div>
            </div>

            </div>
            </pane>

            <pane :size="rightInnerPaneSize" min="25" max="75">
            <div class="pane-fill">
            <div class="chat-column">
              <div class="chat-card info-card">
                <div class="info-header">
                  <h6 class="info-title">Agent thinking</h6>
                </div>
                <div class="info-content chat-panel-content">
                  <div class="agent-chat-panel">
                    <div class="chat-panel-body" ref="chatListRef">
                      <div v-if="!chatMessages.length" class="chat-empty-state">
                        Agent thinking updates will appear here in real time.
                      </div>
                      <div v-else>
                        <div
                          v-for="message in chatMessages"
                          :key="message.id"
                          class="chat-message"
                          :class="[`agent-${message.agent}`, isRightAligned(message.agent) ? 'align-right' : 'align-left']"
                        >
                          <div class="chat-bubble-wrapper">
                            <div class="chat-header" :class="isRightAligned(message.agent) ? 'header-right' : 'header-left'">
                              <div class="chat-avatar" :class="`agent-${message.agent}`">
                                <img
                                  :src="agentDisplayConfig[message.agent].avatarSrc"
                                  :alt="agentDisplayConfig[message.agent].label"
                                />
                              </div>
                              <div class="chat-agent-name">
                                {{ agentDisplayConfig[message.agent].label }}
                              </div>
                            </div>
                            <div class="chat-bubble">
                              <div class="chat-body">
                                <template
                                  v-for="(segment, segIndex) in parseMessageSegments(message.content)"
                                  :key="`${message.id}-${segIndex}`"
                                >
                                  <p v-if="segment.type === 'text'" class="chat-text">{{ segment.content }}</p>
                                  <details v-else-if="segment.type === 'code'" class="code-block">
                                    <summary class="code-summary">{{ segment.label }}</summary>
                                    <pre class="code-pre"><code class="code-code" v-html="highlightCode(segment.content, segment.language)"></code></pre>
                                  </details>
                                  <details
                                    v-else
                                    class="code-block example-block"
                                    :open="isExampleExpanded(message.id, segIndex)"
                                    @toggle="onExampleToggle(message.id, segIndex, $event)"
                                  >
                                    <summary class="code-summary example-summary">
                                      <span class="example-caret" aria-hidden="true"></span>
                                      <span class="example-summary-text">{{ getExampleSummary(segment.items) }}</span>
                                    </summary>
                                    <ul v-if="isExampleExpanded(message.id, segIndex)" class="examples-list">
                                      <li v-for="(item, exIndex) in (segment.items || [])" :key="`${message.id}-${segIndex}-ex-${exIndex}`">
                                        {{ item }}
                                      </li>
                                    </ul>
                                  </details>
                                </template>
                              </div>
                            </div>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
            </div>
            </pane>
          </splitpanes>
        </div>
      </pane>

      <pane :size="rightPaneSize" min="20" max="60">
        <div class="right-panel-content">
          <InDbComputationPanel />
        </div>
      </pane>

      <div v-if="rightPanelCollapsed" class="expand-button-container" @click="toggleRightPanel">
        <div class="expand-button">
          <span class="expand-arrow">‹</span>
          <span class="expand-tooltip">Show in-DB panel (Ctrl+→)</span>
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
import FeatureTreePanel from '@/components/Features/FeatureTreePanel.vue'
import InDbComputationPanel from '@/components/InDb/InDbComputationPanel.vue'

const taskStore = useTaskStore()
const featureTreeStore = useFeatureTreeStore()
const agentStore = useAgentStore()
const { currentAgentThinking, allAgentStates, workingAgents } = storeToRefs(agentStore)
const { featureSearchClearedAt } = storeToRefs(taskStore)

type AgentKey = 'system' | 'main' | 'optimization' | 'validation'
type DisplayMode = 'paper'

const agentDisplayConfig: Record<AgentKey, { label: string; avatarSrc: string; side: 'left' | 'right' }> = {
  system: { label: 'Dataset Info', avatarSrc: '/dataset_chat.png', side: 'left' },
  main: { label: 'Main Agent', avatarSrc: '/robot2.png', side: 'right' },
  optimization: { label: 'Optimization Agent', avatarSrc: '/robot2.png', side: 'right' },
  validation: { label: 'Validation', avatarSrc: '/val.png', side: 'left' }
}

function isRightAligned(agent: AgentKey): boolean {
  return agentDisplayConfig[agent].side === 'right'
}

const connectionActive = ref(false)
const connectionActiveReverse = ref(false)
const connectionActiveValidation = ref(false)
const connectionActiveSystem = ref(false)
const treeReloadTimer = ref<number | null>(null)
const displayMode = ref<DisplayMode>('paper')

const formatScore = (score?: number) => {
  if (typeof score === 'number' && score >= 0) {
    return (score - 0.15).toFixed(4)
  }
  return 'Validating...'
}

// Right panel hosts the in-DB computation panel
const showRightPanel = true

// Splitpanes 相关状态
const leftPaneSize = ref(75) // 左侧面板默认占75%
const rightPaneSize = ref(25) // 右侧面板默认占25%（留空）
const rightPanelCollapsed = ref(false) // 右侧面板折叠状态

// Left inner split: left-stack vs agent thinking feed
const leftInnerPaneSize = ref(50)
const rightInnerPaneSize = ref(50)

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

function handleLeftInnerResize(event: any) {
  if (Array.isArray(event)) {
    const [leftPane] = event
    leftInnerPaneSize.value = leftPane.size
    rightInnerPaneSize.value = 100 - leftPane.size
    localStorage.setItem('left-inner-split-ratio', leftPane.size.toString())
  } else if (event && event[0]) {
    const leftPane = event[0]
    leftInnerPaneSize.value = leftPane.size
    rightInnerPaneSize.value = 100 - leftPane.size
    localStorage.setItem('left-inner-split-ratio', leftPane.size.toString())
  } else if (event && event.size !== undefined) {
    leftInnerPaneSize.value = event.size
    rightInnerPaneSize.value = 100 - event.size
    localStorage.setItem('left-inner-split-ratio', event.size.toString())
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


// WebSocket相关

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

interface MessageSegment {
  type: 'text' | 'code' | 'examples'
  content: string
  language?: string
  label?: string
  items?: string[]
}

// 每个Agent的消息队列
const agentMessageQueues = ref<Map<AgentKey, QueuedMessage[]>>(new Map())
const currentDisplayedMessage = ref<Map<AgentKey, QueuedMessage | null>>(new Map())
const disappearingTimers = ref<Map<string, number>>(new Map())
const chatMessages = ref<ChatMessage[]>([])
const chatListRef = ref<HTMLElement | null>(null)
const agentProcessScrollRef = ref<HTMLElement | null>(null)
const didSetAgentProcessDefaultScroll = ref(false)
const MAX_CHAT_HISTORY = 200

const PYTHON_KEYWORDS = [
  'False', 'None', 'True', 'and', 'as', 'assert', 'async', 'await', 'break', 'class', 'continue',
  'def', 'del', 'elif', 'else', 'except', 'finally', 'for', 'from', 'global', 'if', 'import',
  'in', 'is', 'lambda', 'nonlocal', 'not', 'or', 'pass', 'raise', 'return', 'try', 'while', 'with', 'yield'
]

function escapeHtml(value: string): string {
  return value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

function highlightCode(code: string, language?: string): string {
  const normalizedLang = (language || '').toLowerCase()
  if (normalizedLang !== 'python') {
    return escapeHtml(code)
  }

  const tokens: Array<{ type: 'normal' | 'string' | 'comment'; text: string }> = []
  let i = 0
  while (i < code.length) {
    const ch = code[i]
    if (ch === '#') {
      const start = i
      while (i < code.length && code[i] !== '\n') {
        i += 1
      }
      tokens.push({ type: 'comment', text: code.slice(start, i) })
      continue
    }

    if (ch === '"' || ch === "'") {
      const quote = ch
      const start = i
      i += 1
      let escaped = false
      while (i < code.length) {
        const current = code[i]
        if (escaped) {
          escaped = false
          i += 1
          continue
        }
        if (current === '\\') {
          escaped = true
          i += 1
          continue
        }
        if (current === quote) {
          i += 1
          break
        }
        i += 1
      }
      tokens.push({ type: 'string', text: code.slice(start, i) })
      continue
    }

    const start = i
    while (i < code.length) {
      const current = code[i]
      if (current === '#' || current === '"' || current === "'") {
        break
      }
      i += 1
    }
    tokens.push({ type: 'normal', text: code.slice(start, i) })
  }

  const keywordRegex = new RegExp(`\\b(${PYTHON_KEYWORDS.join('|')})\\b`, 'g')
  return tokens.map(token => {
    if (token.type === 'comment') {
      return `<span class="code-comment">${escapeHtml(token.text)}</span>`
    }
    if (token.type === 'string') {
      return `<span class="code-string">${escapeHtml(token.text)}</span>`
    }

    let escaped = escapeHtml(token.text)
    escaped = escaped.replace(/\b(\d+(\.\d+)?)\b/g, '<span class="code-number">$1</span>')
    escaped = escaped.replace(keywordRegex, '<span class="code-keyword">$1</span>')
    return escaped
  }).join('')
}

function parseMessageSegments(content: string): MessageSegment[] {
  if (!content) {
    return []
  }

  const parts = content.split('```')
  const segments: MessageSegment[] = []

  const splitExamplesFromText = (text: string): MessageSegment[] => {
    const match = text.match(/(^|\n\n|\n)Examples:\s*/)
    if (!match || match.index === undefined) {
      return [{ type: 'text', content: text.trim() }]
    }

    const markerIndex = match.index
    const markerLength = match[0].length
    const before = text.slice(0, markerIndex).trim()
    const after = text.slice(markerIndex + markerLength).trim()
    const result: MessageSegment[] = []

    if (before) {
      result.push({ type: 'text', content: before })
    }

    const rawItems = after.split('\n')
      .map(line => line.trim())
      .filter(Boolean)
      .map(line => line.replace(/^\d+\.\s*/, '').replace(/^-+\s*/, ''))

    result.push({ type: 'examples', content: '', items: rawItems })
    return result
  }

  const splitCodeFromText = (text: string): MessageSegment[] => {
    const lines = text.split('\n')
    const segments: MessageSegment[] = []
    let buffer: string[] = []
    let inCode = false
    let codeLines: string[] = []

    const flushBuffer = () => {
      const bufferedText = buffer.join('\n').trim()
      if (bufferedText) {
        splitExamplesFromText(bufferedText).forEach(segment => segments.push(segment))
      }
      buffer = []
    }

    const flushCode = () => {
      if (codeLines.length) {
        segments.push({
          type: 'code',
          content: codeLines.join('\n').trim(),
          language: 'python',
          label: 'PYTHON code'
        })
      }
      codeLines = []
    }

    lines.forEach(line => {
      if (!inCode && line.trim() === 'Code:') {
        flushBuffer()
        inCode = true
        return
      }

      if (inCode) {
        if (line.startsWith('  ')) {
          codeLines.push(line.slice(2))
          return
        }
        if (line.startsWith('\t')) {
          codeLines.push(line.slice(1))
          return
        }
        if (line.trim() === '') {
          codeLines.push('')
          return
        }
        flushCode()
        inCode = false
        buffer.push(line)
        return
      }

      buffer.push(line)
    })

    if (inCode) {
      flushCode()
    }

    flushBuffer()
    return segments
  }

  parts.forEach((part, index) => {
    if (!part) {
      return
    }

    if (index % 2 === 0) {
      const trimmed = part.trim()
      if (trimmed) {
        splitCodeFromText(trimmed).forEach(segment => {
          segments.push(segment)
        })
      }
      return
    }

    const newlineIndex = part.indexOf('\n')
    let language = ''
    let code = part

    if (newlineIndex >= 0) {
      language = part.slice(0, newlineIndex).trim()
      code = part.slice(newlineIndex + 1)
    } else {
      language = part.trim()
      code = ''
    }

    const label = language ? `${language.toUpperCase()} code` : 'Code'
    segments.push({ type: 'code', content: code.trim(), language, label })
  })

  if (!segments.length) {
    segments.push({ type: 'text', content })
  }

  return segments
}

// 初始化消息队列
const agentTypes: AgentKey[] = ['system', 'main', 'optimization', 'validation']
agentTypes.forEach(agent => {
  agentMessageQueues.value.set(agent, [])
  currentDisplayedMessage.value.set(agent, null)
})

// 全局消息队列 - 用于处理所有Agent的消息排队
const globalMessageQueue = ref<QueuedMessage[]>([])
const isProcessingGlobalQueue = ref(false)
// 记录各Agent上一条thinking的签名，防止重复渲染
const lastThinkingSignatures = ref<Map<AgentKey, string>>(new Map())
const expandedExampleKeys = ref<Set<string>>(new Set())

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
function addThinkingMessageToQueue(agent: AgentKey, content: string, timestamp?: number) {
  // 队列关闭，直接写入聊天列表
  console.log(`Appending ${agent} message:`, content.substring(0, 50) + '...')
  const messageId = `${agent}-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`
  appendChatMessage({
    id: messageId,
    content,
    agent,
    timestamp: (timestamp && timestamp < 1e12 ? timestamp * 1000 : timestamp) || Date.now()
  })
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

function resetThinkingFeed() {
  chatMessages.value = []
  globalMessageQueue.value = []
  isProcessingGlobalQueue.value = false
  lastThinkingSignatures.value = new Map()
  expandedExampleKeys.value = new Set()

  const clearedQueues = new Map<AgentKey, QueuedMessage[]>()
  const clearedDisplayed = new Map<AgentKey, QueuedMessage | null>()
  agentTypes.forEach(agent => {
    clearedQueues.set(agent, [])
    clearedDisplayed.set(agent, null)
  })
  agentMessageQueues.value = clearedQueues
  currentDisplayedMessage.value = clearedDisplayed

  disappearingTimers.value.forEach(timer => {
    clearTimeout(timer)
  })
  disappearingTimers.value.clear()
}

function formatChatTime(timestamp: number): string {
  const ts = timestamp < 1e12 ? timestamp * 1000 : timestamp
  return new Date(ts).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

function formatExamplePreview(item: string): string {
  const cleaned = item
    .replace(/\s*\(similarity:[^)]+\)/i, '')
    .replace(/^Node\s+/i, 'node ')
    .trim()
  const match = cleaned.match(/node\s+(\d+)\s*:\s*['"]?(.+?)['"]?$/i)
  if (match) {
    return `node ${match[1]}: ${match[2]}`
  }
  return cleaned || 'examples'
}

function getExampleSummary(items?: string[]): string {
  if (!items || items.length === 0) {
    return 'No details'
  }

  const count = items.length
  const first = items[0] ?? ''
  if (!first) {
    return `View Details (${count} items)`
  }

  if (first.includes('similarity:')) {
    return `Reference Examples (${count} items)`
  }

  if (first.includes('complexity:')) {
    return `Optimization Candidates (${count} items)`
  }

  if (first.match(/^Feature\s+\d+:/)) {
    return `Top Features (${count} items)`
  }

  if (first.match(/^Node\s+\d+/)) {
    return `Related Nodes (${count} items)`
  }

  return `View Details (${count} items)`
}

function getExampleKey(messageId: string, segIndex: number): string {
  return `${messageId}-${segIndex}`
}

function isExampleExpanded(messageId: string, segIndex: number): boolean {
  return expandedExampleKeys.value.has(getExampleKey(messageId, segIndex))
}

function setExampleExpanded(messageId: string, segIndex: number, open: boolean) {
  const key = getExampleKey(messageId, segIndex)
  const next = new Set(expandedExampleKeys.value)
  if (open) {
    next.add(key)
  } else {
    next.delete(key)
  }
  expandedExampleKeys.value = next
}

function onExampleToggle(messageId: string, segIndex: number, event: Event) {
  const target = event.target as HTMLDetailsElement | null
  if (!target) {
    return
  }
  setExampleExpanded(messageId, segIndex, target.open)
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
      const tsRaw = thinking.timestamp ?? Date.now()
      const tsMs = tsRaw < 1e12 ? tsRaw * 1000 : tsRaw
      const signature = `${tsMs}-${thinking.thinking}`
      const lastSignature = lastThinkingSignatures.value.get(agent)

      // 避免同一条消息在新Agent到来时被重复渲染
      if (signature !== lastSignature) {
        lastThinkingSignatures.value.set(agent, signature)
        console.log(`Processing thinking for ${agent}:`, thinking.thinking.substring(0, 50) + '...')
        addThinkingMessageToQueue(agent, thinking.thinking, tsMs)
      } else {
        console.log(`Skip duplicate thinking for ${agent} at ${tsMs}`)
      }
    }
  })
}, { deep: true, immediate: true })

watch(() => chatMessages.value.length, () => {
  nextTick(() => {
    const container = chatListRef.value
    if (container) {
      container.scrollTop = container.scrollHeight
    }
  })
})

function trySetAgentProcessDefaultScroll() {
  if (didSetAgentProcessDefaultScroll.value) return

  nextTick(() => {
    const container = agentProcessScrollRef.value
    if (!container) return

    const maxScrollTop = container.scrollHeight - container.clientHeight
    if (maxScrollTop <= 0) return

    // Default to ~10% scrolled down so the diagram isn't clipped at the top.
    container.scrollTop = Math.round(maxScrollTop * 0.1)
    didSetAgentProcessDefaultScroll.value = true
  })
}

watch([leftPaneSize, leftInnerPaneSize, rightPanelCollapsed], () => {
  trySetAgentProcessDefaultScroll()
})

watch(featureSearchClearedAt, (clearedAt) => {
  if (clearedAt) {
    resetThinkingFeed()
  }
})

// 测试Agent状态
function testAgentStatus() {
  console.log('Test Agent Status clicked!')

  // 直接添加测试消息到队列
  addThinkingMessageToQueue('main', 'Test thinking message: Main Agent is analyzing dataset features and preparing new feature combinations...')

  // 添加多个测试消息
  setTimeout(() => {
    addThinkingMessageToQueue('system', 'Dataset Info is generating example nodes, including preprocessing and feature transformation logic...')
  }, 1000)

  setTimeout(() => {
    addThinkingMessageToQueue('main', 'Main Agent is generating a feature: max(age, salary) - min(age, salary) as a new numerical feature...')
  }, 2000)

  setTimeout(() => {
    addThinkingMessageToQueue('optimization', 'Optimization Agent is evaluating feature impact. Expected accuracy gain: 15%...')
  }, 3000)

  taskStore.addNotification('Test agent messages have been added to the feed.', 'info')
  console.log('Test message added to queue successfully')
}

// 测试WebSocket消息接收
function testWebSocketMessage() {
  console.log('Test WebSocket Message clicked!')

  // 直接调用agent store的updateAgentThinking来模拟WebSocket消息
  const testThinkingMessage = {
    type: 'agent_thinking' as const,
    agent: 'mainagent' as const,
    thinking: 'Simulated WebSocket thinking message: Main Agent is analyzing data features and preparing new composite features...',
    category: undefined,
    timestamp: Date.now() / 1000
  }

  console.log('Simulating WebSocket thinking message:', testThinkingMessage)
  agentStore.updateAgentThinking(testThinkingMessage)
}

// 轻量防抖：Agent状态变化时触发特征树刷新
function scheduleTreeReload() {
  if (treeReloadTimer.value) return
  treeReloadTimer.value = window.setTimeout(async () => {
    treeReloadTimer.value = null
    try {
      await featureTreeStore.loadTreeData()
    } catch (err) {
      console.error('Failed to reload feature tree:', err)
    }
  }, 800)
}

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

  const active = agentTypeToKey(workingAgents.value?.[0])
  connectionActive.value = active === 'main'
  connectionActiveReverse.value = active === 'optimization'
  connectionActiveValidation.value = active === 'validation'
  connectionActiveSystem.value = active === 'system'

  // 主Agent工作/完成时触发特征树刷新（防抖）
  const mainAgentState = stateList.find((s: AgentState) => s.agent === 'mainagent')
  if (mainAgentState && (mainAgentState.status === 'working' || mainAgentState.status === 'completed')) {
    scheduleTreeReload()
  }
}, { deep: true })

function agentTypeToKey(agentType?: AgentType): AgentKey | undefined {
  if (!agentType) return undefined
  const map: Partial<Record<AgentType, AgentKey>> = {
    system: 'system',
    mainagent: 'main',
    optimizationagent: 'optimization',
    nodevalidator: 'validation'
  }
  return map[agentType]
}

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
  const savedInnerRatio = localStorage.getItem('left-inner-split-ratio')

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

  if (savedInnerRatio) {
    leftInnerPaneSize.value = parseFloat(savedInnerRatio)
    rightInnerPaneSize.value = 100 - leftInnerPaneSize.value
  }

  // 添加键盘事件监听器
  window.addEventListener('keydown', handleKeyDown)
  // 添加splitter点击事件监听器
  nextTick(() => {
    // Set a nicer default scroll position for the agent process diagram.
    trySetAgentProcessDefaultScroll()

    const splitters = document.querySelectorAll('.main-splitpanes > .splitpanes__splitter')
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

  // 清理所有定时器
  disappearingTimers.value.forEach(timer => {
    clearTimeout(timer)
  })
  disappearingTimers.value.clear()

  if (treeReloadTimer.value) {
    clearTimeout(treeReloadTimer.value)
    treeReloadTimer.value = null
  }
})

</script>

<style scoped>
/* ===========================================
   主内容区域样式 - Main Content Styles
   =========================================== */

/* 主内容容器：设置整体布局、背景和自定义CSS变量 */
.main-content {
  /* 弹性布局，垂直排列，占满可用空间 */
  display: flex;
  flex: 1;
  flex-direction: column;
  /* 内边距：减少页面与组件之间的间隙 */
  padding: 0.3rem 0.4rem;
  /* 隐藏溢出内容 */
  overflow: hidden;
  /* 背景色 */
  background-color: #f7f9fc;
  /* 高度占满容器 */
  height: 100%;

  /* 自定义字体大小变量 */
  --font-size-sm: 1rem;
  --font-size-md: 1.25rem;
  --font-size-lg: 1.5rem;
  --font-size-xl: 1.9rem;
  --font-size-2xl: 2.25rem;
  --font-size-3xl: 2.5rem;

  /* 自定义间距变量 */
  --spacing-md: 0.7rem;
  --spacing-lg: 1rem;
  --spacing-xl: 1.35rem;
}

/* Splitpanes容器：确保分栏组件占满可用空间 */
.main-content > .splitpanes {
  flex: 1;
  min-height: 0;
}

/* ===========================================
   滚动条样式 - Scrollbar Styles
   =========================================== */

/* 默认隐藏滚动条，只在悬停时显示 - 提供更清洁的UI体验 */
.main-content,
.main-content * {
  scrollbar-width: none;
  scrollbar-color: transparent transparent;
}

/* Webkit浏览器滚动条完全隐藏 */
.main-content *::-webkit-scrollbar {
  width: 0;
  height: 0;
  background: transparent;
}

/* 悬停时显示滚动条 */
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

/* ===========================================
   打印样式 - Print Styles
   =========================================== */

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

/* ===========================================
   左侧面板布局 - Left Panel Layout
   =========================================== */

/* 左侧面板容器：垂直布局，包含Agent流程图和功能树 */
.left-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  /* 组件间垂直间距 */
  gap: 0.6rem;
  /* 右侧内边距：已调整为0以减少与右侧面板的间隙 */
  padding-right: 0.0rem;
}

/* Left grid: left stack + agent thinking feed */
.left-inner-split {
  flex: 1;
  min-height: 0;
}

.pane-fill {
  height: 100%;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.left-inner-split :deep(.splitpanes__pane) {
  min-height: 0 !important;
}

.chat-column {
  height: 100%;
}

.left-stack {
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
  min-height: 0;
}

.chat-column {
  display: flex;
  flex-direction: column;
  min-height: 0;
}

/* Agent流程图区域：显示Agent协作流程的可视化图表 */
.agent-flow-section {
  min-height: 200px;
  display: flex;
  flex-direction: column;
}

/* Agent流程图卡片：占满可用空间 */
.agent-flow-section .info-card {
  flex: 1;
}

/* Agent流程图内容容器 */
.agent-process-content {
  display: flex;
  height: 100%;
  /* 内边距 */
  padding: calc(var(--spacing-md) * 0.75);
}

/* Agent流程图容器：设置最小高度和宽度 */
.agent-process-content > .agent-flow-diagram {
  min-height: 430px;
  width: 100%;
}

/* ===========================================
   Agent聊天面板样式 - Agent Chat Panel Styles
   =========================================== */

/* Agent聊天面板容器：右侧显示Agent思考过程的面板 */
.agent-chat-panel {
  display: flex;
  flex-direction: column;
  border-radius: 8px;
  border: none;
  background: #fff;
  /* 内边距 */
  padding: calc(var(--spacing-md) * 0.95);
  box-shadow: none;
  height: 100%;
  /* 隐藏溢出，保持内部滚动 */
  overflow: hidden;
}

/* 聊天面板内容区域：占满可用空间 */
.chat-panel-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  padding: 0;
  overflow: hidden;
}

/* 聊天面板头部：包含图标和标题 */
.chat-panel-header {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  /* 下边距 */
  padding-bottom: 0.55rem;
  border-bottom: none;
}

/* 聊天面板图标：显示Agent相关的图标 */
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

/* 聊天面板标题：显示"Agent Thinking Feed" */
.chat-panel-title {
  display: flex;
  flex-direction: column;
  font-weight: 600;
  color: #0f172a;
  font-size: var(--font-size-lg);
}

/* 聊天面板副标题：显示次级信息 */
.chat-panel-title small {
  font-weight: 400;
  color: #64748b;
  font-size: var(--font-size-sm);
}

/* 聊天面板主体：显示聊天消息列表 */
.chat-panel-body {
  flex: 1;
  margin-top: 0;
  overflow-y: auto;
  /* 右侧内边距，为滚动条留空间 */
  padding-right: 0.25rem;
  max-height: 100%;
}

/* 聊天空状态：当没有消息时显示的提示 */
.chat-empty-state {
  text-align: center;
  color: #6c757d;
  padding: 2rem 0.5rem;
  font-size: 0.85rem;
}

/* 聊天消息容器：单个消息的布局 */
.chat-message {
  display: flex;
  justify-content: flex-start;
  margin-bottom: 0.75rem;
}

.chat-message.align-right {
  justify-content: flex-end;
}

.chat-bubble-wrapper {
  position: relative;
  padding-top: 48px; /* avatar/header height + small gap */
  max-width: min(540px, 100%);
}

/* Header row above bubble: avatar + agent name */
.chat-header {
  position: absolute;
  top: 0;
  display: flex;
  align-items: center;
  gap: 8px;
  min-height: 54px;
  pointer-events: none;
}

.chat-header.header-left {
  left: -10px;
  justify-content: flex-start;
}

.chat-header.header-right {
  right: -10px;
  justify-content: flex-end;
  flex-direction: row-reverse;
}

.chat-agent-name {
  font-weight: 700;
  font-size: 1.1rem;
  color: #000;
  line-height: 1.25;
  white-space: nowrap;
  max-width: 260px;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* 聊天头像：显示Agent的头像 */
.chat-avatar {
  width: 54px;
  height: 54px;
  border-radius: 16px;
  background: transparent;
  border: none;
  box-shadow: none;
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: center;
}

.chat-avatar img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

/* 聊天气泡：显示Agent消息内容 */
.chat-bubble {
  min-width: 0;
  padding: 0.5rem 0.75rem;
  border-radius: 8px;
  border: 1px solid #e2e8f0;
  background-color: #fff;
  box-shadow: none;
  font-family: "Helvetica Neue", Helvetica, Arial, sans-serif;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  text-rendering: optimizeLegibility;
  color: #000;
  font-weight: 500;
}

/* 聊天消息作者：显示Agent名称 */
.chat-author {
  font-weight: 600;
  color: inherit;
}

/* 聊天消息文本：显示消息内容 */
.chat-text {
  margin: 0;
  font-size: 1.20rem;
  color: inherit;
  line-height: 1.30;
  white-space: pre-wrap;
  word-break: break-word;
  overflow-wrap: break-word;
  font-family: inherit;
  font-weight: inherit;
  letter-spacing: 0.01em;
}

.chat-body {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.code-block {
  border-radius: 8px;
  border: 1px solid #d0d7de;
  background: #f6f8fa;
  overflow: hidden;
}

.code-summary {
  cursor: pointer;
  padding: 0.45rem 0.65rem;
  font-size: calc(var(--font-size-sm) * 0.9);
  color: #000;
  background: #eef2f7;
  border-bottom: 1px solid #d0d7de;
  font-family: "Helvetica Neue", Helvetica, Arial, sans-serif;
  font-weight: 600;
}

.code-summary:hover {
  background: #e2e8f0;
}

.example-block {
  border: none !important;
  background: transparent !important;
}

.example-block .code-summary {
  border-bottom: none !important;
  background: transparent !important;
  padding-left: 0 !important;
}

.example-summary {
  display: flex;
  align-items: center;
  gap: 0.45rem;
  font-size: calc(var(--font-size-sm) * 0.85);
  color: #000;
}

.example-caret {
  width: 8px;
  height: 8px;
  border-right: 2px solid #64748b;
  border-bottom: 2px solid #64748b;
  transform: rotate(225deg);
  transition: transform 0.2s ease;
  margin-left: 4px;
}

.example-block[open] .example-caret {
  transform: rotate(405deg);
}

.example-summary-text {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  flex: 1;
  min-width: 0;
}

.example-block .examples-list {
  margin: 0 0 0 7px;
  padding: 0.5rem 0 0.5rem 1rem;
  background: transparent;
  color: #000;
  list-style: none;
  border-left: 2px solid #e2e8f0;
}

.example-block .examples-list li {
  margin-left: 0;
  padding: 0.2rem 0;
  line-height: 1.5;
  word-break: break-word;
  overflow-wrap: break-word;
  white-space: pre-wrap;
}

.code-pre {
  margin: 0;
  padding: 0.7rem 0.8rem;
  background: #0f172a;
  color: #e2e8f0;
  font-size: calc(var(--font-size-sm) * 0.95);
  line-height: 1.5;
  overflow-x: auto;
}

.code-code {
  font-family: "IBM Plex Mono", "JetBrains Mono", "SFMono-Regular", "Consolas", "Liberation Mono", "Courier New", monospace;
  white-space: pre;
}

.code-code .code-keyword {
  color: #7dd3fc;
  font-weight: 600;
}

.code-code .code-string {
  color: #fca5a5;
}

.code-code .code-comment {
  color: #94a3b8;
  font-style: italic;
}

.code-code .code-number {
  color: #facc15;
}

/* ===========================================
   响应式布局 - Responsive Layout
   =========================================== */

@media (max-width: 1280px) {
  .agent-process-content {
    display: flex;
    flex-direction: column;
  }

  .agent-process-content > .agent-flow-diagram {
    min-height: 300px;
  }
}

/* ===========================================
   功能树和节点信息布局 - Feature Tree & Node Info Layout
   =========================================== */

/* Feature Generation区域：包含功能树和节点信息 */
.feature-generation-section {
  flex: 1;
  min-height: 200px;
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
  overflow: hidden;
}

/* 节点信息区域：显示选中节点的详细信息 */
.node-info-section {
  min-width: 200px;
  display: flex;
  flex-direction: column;
  flex: 0 0 320px;
  min-height: 180px;
  overflow: hidden;
}

/* 功能树区域：显示特征工程的树状结构 */
.feature-tree-section {
  flex: 1;
  min-width: 250px;
  display: flex;
  flex-direction: column;
  min-height: 0;
  overflow: hidden;
}

/* ===========================================
   右侧面板布局 - Right Panel Layout
   =========================================== */

/* 右侧面板内容容器：包含Agent Thinking Feed等组件 */
.right-panel-content {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  background-color: transparent;
  /* 左侧内边距 */
  padding-left: 0.35rem;
}

/* 聊天卡片：Agent Thinking Feed的主要容器 */
.chat-card {
  height: 100%;
  display: flex;
  flex-direction: column;
}

/* SQL代码区域：显示生成的SQL代码 */
.sql-code-section {
  flex: 1;
  min-height: 200px;
  display: flex;
  flex-direction: column;
  /* 下边距 */
  padding-bottom: 0.375rem;
}

/* 特征性能区域：显示特征工程的性能指标 */
.feature-performance-section {
  flex: 1;
  min-height: 200px;
  display: flex;
  flex-direction: column;
  /* 上边距 */
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
  width: 4px !important;
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
  border-bottom: none;
}

.section-title {
  color: var(--text-primary);
  font-weight: 600;
  margin: 0;
  display: flex;
  align-items: center;
  font-size: var(--font-size-2xl);
}

.info-card {
  height: 100%;
  background-color: #fff;
  border-radius: 6px;
  border: none;
  display: flex;
  flex-direction: column;
  box-shadow: none;
}

.info-header {
  padding: 0.4rem 0.6rem 0.35rem;
  border-bottom: none;
  background-color: #fff;
  border-radius: 6px 6px 0 0;
}

.info-title {
  color: var(--text-primary);
  font-weight: 700;
  margin: 0;
  font-size: var(--font-size-lg);
}

.info-content {
  flex: 1;
  padding: calc(var(--spacing-md) * 0.7);
  overflow-y: auto;
}

.info-content.chat-panel-content {
  display: flex;
  flex-direction: column;
  padding: 0;
  overflow: hidden;
}

/* Agent Flow Diagram - 移除背景和边框，让组件自身样式生效 */
.agent-flow-diagram {
  flex: 1;
  position: relative;
  min-height: 320px; /* 增加最小高度以容纳所有节点 */
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
  min-height: 320px; /* 确保有足够的高度 */
  transform: translateY(-41px);
}

.agent-node {
  position: absolute;
  width: 75px;
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
  transform: translate(-50%, -50%) translate(-110px, -110px);
}

.main-agent {
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%) translate(110px, -110px);
}

.opt-agent {
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%) translate(110px, 110px);
}

.validation-agent {
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%) translate(-110px, 110px);
}

.agent-icon {
  width: 87px;
  height: 87px;
  background-color: transparent;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto;
  border: 2px solid transparent;
  transition: all 0.3s ease;
  color: #6c757d;
}

.agent-image {
  width: 100%;
  height: 100%;
  object-fit: contain;
  border-radius: 4px;
}


.agent-node.working .agent-icon {
  background-color: transparent;
  color: #007bff;
  box-shadow: none;
  animation: none;
}

.agent-node.working .agent-image {
  animation: glow 2s ease-in-out infinite;
}

.agent-label {
  font-weight: 600;
  font-size: var(--font-size-md);
  color: var(--text-primary);
  position: absolute;
  bottom: -15px;
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

.node-code {
  margin-top: 0.75rem;
}

.no-task-code {
  color: #6c757d;
  font-style: italic;
  font-size: 0.9rem;
}

.no-node-info {
  color: #6c757d;
  font-style: italic;
  text-align: center;
  padding: 2rem 0;
  font-size: 14px;
}

/* 动画 */
@keyframes glow {
  0%, 100% { filter: drop-shadow(0 0 2px rgba(0, 123, 255, 0.5)); }
  50% { filter: drop-shadow(0 0 8px rgba(0, 123, 255, 0.8)); }
}

@keyframes flow-horizontal {
  0% { background-position: 100% 0; }
  100% { background-position: -100% 0; }
}

@keyframes flow-vertical {
  0% { background-position: 0 100%; }
  100% { background-position: 0 -100%; }
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

/* ===========================================
   展开按钮容器样式 - Expand Button Container Styles
   =========================================== */

/* 展开按钮容器：当右侧面板折叠时显示的展开按钮定位 */
.expand-button-container {
  position: absolute;
  right: 0;
  top: 50%;
  transform: translateY(-50%);
  z-index: 1000;
  cursor: pointer;
}

/* 展开按钮：用于展开右侧面板的按钮样式 */
.expand-button {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  background-color: #6c757d;
  color: white;
  border: none;
  border-radius: 4px 0 0 4px;
  padding: 0.5rem 0.7rem;
  box-shadow: none;
  transition: all 0.3s ease;
  white-space: nowrap;
}

/* 展开按钮悬停效果 */
.expand-button:hover {
  background-color: #495057;
  transform: translateY(-50%) translateX(-4px);
  box-shadow: none;
}

/* 展开箭头：按钮中的箭头图标 */
.expand-arrow {
  font-size: 20px;
  font-weight: bold;
  margin-right: 0.5rem;
}

/* 展开提示文本：按钮中的提示文字 */
.expand-tooltip {
  font-size: 1rem;
  font-weight: 500;
}

/* ===========================================
   Agent流程图箭头样式 - Agent Flow Diagram Arrow Styles
   =========================================== */

/* CSS箭头直接在agents-container内，无需额外容器 */

/* 水平箭头基础样式：显示Agent之间的水平连接线 */
.arrow-horizontal {
  position: absolute;
  top: 50%;
  left: 50%;
  width: 100px;
  height: 3px;
  background-color: #dee2e6;
  transition: all 0.3s ease;
}

/* 水平箭头末端箭头符号 */
.arrow-horizontal::after {
  content: '';
  position: absolute;
  right: -6px;
  top: 50%;
  transform: translateY(-50%);
  width: 0;
  height: 0;
  border-left: 10px solid #dee2e6;
  border-top: 6px solid transparent;
  border-bottom: 6px solid transparent;
}

/* 垂直箭头基础样式：显示Agent之间的垂直连接线 */
.arrow-vertical {
  position: absolute;
  top: 50%;
  left: 50%;
  width: 3px;
  height: 100px;
  background-color: #dee2e6;
  transition: all 0.3s ease;
}

/* 垂直箭头末端箭头符号 */
.arrow-vertical::after {
  content: '';
  position: absolute;
  bottom: -6px;
  left: 50%;
  transform: translateX(-50%);
  width: 0;
  height: 0;
  border-top: 10px solid #dee2e6;
  border-left: 6px solid transparent;
  border-right: 6px solid transparent;
}

/* ===========================================
   箭头位置定位 - Arrow Position Styles
   =========================================== */

/* 上横箭头位置：连接System和Main Agent */
.top-arrow {
  transform: translate(-50%, -50%) translateY(-110px);
}

/* 右纵箭头位置：连接Main和Optimization Agent */
.right-arrow {
  transform: translate(-50%, -50%) translateX(110px);
}

/* 下横箭头位置和方向：连接Optimization和Validation Agent */
.bottom-arrow {
  transform: translate(-50%, -50%) translateY(110px) rotate(180deg);
}

/* 左纵箭头位置和方向：连接Validation和System Agent */
.left-arrow {
  transform: translate(-50%, -50%) translateX(-110px) rotate(180deg);
}

/* ===========================================
   箭头激活状态样式 - Arrow Active State Styles
   =========================================== */

/* 激活状态：当Agent正在工作时的高亮效果 */
.arrow-horizontal.active {
  background: linear-gradient(90deg, #dee2e6, #007bff, #dee2e6);
  background-size: 200% 100%;
  animation: flow-horizontal 1.5s linear infinite;
}

.arrow-vertical.active {
  background: linear-gradient(180deg, #dee2e6, #007bff, #dee2e6);
  background-size: 100% 200%;
  animation: flow-vertical 1.5s linear infinite;
}

/* 激活状态的箭头符号颜色 */
.arrow-horizontal.active::after {
  border-left-color: #007bff;
}

.arrow-vertical.active::after {
  border-top-color: #007bff;
}

/* 下箭头的激活状态特殊处理 */
.bottom-arrow.active::after {
  border-left-color: #007bff;
}

/* 左箭头的激活状态特殊处理 */
.left-arrow.active::after {
  border-top-color: #007bff;
}

/* ===========================================
   响应式设计 - Responsive Design
   =========================================== */

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

/* ===========================================
   Agent思考气泡样式 - Agent Thinking Bubble Styles
   =========================================== */

/* 思考气泡：Agent正在思考时显示的提示框 */
.thinking-bubble {
  position: absolute;
  background: white;
  border: 2px solid #e3f2fd;
  border-radius: 8px;
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

/* 思考气泡中的预格式化文本样式 */
.thinking-bubble pre {
  margin: 0;
  font-family: inherit;
  font-size: inherit;
  white-space: pre-wrap;
  word-wrap: break-word;
  color: inherit;
}

/* ===========================================
   气泡位置定位 - Bubble Position Styles
   =========================================== */

/* 左侧气泡：显示在Agent节点左侧的思考气泡 */
.left-bubble {
  right: calc(100% + 10px);
  top: 50%;
  transform: translateY(-50%);
}

/* ===========================================
   不同位置节点的特殊气泡处理 - Special Bubble Handling for Different Positions
   =========================================== */

/* 上方节点（System和Main Agent）的气泡特殊定位 */
.system-agent .left-bubble {
  top: -8px; /* 从图标顶部向上偏移8px，增加间距 */
  transform: translateY(0); /* 重置变换 */
}

.main-agent .right-bubble {
  top: -8px; /* 从图标顶部向上偏移8px，增加间距 */
  transform: translateY(0); /* 重置变换 */
}

/* 下方节点（Optimization和Validation Agent）的气泡特殊定位 */
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

/* ===========================================
   气泡箭头样式 - Bubble Arrow Styles
   =========================================== */

/* 左侧气泡的箭头 - 内层白色箭头 */
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

/* 左侧气泡的箭头 - 外层边框箭头 */
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

/* ===========================================
   上方节点气泡箭头特殊定位 - Top Node Bubble Arrow Special Positioning
   =========================================== */

/* System Agent左侧气泡箭头特殊定位 */
.system-agent .left-bubble::before,
.system-agent .left-bubble::after {
  top: 35px; /* 从气泡上边缘往下1/2图标高度（70px/2 = 35px） */
  bottom: auto;
  transform: translateY(-50%);
}

/* Main Agent右侧气泡箭头特殊定位 */
.main-agent .right-bubble::before,
.main-agent .right-bubble::after {
  top: 35px; /* 从气泡上边缘往下1/2图标高度（70px/2 = 35px） */
  bottom: auto;
  transform: translateY(-50%);
}

/* ===========================================
   下方节点气泡箭头特殊定位 - Bottom Node Bubble Arrow Special Positioning
   =========================================== */

/* Optimization Agent右侧气泡箭头特殊定位 */
.opt-agent .right-bubble::before,
.opt-agent .right-bubble::after {
  top: auto;
  bottom: 35px; /* 从气泡下边缘往上1/2图标高度（70px/2 = 35px） */
  transform: translateY(50%);
}

/* Validation Agent左侧气泡箭头特殊定位 */
.validation-agent .left-bubble::before,
.validation-agent .left-bubble::after {
  top: auto;
  bottom: 35px; /* 从气泡下边缘往上1/2图标高度（70px/2 = 35px） */
  transform: translateY(50%);
}

/* ===========================================
   右侧气泡定位 - Right Bubble Positioning
   =========================================== */

/* 右侧气泡：显示在Agent节点右侧的思考气泡 */
.right-bubble {
  left: calc(100% + 10px);
  top: 50%;
  transform: translateY(-50%);
}

/* 右侧气泡的箭头 - 内层白色箭头 */
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

/* 右侧气泡的箭头 - 外层边框箭头 */
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

/* ===========================================
   气泡动画 - Bubble Animations
   =========================================== */

/* 标准气泡出现动画 */
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

/* 标准气泡消失动画 */
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

/* ===========================================
   特殊定位气泡的动画 - Special Positioned Bubble Animations
   =========================================== */

/* 顶部定位气泡出现动画 */
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

/* 顶部定位气泡消失动画 */
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

/* 底部定位气泡出现动画 */
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

/* 底部定位气泡消失动画 */
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

/* ===========================================
   气泡消失状态 - Bubble Disappearing State
   =========================================== */

/* 气泡消失时的动画状态 */
.bubble-disappearing {
  animation: thinking-bubble-disappear 0.2s ease-in forwards;
}

/* 所有节点使用标准的气泡出现动画 */
.thinking-bubble {
  animation: thinking-bubble-appear 0.3s ease-out;
}

/* ===========================================
   测试按钮样式 - Test Button Styles
   =========================================== */

/* 信息按钮样式：用于测试功能的按钮 */
.btn-info {
  background-color: #17a2b8 !important;
  color: white !important;
  font-weight: 500;
  border: none;
  border-radius: 0.25rem;
  transition: all 0.2s ease;
}

/* 信息按钮悬停效果 */
.btn-info:hover:not(:disabled) {
  background-color: #138496 !important;
  transform: translateY(-1px);
}

/* 信息按钮聚焦效果 */
.btn-info:focus {
  outline: none;
  box-shadow: none;
}

/* Wider gutter between Agent Thinking Process and Agent thinking */
.left-inner-split :deep(.splitpanes__splitter) {
  flex: 0 0 10px !important;
  width: 20px !important;
  min-width: 10px !important;
}
</style>
