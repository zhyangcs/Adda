// 端到端分析页面类型定义

export interface FeatureInfo {
  description: string
  pythonCode: string
  sqlCode: string
}

export interface PerformanceData {
  methods: string[]
  auc: number[]
  f1: number[]
}

export interface TimeData {
  methods: string[]
  totalTime: number[]  // 秒
  trainingTime: number[]  // 秒
}

export interface FeatureImportance {
  feature: string
  importance: number
  rawImportance?: number  // 保存原始值用于显示
  scalingFactor?: number  // 记录缩放因子
  isGenerated?: boolean   // 标记是否为新生成特征
}

// Paper Metrics 相关类型定义
export interface TopKFeatureAnalysis {
  rank: number
  feature: string
  importance: number
  is_generated: boolean
}

export interface TopKAnalysis {
  percentage: number
  generated_count: number
  total_count: number
  top_features_analysis: TopKFeatureAnalysis[]
  top_features: string[]
  importances: number[]
  error?: string
}

export interface MethodMetrics {
  feature_importance: Record<string, number>
  method: string
  error?: string
}

export interface PaperMetrics {
  task_name: string
  original_feature_count: number
  generated_feature_count: number
  total_feature_count: number
  top_k: number
  metrics: Record<string, MethodMetrics>
  top_k_analysis: Record<string, TopKAnalysis>
  all_features: {
    original: string[]
    generated: string[]
    target: string
  }
  data_shape: [number, number]
  success: boolean
  error?: string
}

export interface ImportanceData {
  shap: FeatureImportance[]
  ig: FeatureImportance[]
  rfe: FeatureImportance[]
  fi: FeatureImportance[]
  // 新增 paper metrics 数据
  paperMetrics?: PaperMetrics
}