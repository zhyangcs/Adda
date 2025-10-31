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
}

export interface ImportanceData {
  shap: FeatureImportance[]
  ig: FeatureImportance[]
  rfe: FeatureImportance[]
  fi: FeatureImportance[]
}