export interface Agent {
  id: string
  name: string
  description: string
  status: AgentStatus
  position: { x: number; y: number }
  icon: string
  progress?: number
  currentTask?: string
}

export type AgentStatus = 'idle' | 'running' | 'completed' | 'error'

export interface WorkflowStep {
  agentId: string
  status: AgentStatus
  result: any
  timestamp: Date
  duration?: number
}

export interface WorkflowConnection {
  from: string
  to: string
  status: 'idle' | 'active' | 'completed'
}