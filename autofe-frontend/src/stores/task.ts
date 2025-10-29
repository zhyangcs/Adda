import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { TaskConfig, TaskStatus, TaskResponse, Notification } from '@/types/task'
import { apiService } from '@/services/APIService'

export const useTaskStore = defineStore('task', () => {
  // 状态
  const config = ref<TaskConfig>({
    description: '',
    dataset: '2',
    model: '2'
  })

  const status = ref<TaskStatus>('idle')
  const isInitialized = ref(false)
  const isRunning = ref(false)
  const error = ref<string | null>(null)
  const notifications = ref<Notification[]>([])

  // 计算属性
  const canStartTask = computed(() =>
    config.value.description.trim() !== '' && !isRunning.value
  )

  const canDoNextStep = computed(() =>
    isInitialized.value && !isRunning.value
  )

  const statusText = computed(() => {
    const statusMap: Record<TaskStatus, string> = {
      idle: '准备就绪',
      initializing: '正在初始化...',
      running: '正在运行...',
      completed: '已完成',
      error: '发生错误'
    }
    return statusMap[status.value] || '未知状态'
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

  async function startTask(): Promise<boolean> {
    if (!canStartTask.value) return false

    const success = await checkFormat()
    if (success) {
      isRunning.value = true
      status.value = 'running'
    }
    return success
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
          model: '2'
        }
        status.value = 'idle'
        isInitialized.value = false
        isRunning.value = false
        error.value = null
        notifications.value = []
        addNotification('Task cleared successfully', 'success')
      } else {
        addNotification(`Failed to clear task: ${response.message}`, 'fail')
      }
    } catch (error) {
      addNotification('Failed to clear task', 'fail')
    }
  }

  async function nextStep(): Promise<boolean> {
    try {
      if (!isInitialized.value) {
        addNotification('请先初始化任务', 'fail')
        return false
      }

      const response = await apiService.nextStep()
      if (response.status === 'success') {
        addNotification('Next step executed successfully', 'success')
        return true
      } else {
        addNotification(`Next step failed: ${response.message}`, 'fail')
        return false
      }
    } catch (error) {
      addNotification('Failed to execute next step', 'fail')
      return false
    }
  }

  async function autoStep(): Promise<boolean> {
    try {
      if (!isInitialized.value) {
        addNotification('请先初始化任务', 'fail')
        return false
      }

      const response = await apiService.runAutoPipeline()
      if (response.status === 'success') {
        addNotification('Auto pipeline executed successfully', 'success')
        return true
      } else {
        addNotification(`Auto pipeline failed: ${response.message}`, 'fail')
        return false
      }
    } catch (error) {
      addNotification('Failed to run auto pipeline', 'fail')
      return false
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

    // 计算属性
    canStartTask,
    canDoNextStep,
    statusText,

    // 方法
    checkFormat,
    startTask,
    stopTask,
    clearTask,
    nextStep,
    autoStep,
    checkTaskStatus,
    addNotification,
    clearNotifications
  }
})