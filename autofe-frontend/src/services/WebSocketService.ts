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
  // 尽量无限重连，避免后端稍晚启动导致必须刷新
  private maxReconnectAttempts = Number.MAX_SAFE_INTEGER
  private reconnectDelay = 1000
  private isConnected = false
  // 控制自动刷新，避免首批消息漏渲染后需要手动刷新
  private lastAutoReloadAt = (typeof sessionStorage !== 'undefined' && Number(sessionStorage.getItem('ws-auto-reload-ts'))) || 0
  /**
   * Backend Socket.IO endpoint.
   *
   * Priority:
   * - `VITE_WS_URL` (explicit override)
   * - Same hostname + port 5000 (common local/dev setup: frontend on :5173, backend on :5000)
   *
   * Note: Socket.IO expects an HTTP(S) origin URL (it upgrades to WebSocket internally).
   */
  private readonly defaultWsUrl: string = (() => {
    const viteWsUrl =
      (typeof import.meta !== 'undefined' && (import.meta as any).env?.VITE_WS_URL) ||
      ''
    if (viteWsUrl && typeof viteWsUrl === 'string') {
      const trimmed = viteWsUrl.trim()
      // Accept ws/wss but normalize to http/https for Socket.IO.
      if (trimmed.startsWith('ws://')) return `http://${trimmed.slice('ws://'.length)}`
      if (trimmed.startsWith('wss://')) return `https://${trimmed.slice('wss://'.length)}`
      return trimmed
    }

    if (typeof window !== 'undefined' && window.location) {
      const protocol = window.location.protocol === 'https:' ? 'https:' : 'http:'
      const host = window.location.hostname || '127.0.0.1'
      const port = window.location.port ? `:${window.location.port}` : ''
      return `${protocol}//${host}${port}`
    }

    return 'http://127.0.0.1'
  })()

  constructor() {
    // 延迟到调用方明确初始化再连接，避免在回调未注册时丢失缓存事件
  }

  /**
   * 建立WebSocket连接
   */
  connect(url?: string): void {
    // 避免重复创建连接：已连接或正在连接则直接返回
    if (this.socket) {
      if (this.socket.connected) {
        console.log('WebSocket already connected')
        return
      }
      if ((this.socket as any).connecting) {
        console.log('WebSocket is connecting, skip duplicate connect')
        return
      }
      // 如果已有实例但断开，尝试重连而不是重新 new
      console.log('WebSocket instance exists, calling connect()')
      this.socket.connect()
      return
    }

    // 始终优先使用明确的后端地址，避免误连到前端 dev 端口
    const resolvedUrl = (url ?? this.defaultWsUrl)?.trim()
    // 关键：先绑定监听器再 connect，避免首屏错过 server 在 connect 阶段推送的缓存事件
    const options = {
      autoConnect: false,
      reconnection: true,
      reconnectionDelay: 3000,
      reconnectionAttempts: Number.MAX_SAFE_INTEGER,
      timeout: 60000, // 增加到60秒
      transports: ['websocket', 'polling'] as string[] // 优先使用websocket
    }

    if (resolvedUrl) {
      console.log(`Connecting to WebSocket server at: ${resolvedUrl}`)
      this.socket = io(resolvedUrl, options)
    } else {
      console.log('Connecting to WebSocket server via current origin/proxy')
      this.socket = io(options)
    }

    // 先注册监听器，再发起连接，避免 race
    this.setupEventListeners()
    this.socket.connect()
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

      // 重连逻辑（继续使用 socket.io 自带重连）
      if (this.reconnectAttempts < this.maxReconnectAttempts) {
        setTimeout(() => {
          this.reconnectAttempts++
          console.log(`Attempting to reconnect... (${this.reconnectAttempts}/${this.maxReconnectAttempts})`)
          if (this.socket) {
            this.socket.connect()
          } else {
            this.connect(this.defaultWsUrl)
          }
        }, this.reconnectDelay * this.reconnectAttempts)
      }
    })

    // Agent状态更新
    this.socket.on('agent_status_update', (status: AgentStatusMessage) => {
      console.log('Agent status update:', status)
      this.maybeAutoReloadOnFirstStatus()
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

  /**
   * 首次收到状态时自动刷新页面，避免初始渲染错过推送
   * 刷新频率限定 10 秒内只触发一次，防止循环刷新
   */
  private maybeAutoReloadOnFirstStatus() {
    // 暂时关闭首条状态自动刷新，避免丢失消息导致必须手动刷新
    return
  }
}

// 创建单例实例
export const webSocketService = new WebSocketService()

// 导出服务类
export default WebSocketService
