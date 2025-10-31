/**
 * Agent状态管理Store
 * 使用Pinia管理Agent的实时状态和思考过程
 */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
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

  // ===== 计算属性 =====

  // 获取所有Agent的当前状态
  const allAgentStates = computed(() => Array.from(agentStates.value.values()))

  // 获取正在工作的Agent列表
  const workingAgents = computed(() =>
    allAgentStates.value.filter(state => state.status === 'working')
  )

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

  // 更新Agent状态
  const updateAgentState = (statusMessage: AgentStatusMessage) => {
    const { agent, status, work_type, details, data, result, error, timestamp } = statusMessage

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
    agentStates.value.set(agent, agentState)

    // 如果Agent完成工作，延迟清除当前思考（保持10秒用于显示）
    if (status === 'completed' || status === 'error') {
      setTimeout(() => {
        const currentState = agentStates.value.get(agent)
        if (currentState && (currentState.status === 'completed' || currentState.status === 'error')) {
          currentAgentThinking.value.delete(agent)
          console.log(`Cleared thinking for completed agent: ${agent}`)
        }
      }, 10000) // 10秒后清除思考内容
    }
  }

  // 更新Agent思考
  const updateAgentThinking = (thinkingMessage: AgentThinkingMessage) => {
    const { agent, thinking, category, timestamp } = thinkingMessage

    console.log('Agent thinking received:', { agent, thinking, category, timestamp })

    // 更新当前思考
    const currentThinking: AgentThinking = {
      agent,
      thinking,
      category,
      timestamp
    }
    currentAgentThinking.value.set(agent, currentThinking)

    // 添加到历史记录
    if (!agentThinkingHistory.value.has(agent)) {
      agentThinkingHistory.value.set(agent, [])
    }

    const history = agentThinkingHistory.value.get(agent)!
    history.push(currentThinking)

    // 限制历史记录数量
    if (history.length > 50) {
      history.splice(0, history.length - 50)
    }
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
      agentStates.value.delete(agent)
      agentThinkingHistory.value.delete(agent)
      currentAgentThinking.value.delete(agent)
    } else {
      agentStates.value.clear()
      agentThinkingHistory.value.clear()
      currentAgentThinking.value.clear()
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
    // 设置WebSocket回调
    const callbacks = setupWebSocketCallbacks()
    webSocketService.setCallbacks(callbacks)

    // 订阅所有Agent状态
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
    updateAgentState // 暴露用于测试
  }
})