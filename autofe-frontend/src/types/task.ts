export interface TaskConfig {
  description: string
  dataset: string
  model: string
}

export type TaskStatus = 'idle' | 'initializing' | 'running' | 'completed' | 'error'

export interface TaskResponse {
  status: 'success' | 'fail'
  message: string
  data?: AutoStepData
}

export interface AutoStepData {
  featureDescription?: string
  pythonCode?: string
  sqlCode?: string
  performance?: PerformanceData
  timeAnalysis?: TimeAnalysisData
  featureImportance?: FeatureImportanceData
  // 其他可能的返回数据
  [key: string]: any
}

export interface PerformanceData {
  methods: string[]
  auc: number[]
  f1: number[]
  accuracy?: number[]
  precision?: number[]
  recall?: number[]
}

export interface TimeAnalysisData {
  methods: string[]
  totalTime: number[]  // 秒
  trainingTime: number[]  // 秒
  preprocessingTime?: number[]
  featureGenerationTime?: number[]
  evaluationTime?: number[]
}

export interface FeatureImportanceData {
  shap?: FeatureImportanceItem[]
  ig?: FeatureImportanceItem[]
  rfe?: FeatureImportanceItem[]
  fi?: FeatureImportanceItem[]
}

export interface FeatureImportanceItem {
  feature: string
  importance: number
}

export interface Notification {
  id: string
  notice_description: string
  notice_type: 'success' | 'fail' | 'info'
  timestamp: Date
}