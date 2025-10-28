import type {
  TaskConfig,
  TaskResponse,
  FeatureTreeResponse,
  PerformanceResponse,
  Notification
} from '@/types'

class APIService {
  private baseURL = ''

  async post<T = any>(endpoint: string, data?: any): Promise<T> {
    const response = await fetch(`${this.baseURL}${endpoint}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: data ? JSON.stringify(data) : undefined
    })

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`)
    }

    return response.json()
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
    try {
      const response = await fetch('/get-treejson/', {
        method: 'POST',  // 修复：使用POST方法以匹配后端
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({})  // 发送空的JSON body
      })

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }

      return response.json()
    } catch (error) {
      console.error('Failed to get tree data:', error)
      throw error
    }
  }

  async nextStep(): Promise<TaskResponse> {
    return this.post('/next-step/')
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