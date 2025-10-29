import type {
  TaskConfig,
  TaskResponse,
  FeatureTreeResponse,
  PerformanceResponse,
  Notification
} from '@/types'

class APIService {
  private baseURL = ''

  async post<T = any>(endpoint: string, data?: any, timeoutMs: number = 10 * 60 * 1000): Promise<T> {
    // 默认10分钟超时，对于长时操作如next step
    const controller = new AbortController()
    const timeoutId = setTimeout(() => controller.abort(), timeoutMs)

    try {
      const response = await fetch(`${this.baseURL}${endpoint}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: data ? JSON.stringify(data) : undefined,
        signal: controller.signal
      })

      clearTimeout(timeoutId)

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }

      return response.json()
    } catch (error) {
      clearTimeout(timeoutId)

      if (error instanceof Error && error.name === 'AbortError') {
        throw new Error(`Request timeout after ${timeoutMs/1000} seconds`)
      }
      throw error
    }
  }

  // 任务相关API
  async checkFormat(config: TaskConfig): Promise<TaskResponse> {
    const formData = new FormData()
    formData.append('taskDescription', config.description)

    // 将数字值转换为对应的文本
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

    formData.append('dataset', datasetMap[config.dataset] || config.dataset)
    formData.append('model', modelMap[config.model] || config.model)

    const response = await fetch('/check-format/', {
      method: 'POST',
      body: formData
    })

    return response.json()
  }

  async getTreeData(): Promise<FeatureTreeResponse> {
    return this.post('/get-treejson/', {})
  }

  async nextStep(): Promise<TaskResponse> {
    // 为next step操作设置更长的超时时间（15分钟）
    return this.post('/next-step/', undefined, 15 * 60 * 1000)
  }

  async testPerformance(nodeIds: string[]): Promise<PerformanceResponse> {
    return this.post('/test-performance/', { selectedNodeIds: nodeIds })
  }

  async generateModel(nodeIds: string[]): Promise<Blob> {
    const response = await fetch('/gen-model/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ selectedNodeIds: nodeIds })
    })

    if (!response.ok) {
      throw new Error(`Model generation failed: ${response.status}`)
    }

    return response.blob()
  }

  async stopTask(): Promise<TaskResponse> {
    return this.post('/stop-task/')
  }

  async clearTask(): Promise<TaskResponse> {
    return this.post('/clear-task/')
  }

  async checkTaskStatus(): Promise<{ status: 'success' | 'fail', initialized: boolean, message: string }> {
    return this.post('/check-task-status/')
  }

  async getNotifications(): Promise<{ notifications: Notification[] }> {
    const response = await fetch('/get-notifications/', {
      method: 'GET'
    })

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`)
    }

    return response.json()
  }

  async runAutoPipeline(): Promise<TaskResponse> {
    return this.post('/auto-step/')
  }
}

export const apiService = new APIService()