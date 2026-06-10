/**
 * WebSocket相关类型定义
 */

// Agent类型
export type AgentType = 'mainagent' | 'optimizationagent' | 'system' | 'nodevalidator'

// Agent状态类型
export type AgentStatusType = 'working' | 'completed' | 'error' | 'idle'

// 思考类型
export type ThinkingCategory = 'analysis' | 'planning' | 'execution' | 'evaluation'

// 通知类型
export type NotificationType = 'info' | 'success' | 'warning' | 'error'

// 基础消息结构
export interface BaseMessage {
  type: string
  timestamp: number
}

// Agent状态消息
export interface AgentStatusMessage extends BaseMessage {
  type: 'agent_status'
  agent: AgentType
  status: AgentStatusType
  work_type?: string
  details?: AgentStatusDetails
  data?: AgentStatusData
  result?: AgentResult
  error?: string
}

// Agent状态详情
export interface AgentStatusDetails {
  node_id?: string
  phase?: string
  progress?: number
  current_features?: number
  estimated_time?: number
  operation?: string
  current_node?: string
  similar_nodes_count?: number
  validation_phase?: string
  step_index?: number
  passed_nodes?: number
  failed_nodes?: number
  complex_nodes_detected?: number
  total_nodes?: number
  successful_code_generation?: number
}

// Agent状态数据
export interface AgentStatusData {
  summary?: string
  nodes_generated?: number
  nodes_for_example?: string[]
  examples_summary?: string
  activities?: AgentActivity[]
  node_id?: string
  final_score?: number
  feature_count?: number
  performance_metrics?: PerformanceMetrics
  code_preview?: string
  code_complexity?: number
  input_features?: string[]
  output_features?: string[]
  fixing_features_count?: number
  exec_time?: number
  operation_desc?: string
  required_optimization?: boolean
  validation_status?: string
  utility_score?: number
  success_rate?: number
  original_complexity?: number
  timestamp?: number
}

// Agent活动信息
export interface AgentActivity {
  node_id: string
  operation_desc?: string
  code_preview?: string
  code_complexity?: number
  input_features?: string[]
  output_features?: string[]
  fixing_features_count?: number
  exec_time?: number
  final_score?: number
  validation_status?: string
  feature_count?: number
  utility_score?: number
  required_optimization?: boolean
}

// 性能指标
export interface PerformanceMetrics {
  accuracy?: number
  improvement?: string | number
}

// Agent执行结果
export interface AgentResult {
  new_features?: number
  success: boolean
  error?: string
}

// Agent思考消息
export interface AgentThinkingMessage extends BaseMessage {
  type: 'agent_thinking'
  agent: AgentType
  thinking: string
  category?: ThinkingCategory
}

// 系统通知消息
export interface SystemNotificationMessage extends BaseMessage {
  type: 'system_notification' | 'connection'
  message: string
  notification_type?: NotificationType
}

// WebSocket消息联合类型
export type WebSocketMessage =
  | AgentStatusMessage
  | AgentThinkingMessage
  | SystemNotificationMessage

// WebSocket回调函数
export interface WebSocketCallbacks {
  onAgentStatusUpdate?: (status: AgentStatusMessage) => void
  onAgentThinking?: (thinking: AgentThinkingMessage) => void
  onSystemNotification?: (notification: SystemNotificationMessage) => void
  onConnect?: () => void
  onDisconnect?: () => void
  onError?: (error: any) => void
}

// Agent状态信息（用于存储）
export interface AgentState {
  agent: AgentType
  status: AgentStatusType
  work_type?: string
  details?: AgentStatusDetails
  data?: AgentStatusData
  result?: AgentResult
  error?: string
  last_updated: number
}

// Agent思考信息（用于存储）
export interface AgentThinking {
  agent: AgentType
  thinking: string
  category?: ThinkingCategory
  timestamp: number
}

// WebSocket连接信息
export interface ConnectionInfo {
  connected: boolean
  id?: string
  url?: string
  reconnectAttempts?: number
}

// WebSocket事件类型
export type WebSocketEventType =
  | 'connect'
  | 'disconnect'
  | 'connect_error'
  | 'agent_status_update'
  | 'agent_thinking'
  | 'system_notification'
  | 'status'
  | 'pong'