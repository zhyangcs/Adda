export interface TaskConfig {
  description: string
  dataset: string
  model: string
  /** Downstream ML model used for training/evaluation (e.g., RF/XGB/LightGBM) */
  mlModel: string
}

export type TaskStatus = 'idle' | 'initializing' | 'running' | 'completed' | 'error'

export interface TaskResponse {
  status: 'success' | 'fail'
  message: string
  data?: AutoStepData
}

export interface AutoStepData {
  // === 端到端模式数据结构 ===

  // 特征信息 (支持 FeatureInfoPanel 组件)
  featureInfo?: {
    description?: string
    pythonCode?: string
    sqlCode?: string
  }

  // 性能对比数据 (支持 PerformanceComparisonChart 组件)
  performanceData?: {
    methods?: string[]
    auc?: number[]
    f1?: number[]
    accuracy?: number[]
    precision?: number[]
    recall?: number[]
  }

  // 时间分析数据 (支持 TimeComparisonChart 组件)
  timeData?: {
    methods?: string[]
    totalTime?: number[]      // 秒
    trainingTime?: number[]   // 秒
    preprocessingTime?: number[]
    featureGenerationTime?: number[]
    evaluationTime?: number[]
  }

  // 特征重要性数据 (支持 FeatureImportancePanel 组件)
  importanceData?: {
    shap?: FeatureImportanceItem[]
    ig?: FeatureImportanceItem[]
    rfe?: FeatureImportanceItem[]
    fi?: FeatureImportanceItem[]
  }

  // === 其他后端返回字段 ===
  status?: string
  message?: string
  tree?: string
  finished?: boolean
  search_depth?: number
  performance_metrics?: any
  sql_code?: any
  best_features?: any
  training_result?: any

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
