/**
 * WebSocket服务类，用于与后端Agent状态监控通信
 */
import { io, Socket } from 'socket.io-client'
import type {
  AgentStatusMessage,
  AgentThinkingMessage,
  SystemNotificationMessage,
  WebSocketCallbacks
} from '@/types/websocket'

class WebSocketService {
  private socket: Socket | null = null
  private callbacks: WebSocketCallbacks = {}
  private reconnectAttempts = 0
  private maxReconnectAttempts = 5
  private reconnectDelay = 1000
  private isConnected = false

  constructor() {
    this.connect()
  }

  /**
   * 建立WebSocket连接
   */
  connect(url: string = ''): void {
    if (this.socket?.connected) {
      console.log('WebSocket already connected')
      return
    }

    // 直接连接到服务器，绕过代理问题
    const connectUrl = url || 'http://10.82.1.203:5000'
    console.log(`Connecting directly to WebSocket server at: ${connectUrl}`)

    this.socket = io(connectUrl, {
      autoConnect: true,
      reconnection: true,
      reconnectionDelay: 3000,
      reconnectionAttempts: 10,
      timeout: 60000, // 增加到60秒
      transports: ['websocket', 'polling'] // 优先使用websocket
    })

    this.setupEventListeners()
  }

  /**
   * 设置事件监听器
   */
  private setupEventListeners(): void {
    if (!this.socket) return

    // 连接成功
    this.socket.on('connect', () => {
      console.log('WebSocket connected to ADDA server')
      this.isConnected = true
      this.reconnectAttempts = 0
      this.callbacks.onConnect?.()
    })

    // 连接断开
    this.socket.on('disconnect', (reason) => {
      console.log('WebSocket disconnected:', reason)
      this.isConnected = false
      this.callbacks.onDisconnect?.()
    })

    // 连接错误
    this.socket.on('connect_error', (error) => {
      console.error('WebSocket connection error:', error)
      this.callbacks.onError?.(error)

      // 重连逻辑
      if (this.reconnectAttempts < this.maxReconnectAttempts) {
        setTimeout(() => {
          this.reconnectAttempts++
          console.log(`Attempting to reconnect... (${this.reconnectAttempts}/${this.maxReconnectAttempts})`)
          this.socket?.connect()
        }, this.reconnectDelay * this.reconnectAttempts)
      }
    })

    // Agent状态更新
    this.socket.on('agent_status_update', (status: AgentStatusMessage) => {
      console.log('Agent status update:', status)
      this.callbacks.onAgentStatusUpdate?.(status)
    })

    // Agent思考过程
    this.socket.on('agent_thinking', (thinking: AgentThinkingMessage) => {
      console.log('Agent thinking:', thinking)
      this.callbacks.onAgentThinking?.(thinking)
    })

    // 通用事件监听，用于调试 - 添加在所有事件监听之后
    this.socket.onAny((eventName, ...args) => {
      console.log('[WS DEBUG] Received event:', eventName, args)

      // 特别关注agent_thinking事件
      if (eventName === 'agent_thinking') {
        console.log('[WS DEBUG] 🎯 Agent thinking event received!', args[0])
        this.callbacks.onAgentThinking?.(args[0])
      }
    })

    // 系统通知
    this.socket.on('system_notification', (notification: SystemNotificationMessage) => {
      console.log('System notification:', notification)
      this.callbacks.onSystemNotification?.(notification)
    })

    // 连接状态
    this.socket.on('status', (status: SystemNotificationMessage) => {
      console.log('Status update:', status)
      this.callbacks.onSystemNotification?.(status)
    })

    // Pong响应
    this.socket.on('pong', (data) => {
      console.log('Pong received:', data)
    })
  }

  /**
   * 断开WebSocket连接
   */
  disconnect(): void {
    if (this.socket) {
      this.socket.disconnect()
      this.socket = null
      this.isConnected = false
    }
  }

  /**
   * 检查连接状态
   */
  isSocketConnected(): boolean {
    return this.isConnected && this.socket?.connected || false
  }

  /**
   * 订阅特定Agent状态
   */
  subscribeToAgent(agent: string): void {
    if (this.socket?.connected) {
      this.socket.emit('subscribe_agent', { agent })
    }
  }

  /**
   * 取消订阅特定Agent状态
   */
  unsubscribeFromAgent(agent: string): void {
    if (this.socket?.connected) {
      this.socket.emit('unsubscribe_agent', { agent })
    }
  }

  /**
   * 发送心跳检测
   */
  ping(): void {
    if (this.socket?.connected) {
      this.socket.emit('ping')
    }
  }

  /**
   * 设置回调函数
   */
  setCallbacks(callbacks: WebSocketCallbacks): void {
    this.callbacks = { ...this.callbacks, ...callbacks }
  }

  /**
   * 移除所有回调函数
   */
  clearCallbacks(): void {
    this.callbacks = {}
  }

  /**
   * 获取连接信息
   */
  getConnectionInfo(): {
    connected: boolean
    id: string
    url: string
    reconnectAttempts: number
  } {
    return {
      connected: this.isConnected,
      id: this.socket?.id || '',
      url: (typeof window !== 'undefined' ? window.location.origin : ''),
      reconnectAttempts: this.reconnectAttempts
    }
  }
}

// 创建单例实例
export const webSocketService = new WebSocketService()

// 导出服务类
export default WebSocketService