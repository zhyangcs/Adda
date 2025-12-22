export interface TaskConfig {
  description: string
  dataset: string
  model: string
  /** Downstream ML model used for training/evaluation (e.g., RF/XGB/LightGBM) */
  mlModel: string
  /** Comparison methods to run alongside Adda (Adda always runs by default) */
  comparisonMethods: string[]
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

export interface Py2SqlAstNode {
  type: string
  id?: string
  attr?: string
  value?: any
  func?: string
  truncated?: boolean
  targets?: string[]
  children?: Py2SqlAstNode[]
}

export interface Py2SqlSemanticNode {
  type: 'operator' | 'udf'
  displayName: string
  inputs: string[]
  outputs: string[]
  parameters?: Record<string, any>
  color?: string
  sqlConvertible?: boolean
}

export interface Py2SqlSemanticAstView {
  summaryNode: Py2SqlSemanticNode
  previewAst?: Py2SqlAstNode
  rawAst?: Py2SqlAstNode
  edges?: { from: string; to: string }[]
  drillDownAvailable?: boolean
}

export interface Py2SqlAstBlock {
  nodeId?: number | null
  opType: string
  opParameters?: Record<string, any>
  readColumns: string[]
  writeColumns: string[]
  sqlSnippet?: string
  code: string
  ast: Py2SqlAstNode
  semanticNode?: Py2SqlSemanticNode
  semanticAst?: Py2SqlSemanticAstView
  executionError?: string
}

export interface Py2SqlAstData {
  dataset: string
  mlModel: string
  pipelinePath: string
  columns: string[]
  preCode?: string
  curStatesPath?: string | null
  storeDir?: string | null
  pipelineSource?: 'pipes' | 'scan'
  pipelineFromPipes?: boolean
  curStatesLoaded?: boolean
  sqlGenerationMeta?: Record<string, any>
  finalSql?: string
  finalSqlPath?: string
  finalSqlFound?: boolean
  finalSqlGenerated?: boolean
  finalSqlError?: string
  blocks: Py2SqlAstBlock[]
}

export interface Py2SqlAstResponse {
  status: 'success' | 'fail'
  message?: string
  data?: Py2SqlAstData
}

export interface Py2SqlDagSnippet {
  cte?: string
  sql: string
}

export interface Py2SqlDagNode {
  nodeId: number
  cteName: string
  opType: string
  readColumns: string[]
  writeColumns: string[]
  pythonCode?: string
  sqlSnippets?: Py2SqlDagSnippet[]
  udfSnippets?: string[]
}

export interface Py2SqlDagEdge {
  from: number
  to: number
}

export interface Py2SqlDagData {
  nodes: Py2SqlDagNode[]
  edges: Py2SqlDagEdge[]
  meta?: Record<string, any>
}

export interface Py2SqlDagResponse {
  status: 'success' | 'fail'
  message?: string
  data?: Py2SqlDagData
}
