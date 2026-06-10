import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { TreeNode, FeatureTreeData } from '@/types/featureTree'
import { apiService } from '@/services/APIService'

export const useFeatureTreeStore = defineStore('featureTree', () => {
  // 状态
  const treeData = ref<FeatureTreeData | null>(null)
  const selectedNodes = ref<Set<string>>(new Set())
  const selectedNode = ref<TreeNode | null>(null)
  const currentFeatures = ref<string[]>([])
  const performance = ref<string>('not calculated yet')
  const isLoading = ref(false)
  const root = ref<any>(null)

  // 计算属性
  const selectedNodeIds = computed(() => Array.from(selectedNodes.value))

  const selectedFeatureNames = computed(() => {
    if (!treeData.value) return []
    return selectedNodeIds.value.map(id => {
      const node = findNodeById(treeData.value!, id)
      return node?.feature_name || ''
    }).filter(Boolean)
  })

  const hasSelection = computed(() => selectedNodes.value.size > 0)

  // 方法
  function findNodeById(treeData: FeatureTreeData, nodeId: string): TreeNode | null {
    const nodeMap = treeData.node_info.find(node => node.node_id === nodeId)
    return nodeMap || null
  }

  async function loadTreeData() {
    try {
      isLoading.value = true
      const response = await apiService.getTreeData()

      if (response.status === 'success') {
        treeData.value = response.json
        console.log('[TREE LOAD] success root:', response.json?.root_id, 'nodes:', response.json?.node_info?.length || 0, 'edges:', response.json?.parent_child_relations?.length || 0)
        selectedNode.value = null
        // 更新选中状态
        updateSelectionFromTree()
      } else {
        console.warn('[TREE LOAD] failed status:', response.status, 'msg:', (response as any)?.message)
      }
    } catch (error) {
      console.error('加载树数据失败:', error)
    } finally {
      isLoading.value = false
    }
  }

  function updateSelectionFromTree() {
    if (!treeData.value) return

    selectedNodes.value.clear()
    treeData.value.cur_selected_idx.forEach(nodeId => {
      selectedNodes.value.add(nodeId)
    })
    updateCurrentFeatures()
  }

  function toggleNodeSelection(nodeId: string) {
    if (selectedNodes.value.has(nodeId)) {
      selectedNodes.value.delete(nodeId)
    } else {
      selectedNodes.value.add(nodeId)
    }
    updateCurrentFeatures()

    // 更新树数据中的选中状态
    if (treeData.value) {
      const index = treeData.value.cur_selected_idx.indexOf(nodeId)
      if (index > -1) {
        treeData.value.cur_selected_idx.splice(index, 1)
      } else {
        treeData.value.cur_selected_idx.push(nodeId)
      }
    }
  }

  function updateCurrentFeatures() {
    currentFeatures.value = selectedFeatureNames.value
  }

  function clearSelection() {
    selectedNodes.value.clear()
    selectedNode.value = null
    currentFeatures.value = []
    if (treeData.value) {
      treeData.value.cur_selected_idx = []
    }
  }

  function clearFeatureOutput() {
    treeData.value = null
    root.value = null
    selectedNodes.value.clear()
    selectedNode.value = null
    currentFeatures.value = []
    performance.value = 'not calculated yet'
    isLoading.value = false
  }

  async function testPerformance(modelType?: string): Promise<boolean> {
    if (!hasSelection.value) return false

    try {
      const response = await apiService.testPerformance(selectedNodeIds.value, modelType)
      if (response.status === 'success') {
        performance.value = response.message
        return true
      }
      return false
    } catch (error) {
      console.error('性能测试失败:', error)
      return false
    }
  }

  async function generateModel(): Promise<boolean> {
    if (!hasSelection.value) return false

    try {
      const blob = await apiService.generateModel(selectedNodeIds.value)
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = 'model.pkl'
      document.body.appendChild(a)
      a.click()
      window.URL.revokeObjectURL(url)
      document.body.removeChild(a)
      return true
    } catch (error) {
      console.error('模型生成失败:', error)
      return false
    }
  }

  function setRoot(rootValue: any) {
    root.value = rootValue
  }

  function setSelectedNode(node: TreeNode | null) {
    selectedNode.value = node
  }

  return {
    // 状态
    treeData,
    selectedNodes,
    selectedNode,
    currentFeatures,
    performance,
    isLoading,
    root,

    // 计算属性
    selectedNodeIds,
    selectedFeatureNames,
    hasSelection,

    // 方法
    loadTreeData,
    toggleNodeSelection,
    updateSelectionFromTree,
    updateCurrentFeatures,
    clearSelection,
    clearFeatureOutput,
    testPerformance,
    generateModel,
    setRoot,
    setSelectedNode,
    findNodeById
  }
})
