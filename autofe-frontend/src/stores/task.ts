import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { TaskConfig, TaskStatus, TaskResponse, Notification, AutoStepData } from '@/types/task'
import { apiService } from '@/services/APIService'

export const useTaskStore = defineStore('task', () => {
  // 状态
  const config = ref<TaskConfig>({
    description: '',
    dataset: '2',
    model: '2',
    mlModel: 'RF'
  })

  const status = ref<TaskStatus>('idle')
  const isInitialized = ref(false)
  const isRunning = ref(false)
  const error = ref<string | null>(null)
  const notifications = ref<Notification[]>([])
  const autoStepData = ref<AutoStepData | null>(null)

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
          mlModel: 'RF'
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
        mlModel: config.value.mlModel
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

  return {
    // 状态
    config,
    status,
    isInitialized,
    isRunning,
    error,
    notifications,
    autoStepData,

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
    ensureInitialized
  }
})
