/**
 * Agent状态管理Store
 * 使用Pinia管理Agent的实时状态和思考过程
 */
import { defineStore } from 'pinia'
import { ref, computed, readonly } from 'vue'
import type {
  AgentStatusMessage,
  AgentThinkingMessage,
  SystemNotificationMessage,
  AgentThinking,
  AgentType,
  AgentStatusType,
  WebSocketCallbacks
} from '@/types/websocket'

// 本地定义AgentState接口（避免导入问题）
interface AgentState {
  agent: AgentType
  status: AgentStatusType
  work_type?: string
  details?: any
  data?: any
  result?: any
  error?: string
  last_updated: number
}
import { webSocketService } from '@/services/WebSocketService'

export const useAgentStore = defineStore('agent', () => {
  // ===== 状态定义 =====

  // Agent状态映射 {agent_type: AgentState}
  const agentStates = ref<Map<AgentType, AgentState>>(new Map())

  // Agent思考历史 {agent_type: AgentThinking[]}
  const agentThinkingHistory = ref<Map<AgentType, AgentThinking[]>>(new Map())

  // 当前正在思考的Agent {agent_type: AgentThinking}
  const currentAgentThinking = ref<Map<AgentType, AgentThinking>>(new Map())

  // 系统通知列表
  const systemNotifications = ref<SystemNotificationMessage[]>([])

  // WebSocket连接状态
  const isConnected = ref(false)
  const connectionInfo = ref({
    connected: false,
    id: '',
    url: '',
    reconnectAttempts: 0
  })

  // ===== 时间与常量 =====
  const toMs = (ts?: number) => {
    if (!ts) return Date.now()
    return ts < 1e12 ? ts * 1000 : ts
  }
  const STALE_THRESHOLD_MS = 30_000

  // ===== 计算属性 =====

  // 获取所有Agent的当前状态
  const allAgentStates = computed(() => Array.from(agentStates.value.values()))

  // 获取正在工作的Agent列表
  const workingAgents = computed(() => {
    // 首先获取所有状态
    const allStates = Array.from(agentStates.value.values())
    console.log('All agent states:', allStates.map(s => `${s.agent}: ${s.status}`))

    // 获取所有正在工作的agent，并映射到简化的名称
    const working = allStates
      .filter(state => state.status === 'working')
      .map(state => {
        // 将后端的agent名称映射到前端的简化名称
        let mappedName = state.agent
        if (state.agent === 'mainagent') mappedName = 'main'
        if (state.agent === 'optimizationagent') mappedName = 'optimization'
        if (state.agent === 'nodevalidator') mappedName = 'validation'
        if (state.agent === 'system') mappedName = 'system'

        console.log(`Mapping working agent: ${state.agent} -> ${mappedName}`)
        return mappedName
      })

    console.log('Final working agents mapped:', working)
    return working
  })

  // 检查特定Agent是否正在工作
  const isAgentWorking = (agent: AgentType): boolean => {
    const state = agentStates.value.get(agent)
    return state?.status === 'working'
  }

  // 获取特定Agent的当前状态
  const getAgentState = (agent: AgentType): AgentState | undefined => {
    return agentStates.value.get(agent)
  }

  // 获取特定Agent的最新思考或状态信息
  const getLatestThinking = (agent: AgentType): string => {
    // 首先检查是否有thinking内容
    const thinking = currentAgentThinking.value.get(agent)
    if (thinking?.thinking) {
      console.log(`Found thinking for ${agent}:`, thinking.thinking)
      return thinking.thinking
    }

    // 如果没有thinking，检查是否有status信息可以显示
    const state = agentStates.value.get(agent)
    if (state) {
      console.log(`Found state for ${agent}:`, state)
      // 根据状态和工作类型生成显示文本
      if (state.status === 'working' && state.work_type) {
        const text = `正在执行: ${state.work_type}`
        console.log(`Generated working text for ${agent}:`, text)
        return text
      } else if (state.status === 'completed') {
        const summary = state.result?.summary || state.data?.summary
        if (summary) {
          const text = `✅ ${summary}`
          console.log(`Generated completed text for ${agent}:`, text)
          return text
        }
        const text = `✅ 任务完成`
        console.log(`Generated default completed text for ${agent}:`, text)
        return text
      } else if (state.status === 'error') {
        const text = `❌ 错误: ${state.error || '执行失败'}`
        console.log(`Generated error text for ${agent}:`, text)
        return text
      } else if (state.details?.phase) {
        const text = `📋 阶段: ${state.details.phase.replace(/_/g, ' ')}`
        console.log(`Generated phase text for ${agent}:`, text)
        return text
      }
    }

    console.log(`No thinking or state found for ${agent}`)
    return ''
  }

  // 获取特定Agent的思考历史
  const getAgentThinkingHistory = (agent: AgentType, limit: number = 10): AgentThinking[] => {
    const history = agentThinkingHistory.value.get(agent) || []
    return history.slice(-limit)
  }

  // 获取Agent工作进度（如果有的话）
  const getAgentProgress = (agent: AgentType): number => {
    const state = agentStates.value.get(agent)
    return state?.details?.progress || 0
  }

  // ===== WebSocket回调设置 =====

  // 设置WebSocket事件处理
  const setupWebSocketCallbacks = (): WebSocketCallbacks => {
    return {
      onConnect: () => {
        isConnected.value = true
        connectionInfo.value = webSocketService.getConnectionInfo()
        subscribeToAllAgents()
        addSystemNotification({
          type: 'system_notification',
          message: '已连接到ADDA WebSocket服务器',
          notification_type: 'success',
          timestamp: Date.now()
        })
      },

      onDisconnect: () => {
        isConnected.value = false
        connectionInfo.value.connected = false
        addSystemNotification({
          type: 'system_notification',
          message: '与ADDA WebSocket服务器断开连接',
          notification_type: 'warning',
          timestamp: Date.now()
        })
      },

      onError: (error) => {
        addSystemNotification({
          type: 'system_notification',
          message: `WebSocket连接错误: ${error.message || error}`,
          notification_type: 'error',
          timestamp: Date.now()
        })
      },

      onAgentStatusUpdate: (status: AgentStatusMessage) => {
        updateAgentState(status)
      },

      onAgentThinking: (thinking: AgentThinkingMessage) => {
        console.log('Agent thinking received:', thinking)
        updateAgentThinking(thinking)
      },

      onSystemNotification: (notification: SystemNotificationMessage) => {
        addSystemNotification(notification)
      }
    }
  }

  // ===== 状态更新方法 =====

  // 防抖状态更新
  const stateUpdateTimeouts = new Map<string, number>()
  const STATE_UPDATE_DELAY = 500 // 500ms 防抖延迟

  // 更新Agent状态
  const updateAgentState = (statusMessage: AgentStatusMessage) => {
    const { agent, status, work_type, details, data, result, error, timestamp } = statusMessage

    console.log(`[STATE UPDATE] Received status for ${agent}: ${status} - ${work_type || 'N/A'}`)

    // 清除之前的延迟更新
    if (stateUpdateTimeouts.has(agent)) {
      clearTimeout(stateUpdateTimeouts.get(agent)!)
      stateUpdateTimeouts.delete(agent)
    }

    // 对于 working 状态，立即更新；对于其他状态，延迟更新
    const isWorkingState = status === 'working'
    const delay = isWorkingState ? 0 : STATE_UPDATE_DELAY

    console.log(`[STATE UPDATE] ${agent} is working: ${isWorkingState}, delay: ${delay}ms`)

    if (isWorkingState) {
      // working 状态立即更新
      const agentState: AgentState = {
        agent,
        status,
        work_type,
        details,
        data,
        result,
        error,
        last_updated: timestamp
      }

      // 更新状态映射
      const next = new Map(agentStates.value)
      next.set(agent, agentState)
      agentStates.value = next
      console.log(`[STATE UPDATE] IMMEDIATE update for ${agent}: ${status}`)
    } else {
      // 其他状态延迟更新
      const timeoutId = setTimeout(() => {
        const agentState: AgentState = {
          agent,
          status,
          work_type,
          details,
          data,
          result,
          error,
          last_updated: timestamp
        }

        // 更新状态映射
        const next = new Map(agentStates.value)
        next.set(agent, agentState)
        agentStates.value = next
        console.log(`[STATE UPDATE] DELAYED update for ${agent}: ${status} (delayed: ${delay}ms)`)

        stateUpdateTimeouts.delete(agent)
      }, delay)

      stateUpdateTimeouts.set(agent, timeoutId)
    }
  }

  // ===== 消息队列系统 =====

  interface QueuedMessage {
    id: string
    agent: string
    content: string
    timestamp: number
    type: 'thinking' | 'status'
  }

  const messageQueue = ref<QueuedMessage[]>([])
  const currentMessageId = ref<string | null>(null)
  const messageDisplayTimeout = ref<number | null>(null)
  const MESSAGE_DISPLAY_DURATION = 2500 // 2.5秒显示时间

  // 添加消息到队列
  const addMessageToQueue = (message: QueuedMessage) => {
    // 避免重复的相同消息
    const existingIndex = messageQueue.value.findIndex(
      m => m.agent === message.agent && m.content === message.content
    )

    if (existingIndex >= 0) {
      // 更新现有消息的时间戳
      messageQueue.value[existingIndex] = message
    } else {
      // 添加新消息到队列末尾
      messageQueue.value.push(message)
    }

    console.log(`Message added to queue: ${message.agent} - ${message.content.substring(0, 30)}...`)

    // 如果当前没有显示消息，开始显示
    if (!currentMessageId.value) {
      processNextMessage()
    }
  }

  // 处理下一条消息
  const processNextMessage = () => {
    if (messageQueue.value.length === 0) {
      currentMessageId.value = null
      return
    }

    const message = messageQueue.value.shift()!
    currentMessageId.value = message.id

    console.log(`Displaying message: ${message.agent} - ${message.content.substring(0, 30)}...`)

    if (message.type === 'thinking') {
      // 更新思考内容
      const currentThinking: AgentThinking = {
        agent: message.agent as AgentType,
        thinking: message.content,
        category: undefined,
        timestamp: message.timestamp
      }
      const nextThinking = new Map(currentAgentThinking.value)
      nextThinking.set(message.agent as AgentType, currentThinking)
      currentAgentThinking.value = nextThinking
    }

    // 设置3秒后显示下一条消息
    messageDisplayTimeout.value = setTimeout(() => {
      // 清除当前显示的消息
      if (currentMessageId.value === message.id) {
        if (message.type === 'thinking') {
          const nextThinking = new Map(currentAgentThinking.value)
          nextThinking.delete(message.agent as AgentType)
          currentAgentThinking.value = nextThinking
        }
        currentMessageId.value = null

        // 延迟200ms后处理下一条消息，避免闪烁
        setTimeout(() => {
          processNextMessage()
        }, 200)
      }
    }, MESSAGE_DISPLAY_DURATION)
  }

  // 清空队列
  const clearMessageQueue = () => {
    if (messageDisplayTimeout.value) {
      clearTimeout(messageDisplayTimeout.value)
      messageDisplayTimeout.value = null
    }
    messageQueue.value = []
    currentMessageId.value = null
    currentAgentThinking.value = new Map()
  }

  // 更新Agent思考 - 重写为队列模式
  const updateAgentThinking = (thinkingMessage: AgentThinkingMessage) => {
    const { agent, thinking, category, timestamp } = thinkingMessage

    const tsMs = toMs(timestamp)
    const arrivalDelay = Date.now() - tsMs
    // 打印到前端调试，观察延迟/丢弃
    console.log('🎯 Agent thinking received:', {
      agent,
      thinking: thinking?.substring(0, 100) + '...',
      category,
      timestamp,
      fullMessage: thinkingMessage,
      delay_ms: arrivalDelay
    })

    // 超时丢弃
    if (arrivalDelay > STALE_THRESHOLD_MS) {
      console.warn(`[THINKING] Drop stale thinking (${arrivalDelay}ms delay) for ${agent}`)
      return
    }

    // 验证必要字段
    if (!agent || !thinking) {
      console.error('❌ Invalid thinking message - missing agent or thinking:', thinkingMessage)
      return
    }

    const message: QueuedMessage = {
      id: `${agent}-${timestamp}-${Math.random()}`,
      agent,
      content: thinking,
      timestamp: timestamp || Date.now(),
      type: 'thinking'
    }

    console.log('📤 Adding thinking message to queue:', message)
    addMessageToQueue(message)
  }

  // 添加系统通知
  const addSystemNotification = (notification: SystemNotificationMessage) => {
    systemNotifications.value.unshift(notification)

    // 限制通知数量
    if (systemNotifications.value.length > 100) {
      systemNotifications.value = systemNotifications.value.slice(0, 100)
    }
  }

  // ===== Agent操作方法 =====

  // 订阅特定Agent状态
  const subscribeToAgent = (agent: AgentType) => {
    webSocketService.subscribeToAgent(agent)
  }

  // 取消订阅特定Agent状态
  const unsubscribeFromAgent = (agent: AgentType) => {
    webSocketService.unsubscribeFromAgent(agent)
  }

  // 订阅所有Agent状态
  const subscribeToAllAgents = () => {
    const agents: AgentType[] = ['mainagent', 'optimizationagent', 'system', 'nodevalidator']
    agents.forEach(agent => subscribeToAgent(agent))
  }

  // 清除Agent状态缓存
  const clearAgentCache = (agent?: AgentType) => {
    if (agent) {
      const nextStates = new Map(agentStates.value)
      nextStates.delete(agent)
      agentStates.value = nextStates

      const nextHistory = new Map(agentThinkingHistory.value)
      nextHistory.delete(agent)
      agentThinkingHistory.value = nextHistory

      const nextThinking = new Map(currentAgentThinking.value)
      nextThinking.delete(agent)
      currentAgentThinking.value = nextThinking
    } else {
      agentStates.value = new Map()
      agentThinkingHistory.value = new Map()
      currentAgentThinking.value = new Map()
    }
  }

  // 清除系统通知
  const clearNotifications = () => {
    systemNotifications.value = []
  }

  // 发送心跳检测
  const pingServer = () => {
    webSocketService.ping()
  }

  // ===== 初始化方法 =====

  // 初始化WebSocket连接和事件监听
  const initializeWebSocket = () => {
    // 先绑定回调，避免连接初始缓存事件丢失
    const callbacks = setupWebSocketCallbacks()
    webSocketService.setCallbacks(callbacks)

    // 再建立连接
    webSocketService.connect()

    // 订阅所有Agent状态（若此时尚未连接，onConnect回调会再次订阅）
    subscribeToAllAgents()

    // 暂时禁用心跳检测，避免连接问题
    // setInterval(() => {
    //   if (isConnected.value) {
    //     pingServer()
    //   }
    // }, 30000) // 每30秒发送一次心跳
  }

  // ===== 返回值 =====

  return {
    // 状态
    agentStates,
    agentThinkingHistory,
    currentAgentThinking,
    systemNotifications,
    isConnected,
    connectionInfo,
    messageQueue: readonly(messageQueue),

    // 计算属性
    allAgentStates,
    workingAgents,

    // 方法
    isAgentWorking,
    getAgentState,
    getLatestThinking,
    getAgentThinkingHistory,
    getAgentProgress,
    subscribeToAgent,
    unsubscribeFromAgent,
    subscribeToAllAgents,
    clearAgentCache,
    clearNotifications,
    pingServer,
    initializeWebSocket,
    updateAgentThinking, // 暴露用于测试
    updateAgentState, // 暴露用于测试
    clearMessageQueue, // 消息队列控制
    addMessageToQueue // 消息队列控制
  }
})
