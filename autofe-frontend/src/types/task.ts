export interface TaskConfig {
  description: string
  dataset: string
  model: string
}

export type TaskStatus = 'idle' | 'initializing' | 'running' | 'completed' | 'error'

export interface TaskResponse {
  status: 'success' | 'fail'
  message: string
}

export interface Notification {
  id: string
  notice_description: string
  notice_type: 'success' | 'fail' | 'info'
  timestamp: Date
}