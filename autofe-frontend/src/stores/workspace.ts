import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useWorkspaceStore = defineStore('workspace', () => {
  // 三栏布局状态
  const leftColumnVisible = ref(true)
  const rightColumnVisible = ref(true)
  const executionMode = ref<'agent' | 'in-db' | 'performance'>('agent')

  // 布局配置
  const leftColumnWidth = ref(330) // px
  const rightColumnWidth = ref(300) // px

  // Agent状态
  const activeAgent = ref<'main' | 'optimization'>('main')
  const workingAgents = ref<string[]>([])

  // 特征树状态
  const featureTreeScale = ref(1)
  const selectedNode = ref<any>(null)

  // 通知历史 (用于右侧栏显示)
  const notificationHistory = ref<Array<{
    id: string
    message: string
    type: 'success' | 'error' | 'warning' | 'info'
    timestamp: Date
  }>>([])

  // 视图状态
  const isAgentThinkingVisible = ref(false)
  const currentView = ref<'dashboard' | 'detailed'>('dashboard')

  // 执行触发器
  const executionTrigger = ref(0)

  // 方法
  function toggleLeftColumn() {
    leftColumnVisible.value = !leftColumnVisible.value
  }

  function toggleRightColumn() {
    rightColumnVisible.value = !rightColumnVisible.value
  }

  function setExecutionMode(mode: 'agent' | 'in-db' | 'performance') {
    executionMode.value = mode
  }

  function setActiveAgent(agent: 'main' | 'optimization') {
    activeAgent.value = agent
  }

  function setWorkingAgents(agents: string[]) {
    workingAgents.value = [...agents]
  }

  function addWorkingAgent(agent: string) {
    if (!workingAgents.value.includes(agent)) {
      workingAgents.value.push(agent)
    }
  }

  function removeWorkingAgent(agent: string) {
    const index = workingAgents.value.indexOf(agent)
    if (index > -1) {
      workingAgents.value.splice(index, 1)
    }
  }

  function setFeatureTreeScale(scale: number) {
    featureTreeScale.value = Math.max(0.5, Math.min(2, scale))
  }

  function setSelectedNode(node: any) {
    selectedNode.value = node
  }

  function addNotification(message: string, type: 'success' | 'error' | 'warning' | 'info' = 'info') {
    const notification = {
      id: Date.now().toString() + Math.random().toString(36).substr(2, 9),
      message,
      type,
      timestamp: new Date()
    }

    notificationHistory.value.unshift(notification)

    // 限制通知历史数量
    if (notificationHistory.value.length > 100) {
      notificationHistory.value = notificationHistory.value.slice(0, 100)
    }
  }

  function clearNotifications() {
    notificationHistory.value = []
  }

  function toggleAgentThinking() {
    isAgentThinkingVisible.value = !isAgentThinkingVisible.value
  }

  function setView(view: 'dashboard' | 'detailed') {
    currentView.value = view
  }

  function triggerExecution() {
    executionTrigger.value++
  }

  function resetWorkspace() {
    leftColumnVisible.value = true
    rightColumnVisible.value = true
    executionMode.value = 'agent'
    activeAgent.value = 'main'
    workingAgents.value = []
    featureTreeScale.value = 1
    selectedNode.value = null
    isAgentThinkingVisible.value = false
    currentView.value = 'dashboard'
    // 保留通知历史，不清空
  }

  // 布局预设
  const layoutPresets = {
    'full-feature': {
      leftColumnVisible: true,
      rightColumnVisible: true,
      leftColumnWidth: 330,
      rightColumnWidth: 300
    },
    'focus-feature': {
      leftColumnVisible: true,
      rightColumnVisible: false,
      leftColumnWidth: 330,
      rightColumnWidth: 300
    },
    'focus-logs': {
      leftColumnVisible: false,
      rightColumnVisible: true,
      leftColumnWidth: 330,
      rightColumnWidth: 400
    },
    'max-workspace': {
      leftColumnVisible: false,
      rightColumnVisible: false,
      leftColumnWidth: 0,
      rightColumnWidth: 0
    }
  }

  function applyLayoutPreset(presetName: keyof typeof layoutPresets) {
    const preset = layoutPresets[presetName]
    if (preset) {
      leftColumnVisible.value = preset.leftColumnVisible
      rightColumnVisible.value = preset.rightColumnVisible
      leftColumnWidth.value = preset.leftColumnWidth
      rightColumnWidth.value = preset.rightColumnWidth
    }
  }

  return {
    // 状态
    leftColumnVisible,
    rightColumnVisible,
    executionMode,
    leftColumnWidth,
    rightColumnWidth,
    activeAgent,
    workingAgents,
    featureTreeScale,
    selectedNode,
    notificationHistory,
    isAgentThinkingVisible,
    currentView,
    executionTrigger,

    // 方法
    toggleLeftColumn,
    toggleRightColumn,
    setExecutionMode,
    setActiveAgent,
    setWorkingAgents,
    addWorkingAgent,
    removeWorkingAgent,
    setFeatureTreeScale,
    setSelectedNode,
    addNotification,
    clearNotifications,
    toggleAgentThinking,
    setView,
    resetWorkspace,
    applyLayoutPreset,
    layoutPresets,
    triggerExecution
  }
})