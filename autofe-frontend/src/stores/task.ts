import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { TaskConfig, TaskStatus, TaskResponse, Notification, AutoStepData } from '@/types/task'
import { apiService } from '@/services/APIService'
import { useFeatureTreeStore } from '@/stores/featureTree'
import { useAgentStore } from '@/stores/agent'

export const useTaskStore = defineStore('task', () => {
  // 状态
  const config = ref<TaskConfig>({
    description: '',
    dataset: '2',
    model: '2',
    mlModel: 'RF',
    comparisonMethods: []
  })

  const status = ref<TaskStatus>('idle')
  const isInitialized = ref(false)
  const isRunning = ref(false)
  const error = ref<string | null>(null)
  const notifications = ref<Notification[]>([])
  const autoStepData = ref<AutoStepData | null>(null)
  type AgentSearchStatus = 'idle' | 'running' | 'paused' | 'finished' | 'stopped' | 'error' | 'clear'
  const agentSearchStatus = ref<AgentSearchStatus>('idle')
  const agentSearchInfo = ref<any>(null)
  const featureSearchClearedAt = ref(0)

  // 计算属性
  const canStartTask = computed(() =>
    !isRunning.value
  )

  const canDoNextStep = computed(() =>
    !isRunning.value
  )

  const statusText = computed(() => {
    const statusMap: Record<TaskStatus, string> = {
      idle: 'Ready',
      initializing: 'Initializing...',
      running: 'Running...',
      completed: 'Completed',
      error: 'Error'
    }
    return statusMap[status.value] || 'Unknown'
  })

  // 方法
  async function checkFormat(): Promise<boolean> {
    try {
      status.value = 'initializing'
      const response = await apiService.checkFormat(config.value)

      if (response.status === 'success') {
        isInitialized.value = true
        status.value = 'idle'
        addNotification('Format check successful', 'success')
        return true
      } else {
        throw new Error(response.message)
      }
    } catch (err) {
      status.value = 'error'
      error.value = err instanceof Error ? err.message : '未知错误'
      addNotification(`Format check failed: ${error.value}`, 'fail')
      return false
    }
  }

  async function stopTask() {
    try {
      const response = await apiService.stopTask()
      if (response.status === 'success') {
        isRunning.value = false
        status.value = 'idle'
        addNotification('Task stopped successfully', 'success')
      } else {
        addNotification(`Failed to stop task: ${response.message}`, 'fail')
      }
    } catch (error) {
      addNotification('Failed to stop task', 'fail')
    }
  }

  async function clearTask() {
    try {
      const response = await apiService.clearTask()
      if (response.status === 'success') {
        config.value = {
          description: '',
          dataset: '2',
          model: '2',
          mlModel: 'RF',
          comparisonMethods: []
        }
        status.value = 'idle'
        isInitialized.value = false
        isRunning.value = false
        error.value = null
        notifications.value = []
        autoStepData.value = null
        addNotification('Task cleared successfully', 'success')
      } else {
        addNotification(`Failed to clear task: ${response.message}`, 'fail')
      }
    } catch (error) {
      addNotification('Failed to clear task', 'fail')
    }
  }

  async function ensureInitialized(): Promise<boolean> {
    if (isInitialized.value) return true
    return await checkFormat()
  }

  async function nextStep(): Promise<boolean> {
    try {
      const ready = await ensureInitialized()
      if (!ready) return false

      isRunning.value = true
      status.value = 'running'

      const response = await apiService.nextStep()
      if (response.status === 'success') {
        status.value = 'idle'
        addNotification('Next step executed successfully', 'success')
        return true
      } else {
        status.value = 'error'
        addNotification(`Next step failed: ${response.message}`, 'fail')
        return false
      }
    } catch (error) {
      status.value = 'error'
      addNotification('Failed to execute next step', 'fail')
      return false
    } finally {
      isRunning.value = false
    }
  }

  async function autoStep(useConfig = false): Promise<boolean> {
    try {
      // 调试：打印参数和配置
      console.log('TaskStore autoStep - useConfig:', useConfig)
      if (useConfig) {
        console.log('TaskStore autoStep - Config to send:', {
          description: config.value.description,
          descriptionLength: config.value.description?.length || 0,
          dataset: config.value.dataset,
        model: config.value.model,
        mlModel: config.value.mlModel,
        comparisonMethods: config.value.comparisonMethods
        })
      }

      const ready = await ensureInitialized()
      if (!ready) return false

      isRunning.value = true
      status.value = 'running'

      // 如果指定使用配置，传入配置进行初始化
      const response = await apiService.runAutoPipeline(useConfig ? config.value : undefined)
      if (response.status === 'success') {
        if (response.data) {
          autoStepData.value = response.data
        }
        isInitialized.value = true
        status.value = 'completed'
        addNotification('Auto pipeline executed successfully', 'success')
        return true
      } else {
        status.value = 'error'
        addNotification(`Auto pipeline failed: ${response.message}`, 'fail')
        return false
      }
    } catch (error) {
      status.value = 'error'
      addNotification('Failed to run auto pipeline', 'fail')
      return false
    } finally {
      isRunning.value = false
    }
  }

  async function checkTaskStatus() {
    try {
      const response = await apiService.checkTaskStatus()
      if (response.status === 'success' && response.initialized) {
        isInitialized.value = true
      }
    } catch (error) {
      console.error('Failed to check task status:', error)
    }
  }

  function addNotification(message: string, type: 'success' | 'fail' | 'info' = 'info') {
    const notification: Notification = {
      id: Date.now().toString(),
      notice_description: message,
      notice_type: type,
      timestamp: new Date()
    }
    notifications.value.unshift(notification)

    // 限制通知数量
    if (notifications.value.length > 100) {
      notifications.value = notifications.value.slice(0, 100)
    }
  }

  function clearNotifications() {
    notifications.value = []
  }

  // ==== 可暂停/恢复的特征搜索控制 ====
  const datasetMap: Record<string, string> = {
    '1': 'Titanic',
    '2': 'Heart',
    '3': 'Bank',
    '4': 'Diabetes',
    '5': 'Bike',
    '6': 'House'
  }

  const modelMap: Record<string, string> = {
    '1': 'Openai-gpt4-turbo',
    '2': 'Openai-gpt4o',
    '3': 'Openai-gpt4o-mini',
    '4': 'Deepseek-v3'
  }

  function normalizeFeatureSearchStatus(nextStatus?: string): AgentSearchStatus {
    const normalized = (nextStatus || '').toLowerCase()
    if (normalized === 'running') return 'running'
    if (normalized === 'paused') return 'paused'
    if (normalized === 'error') return 'error'
    if (normalized === 'idle') return 'idle'
    if (normalized === 'finished' || normalized === 'stopped') return 'clear'
    if (normalized === 'stopping') return 'running'
    return 'idle'
  }

  function setFeatureSearchStatus(nextStatus: AgentSearchStatus, info?: any) {
    agentSearchStatus.value = nextStatus
    if (info !== undefined) {
      agentSearchInfo.value = info
    }
  }

  async function startFeatureSearch(depth: number = 1, forceNew = false, resume = false) {
    try {
      const dataset = datasetMap[config.value.dataset] || config.value.dataset || 'Heart'
      const modelType = config.value.mlModel || 'RF'
      agentSearchStatus.value = 'running'
      const res = await apiService.featureSearchStart({
        dataset,
        modelType,
        depth,
        forceNew,
        resume
      })
      agentSearchInfo.value = res.data || null
      agentSearchStatus.value = normalizeFeatureSearchStatus(res.data?.status || 'running')
      addNotification(`Feature search started (depth=${depth}, model=${modelType})`, 'info')
      return true
    } catch (error: any) {
      agentSearchStatus.value = 'error'
      addNotification(`Failed to start feature search: ${error?.message || error}`, 'fail')
      return false
    }
  }

  async function pauseFeatureSearch() {
    try {
      const res = await apiService.featureSearchPause()
      agentSearchInfo.value = res.data || null
      agentSearchStatus.value = normalizeFeatureSearchStatus(res.data?.status || 'paused')
      addNotification('Feature search paused', 'info')
      return true
    } catch (error: any) {
      agentSearchStatus.value = 'error'
      addNotification(`Failed to pause: ${error?.message || error}`, 'fail')
      return false
    }
  }

  async function resumeFeatureSearch() {
    try {
      const res = await apiService.featureSearchResume()
      agentSearchInfo.value = res.data || null
      agentSearchStatus.value = normalizeFeatureSearchStatus(res.data?.status || 'running')
      addNotification('Feature search resumed', 'info')
      return true
    } catch (error: any) {
      agentSearchStatus.value = 'error'
      addNotification(`Failed to resume: ${error?.message || error}`, 'fail')
      return false
    }
  }

  async function stopFeatureSearch() {
    try {
      const agentStore = useAgentStore()
      const res = await apiService.featureSearchStop()
      agentSearchInfo.value = res.data || null
      agentSearchStatus.value = 'clear'
      agentStore.clearWorkingStates()
      addNotification('Feature search stopped', 'warning')
      return true
    } catch (error: any) {
      agentSearchStatus.value = 'error'
      addNotification(`Failed to stop: ${error?.message || error}`, 'fail')
      return false
    }
  }

  async function refreshFeatureSearchStatus() {
    try {
      const res = await apiService.featureSearchStatus()
      agentSearchInfo.value = res.data || null
      if (res.data?.status) {
        agentSearchStatus.value = normalizeFeatureSearchStatus(res.data.status)
      }
    } catch (error) {
      console.error('Failed to refresh feature search status:', error)
    }
  }

  function markFeatureSearchCompleted(info?: any) {
    setFeatureSearchStatus('clear', info)
  }

  function clearFeatureSearchOutput() {
    const featureTreeStore = useFeatureTreeStore()
    const agentStore = useAgentStore()
    featureTreeStore.clearFeatureOutput()
    agentStore.clearMessageQueue()
    agentStore.clearAgentCache()
    agentStore.clearWorkingStates()
    agentSearchInfo.value = null
    agentSearchStatus.value = 'idle'
    featureSearchClearedAt.value = Date.now()
    addNotification('Feature output cleared', 'success')
  }

  return {
    // 状态
    config,
    status,
    isInitialized,
    isRunning,
    error,
    notifications,
    autoStepData,
    agentSearchStatus,
    agentSearchInfo,
    featureSearchClearedAt,

    // 计算属性
    canStartTask,
    canDoNextStep,
    statusText,

    // 方法
    checkFormat,
    stopTask,
    clearTask,
    nextStep,
    autoStep,
    checkTaskStatus,
    addNotification,
    clearNotifications,
    startFeatureSearch,
    pauseFeatureSearch,
    resumeFeatureSearch,
    stopFeatureSearch,
    refreshFeatureSearchStatus,
    ensureInitialized,
    setFeatureSearchStatus,
    markFeatureSearchCompleted,
    clearFeatureSearchOutput
  }
})
