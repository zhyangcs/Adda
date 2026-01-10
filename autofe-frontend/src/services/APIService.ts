import type {
  TaskConfig,
  TaskResponse,
  FeatureTreeResponse,
  PerformanceResponse,
  Notification,
  Py2SqlAstResponse,
  Py2SqlDagResponse
} from '@/types'

class APIService {
  private baseURL = (() => {
    const viteBase =
      (typeof import.meta !== 'undefined' && (import.meta as any).env?.VITE_API_BASE_URL) ||
      ''
    if (viteBase && typeof viteBase === 'string') {
      return viteBase.trim()
    }

    // Default to same hostname + port 5000 (common dev setup: frontend on :5173, backend on :5000).
    if (typeof window !== 'undefined' && window.location) {
      const protocol = window.location.protocol === 'https:' ? 'https:' : 'http:'
      const host = window.location.hostname || '127.0.0.1'
      return `${protocol}//${host}:5000`
    }

    return 'http://127.0.0.1:5000'
  })()

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
    formData.append('ml_model_type', config.mlModel || 'RF')

    const response = await fetch(`${this.baseURL}/check-format/`, {
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

  async testPerformance(nodeIds: string[], modelType?: string, useInDbMl: boolean = true): Promise<PerformanceResponse> {
    return this.post('/test-performance/', {
      selectedNodeIds: nodeIds,
      modelType: modelType || 'RF',
      useInDbMl
    })
  }

  async generateModel(nodeIds: string[]): Promise<Blob> {
    const response = await fetch(`${this.baseURL}/gen-model/`, {
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
    const response = await fetch(`${this.baseURL}/get-notifications/`, {
      method: 'GET'
    })

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`)
    }

    return response.json()
  }

  async runAutoPipeline(config?: TaskConfig): Promise<TaskResponse> {
    if (config) {
      // 调试：打印配置信息
      console.log('PerformanceEvaluation API Call - Config:', {
        description: config.description,
        descriptionLength: config.description?.length || 0,
        dataset: config.dataset,
        model: config.model
      })

      // 传入任务配置，与checkFormat相同的逻辑
      const formData = new FormData()

      const description = (config.description || '').trim()
      if (description) {
        formData.append('taskDescription', description)
      }

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
      formData.append('ml_model_type', config.mlModel || 'RF')
      formData.append('comparison_methods', JSON.stringify(config.comparisonMethods || []))

      const response = await fetch(`${this.baseURL}/performance-evaluation/`, {
        method: 'POST',
        body: formData
      })

      return response.json()
    } else {
      return this.post('/performance-evaluation/')
    }
  }

  async getPy2SqlAst(payload: { dataset: string, mlModel: string, pipelineId?: string }): Promise<Py2SqlAstResponse> {
    return this.post('/py2sql-ast/', payload, 2 * 60 * 1000)
  }

  async getPy2SqlDag(payload: { dataset: string, mlModel: string, pipelineId?: string }): Promise<Py2SqlDagResponse> {
    return this.post('/py2sql-dag/', payload, 2 * 60 * 1000)
  }

  // 可暂停/恢复的特征搜索（demo LLMDagConstructor）
  async featureSearchStart(payload: { dataset: string; modelType: string; depth?: number; forceNew?: boolean; resume?: boolean }) {
    return this.post('/feature-search/start/', payload, 15 * 60 * 1000)
  }

  async featureSearchPause() {
    return this.post('/feature-search/pause/')
  }

  async featureSearchResume() {
    return this.post('/feature-search/resume/')
  }

  async featureSearchStop() {
    return this.post('/feature-search/stop/')
  }

  async featureSearchStatus() {
    const response = await fetch(`${this.baseURL}/feature-search/status/`, {
      method: 'GET'
    })
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`)
    }
    return response.json()
  }
}

export const apiService = new APIService()
