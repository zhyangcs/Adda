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
  // 多候选地址轮询，避免因为端口或代理差异导致首连失败
  private candidateUrls: string[] = this.buildCandidateUrls()
  private currentUrlIndex = 0
  // 控制自动刷新，避免首批消息漏渲染后需要手动刷新
  private lastAutoReloadAt = (typeof sessionStorage !== 'undefined' && Number(sessionStorage.getItem('ws-auto-reload-ts'))) || 0

  private buildCandidateUrls(): string[] {
    // 指定直连后端 WS 地址，避免经过 Vite 代理
    return ['http://10.82.1.203:5000']
  }

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

    const resolvedUrl =
      (url ?? this.candidateUrls[this.currentUrlIndex] ?? '')?.trim()
    const options = {
      autoConnect: true,
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

      // 轮询下一个候选地址，避免卡在不可达地址
      let switched = false
      if (this.candidateUrls.length > 1) {
        this.currentUrlIndex = (this.currentUrlIndex + 1) % this.candidateUrls.length
        const nextUrl = this.candidateUrls[this.currentUrlIndex]
        console.warn(`Switching WS endpoint to: ${nextUrl}`)
        switched = true
      }

      // 若已切换 URL，则销毁旧 socket 并用新 URL 重建，避免继续对不可达地址无限重连
      if (switched) {
        this.socket?.removeAllListeners()
        this.socket?.disconnect()
        this.socket = null
        this.connect(this.candidateUrls[this.currentUrlIndex])
        return
      }

      // 重连逻辑（继续使用 socket.io 自带重连）
      if (this.reconnectAttempts < this.maxReconnectAttempts) {
        setTimeout(() => {
          this.reconnectAttempts++
          console.log(`Attempting to reconnect... (${this.reconnectAttempts}/${this.maxReconnectAttempts})`)
          // 如果已有 socket 实例，直接调用 connect；否则重新创建
          if (this.socket) {
            this.socket.connect()
          } else {
            this.connect()
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
