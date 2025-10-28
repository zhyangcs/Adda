export interface TreeNode {
  node_id: string
  feature_name: string
  task_code: string
  op_type: string
  score: number
  exec_time: number
  operation_desc: string
  selected?: boolean
}

export interface FeatureTreeData {
  root_id: string
  parent_child_relations: [string, string][]
  node_info: TreeNode[]
  cur_selected_idx: string[]
}

export interface FeatureTreeResponse {
  status: 'success' | 'fail'
  json: FeatureTreeData
  message?: string
}

export interface PerformanceResponse {
  status: 'success' | 'fail'
  message: string
}