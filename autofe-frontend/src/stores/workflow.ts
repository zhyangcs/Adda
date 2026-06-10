import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { Agent, WorkflowStep, WorkflowConnection } from '@/types/workflow'

export const useWorkflowStore = defineStore('workflow', () => {
  // 状态
  const agents = ref<Agent[]>([
    {
      id: 'analyzer',
      name: '分析Agent',
      description: '分析数据集和任务需求，确定特征工程方向',
      status: 'idle',
      position: { x: 150, y: 100 },
      icon: '📊'
    },
    {
      id: 'generator',
      name: '生成Agent',
      description: '基于分析结果生成新的特征候选',
      status: 'idle',
      position: { x: 400, y: 100 },
      icon: '⚙️'
    },
    {
      id: 'evaluator',
      name: '评估Agent',
      description: '评估生成特征的性能和有效性',
      status: 'idle',
      position: { x: 650, y: 100 },
      icon: '🎯'
    }
  ])

  const connections = ref<WorkflowConnection[]>([
    { from: 'analyzer', to: 'generator', status: 'idle' },
    { from: 'generator', to: 'evaluator', status: 'idle' }
  ])

  const currentStep = ref<string | null>(null)
  const workflowHistory = ref<WorkflowStep[]>([])
  const isRunning = ref(false)
  const selectedAgent = ref<Agent | null>(null)

  // 计算属性
  const activeAgent = computed(() =>
    agents.value.find(agent => agent.status === 'running')
  )

  const completedSteps = computed(() =>
    workflowHistory.value.filter(step => step.status === 'completed')
  )

  const hasActiveAgent = computed(() => !!activeAgent.value)

  // 方法
  function startAgent(agentId: string) {
    const agent = agents.value.find(a => a.id === agentId)
    if (agent) {
      agent.status = 'running'
      agent.progress = 0
      currentStep.value = agentId
      isRunning.value = true
      selectedAgent.value = agent

      // 更新连接状态
      updateConnections()
    }
  }

  function completeAgent(agentId: string, result: any, duration?: number) {
    const agent = agents.value.find(a => a.id === agentId)
    if (agent) {
      agent.status = 'completed'
      agent.progress = 100
      agent.result = result

      workflowHistory.value.push({
        agentId,
        status: 'completed',
        result,
        timestamp: new Date(),
        duration
      })

      // 更新连接状态
      updateConnections()

      // 自动启动下一个Agent
      scheduleNextAgent(agentId)
    }
  }

  function errorAgent(agentId: string, error: string) {
    const agent = agents.value.find(a => a.id === agentId)
    if (agent) {
      agent.status = 'error'
      agent.error = error
      agent.progress = 0

      workflowHistory.value.push({
        agentId,
        status: 'error',
        result: error,
        timestamp: new Date()
      })

      // 停止工作流
      isRunning.value = false
      currentStep.value = null

      // 更新连接状态
      updateConnections()
    }
  }

  function updateAgentProgress(agentId: string, progress: number, currentTask?: string) {
    const agent = agents.value.find(a => a.id === agentId)
    if (agent) {
      agent.progress = Math.min(100, Math.max(0, progress))
      if (currentTask) {
        agent.currentTask = currentTask
      }
    }
  }

  function scheduleNextAgent(completedAgentId: string) {
    // 定义Agent执行顺序
    const agentOrder = ['analyzer', 'generator', 'evaluator']
    const currentIndex = agentOrder.indexOf(completedAgentId)

    if (currentIndex < agentOrder.length - 1) {
      const nextAgentId = agentOrder[currentIndex + 1]
      setTimeout(() => {
        startAgent(nextAgentId)
        // 模拟执行过程
        simulateAgentExecution(nextAgentId)
      }, 1000)
    } else {
      // 工作流完成
      isRunning.value = false
      currentStep.value = null
    }
  }

  function simulateAgentExecution(agentId: string) {
    const agent = agents.value.find(a => a.id === agentId)
    if (!agent) return

    const taskMessages = {
      analyzer: '分析数据集结构和特征...',
      generator: '生成新特征候选...',
      evaluator: '评估特征性能...'
    }

    const durations = {
      analyzer: 3000,
      generator: 4000,
      evaluator: 2000
    }

    agent.currentTask = taskMessages[agentId as keyof typeof taskMessages]
    const duration = durations[agentId as keyof typeof durations]
    const startTime = Date.now()

    // 模拟进度更新
    const progressInterval = setInterval(() => {
      const currentProgress = agent.progress || 0
      if (currentProgress < 90) {
        updateAgentProgress(agentId, currentProgress + 10)
      }
    }, duration / 10)

    // 完成执行
    setTimeout(() => {
      clearInterval(progressInterval)
      updateAgentProgress(agentId, 100)

      const executionDuration = (Date.now() - startTime) / 1000
      const result = `${agent.name} 执行完成`

      completeAgent(agentId, result, executionDuration)
    }, duration)
  }

  function updateConnections() {
    connections.value.forEach(connection => {
      const fromAgent = agents.value.find(a => a.id === connection.from)
      const toAgent = agents.value.find(a => a.id === connection.to)

      if (fromAgent && toAgent) {
        if (fromAgent.status === 'completed' && toAgent.status !== 'idle') {
          connection.status = 'active'
        } else if (fromAgent.status === 'completed' && toAgent.status === 'idle') {
          connection.status = 'completed'
        } else if (fromAgent.status === 'running') {
          connection.status = 'active'
        } else {
          connection.status = 'idle'
        }
      }
    })
  }

  function selectAgent(agent: Agent | null) {
    selectedAgent.value = agent
  }

  async function startWorkflow() {
    if (isRunning.value) return

    resetWorkflow()
    isRunning.value = true

    // 开始第一个Agent
    setTimeout(() => {
      startAgent('analyzer')
      simulateAgentExecution('analyzer')
    }, 500)
  }

  function resetWorkflow() {
    agents.value.forEach(agent => {
      agent.status = 'idle'
      agent.progress = 0
      agent.currentTask = ''
      agent.result = ''
      agent.error = ''
    })

    connections.value.forEach(connection => {
      connection.status = 'idle'
    })

    currentStep.value = null
    workflowHistory.value = []
    isRunning.value = false
    selectedAgent.value = null
  }

  function stopWorkflow() {
    if (activeAgent.value) {
      errorAgent(activeAgent.value.id, '用户中断执行')
    }
    isRunning.value = false
    currentStep.value = null
  }

  function getAgentById(agentId: string): Agent | undefined {
    return agents.value.find(a => a.id === agentId)
  }

  function getConnectionStatus(fromId: string, toId: string): 'idle' | 'active' | 'completed' {
    const connection = connections.value.find(c => c.from === fromId && c.to === toId)
    return connection?.status || 'idle'
  }

  return {
    // 状态
    agents,
    connections,
    currentStep,
    workflowHistory,
    isRunning,
    selectedAgent,

    // 计算属性
    activeAgent,
    completedSteps,
    hasActiveAgent,

    // 方法
    startAgent,
    completeAgent,
    errorAgent,
    updateAgentProgress,
    selectAgent,
    startWorkflow,
    resetWorkflow,
    stopWorkflow,
    getAgentById,
    getConnectionStatus,
    updateConnections
  }
})