<template>
  <div class="feature-generation-panel">
    <div class="info-card">
      <div class="info-header">
        <h6 class="info-title">
          <GitBranch :size="18" class="me-2" />
          Feature Generation
        </h6>
      </div>
      <div class="info-content">
        <!-- 特征树容器 -->
        <div class="tree-container mb-3">
          <div
            ref="treeContainer"
            class="tree-visualization"
            :class="{ 'is-loading': featureTreeStore.isLoading }"
          >
            <div
              v-if="!featureTreeStore.treeData && !featureTreeStore.isLoading"
              class="empty-state"
            >
              <GitBranch :size="48" class="text-muted mb-3" />
              <h6 class="text-muted">No Feature Tree Available</h6>
              <p class="text-muted small">
                Please configure and initialize a task in the Task Configuration panel first.
              </p>
              <button
                class="btn btn-primary btn-sm mt-2"
                @click="goToTaskConfig"
              >
                Go to Task Configuration
              </button>
            </div>

            <div
              v-if="featureTreeStore.isLoading"
              class="loading-state"
            >
              <div class="spinner-border text-primary" role="status">
                <span class="visually-hidden">Loading...</span>
              </div>
              <p class="mt-2 mb-0 text-muted">Loading feature tree...</p>
            </div>
          </div>
        </div>

        <!-- 当前特征信息 -->
        <div class="feature-info mb-3">
          <div class="info-item">
            <strong>Current Feature Set:</strong>
            <span
              class="features-list"
              :class="{ 'has-features': featureTreeStore.currentFeatures.length > 0 }"
            >
              {{ featureTreeDisplay }}
            </span>
          </div>
          <div class="info-item">
            <strong>Current Feature Set Performance (AUC/1-RAE):</strong>
            <span class="performance-display">
              {{ featureTreeStore.performance }}
              <div
                v-if="isPerformanceLoading"
                class="spinner-border spinner-border-sm ms-2"
                role="status"
              ></div>
            </span>
          </div>
        </div>

        <!-- 控制按钮 -->
        <div class="control-buttons mb-3">
          <div class="button-row">
            <button
              id="nextStep"
              class="btn btn-primary"
              @click="handleNextStep"
              :disabled="!taskStore.canDoNextStep || isNextStepLoading"
            >
              <div
                v-if="isNextStepLoading"
                class="spinner-border spinner-border-sm me-2"
                role="status"
              ></div>
              <Play :size="16" class="me-2" v-else />
              Next Step
            </button>

            <button
              id="testPerformance"
              class="btn btn-success"
              @click="handleTestPerformance"
              :disabled="!featureTreeStore.hasSelection || isPerformanceLoading"
            >
              <div
                v-if="isPerformanceLoading"
                class="spinner-border spinner-border-sm me-2"
                role="status"
              ></div>
              <TrendingUp :size="16" class="me-2" v-else />
              Test Performance
            </button>
          </div>

          <div class="button-row">
            <button
              id="generateModel"
              class="btn btn-warning"
              @click="handleGenerateModel"
              :disabled="!featureTreeStore.hasSelection || isModelLoading"
            >
              <div
                v-if="isModelLoading"
                class="spinner-border spinner-border-sm me-2"
                role="status"
              ></div>
              <Package :size="16" class="me-2" v-else />
              Generate & Download Model
            </button>

            <button
              class="btn btn-outline-secondary"
              @click="handleClearSelection"
              :disabled="!featureTreeStore.hasSelection"
            >
              <X :size="16" class="me-2" />
              Clear Selection
            </button>
          </div>
        </div>

        <!-- 节点信息容器 -->
        <div class="node-info-container">
          <strong>Node Information:</strong>
          <div id="nodeInfoContent" class="node-info-content">
            <div v-if="featureTreeStore.selectedNode">
              <div class="node-detail">
                <span class="node-info-label">Node ID:</span>
                <span class="node-info-value">{{ featureTreeStore.selectedNode.node_id }}</span>
              </div>
              <div class="node-detail">
                <span class="node-info-label">Feature Name:</span>
                <span class="node-info-value">{{ featureTreeStore.selectedNode.feature_name }}</span>
              </div>
              <div class="node-detail">
                <span class="node-info-label">Task Code:</span>
                <span class="node-info-value">{{ featureTreeStore.selectedNode.task_code }}</span>
              </div>
              <div class="node-detail">
                <span class="node-info-label">Operation:</span>
                <span class="node-info-value">{{ featureTreeStore.selectedNode.op_type }}</span>
              </div>
              <div class="node-detail">
                <span class="node-info-label">Description:</span>
                <span class="node-info-value">{{ featureTreeStore.selectedNode.operation_desc }}</span>
              </div>
              <div class="node-detail">
                <span class="node-info-label">Score:</span>
                <span class="node-info-value">{{ featureTreeStore.selectedNode.score.toFixed(4) }}</span>
              </div>
              <div class="node-detail">
                <span class="node-info-label">Execution Time:</span>
                <span class="node-info-value">{{ featureTreeStore.selectedNode.exec_time.toFixed(3) }}s</span>
              </div>
            </div>
            <div v-else class="text-muted">
              Hover over a node to see details.
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch, nextTick } from 'vue'
import { GitBranch, Play, TrendingUp, Package, X } from 'lucide-vue-next'
import { useTaskStore } from '@/stores/task'
import { useFeatureTreeStore } from '@/stores/featureTree'
import { useWorkspaceStore } from '@/stores/workspace'
import * as d3 from 'd3'

const taskStore = useTaskStore()
const featureTreeStore = useFeatureTreeStore()
const workspaceStore = useWorkspaceStore()

const treeContainer = ref<HTMLElement>()
const isNextStepLoading = ref(false)
const isPerformanceLoading = ref(false)
const isModelLoading = ref(false)

const featureTreeDisplay = computed(() => {
  if (featureTreeStore.currentFeatures.length === 0) {
    return 'No features selected (click node for choose/delete)'
  }
  return featureTreeStore.currentFeatures.join(', ')
})

// 监听树数据变化，重新渲染
watch(() => featureTreeStore.treeData, (newData) => {
  if (newData && treeContainer.value) {
    nextTick(() => {
      renderTree(newData)
    })
  }
}, { deep: true })

onMounted(() => {
  if (taskStore.isInitialized) {
    featureTreeStore.loadTreeData()
  }
})

function goToTaskConfig() {
  workspaceStore.switchPanel('TaskConfigPanel')
}

async function handleNextStep() {
  isNextStepLoading.value = true
  try {
    const success = await taskStore.nextStep()
    if (success) {
      await featureTreeStore.loadTreeData()
      taskStore.addNotification('Next step completed successfully', 'success')
    } else {
      taskStore.addNotification('Failed to execute next step', 'fail')
    }
  } finally {
    isNextStepLoading.value = false
  }
}

async function handleTestPerformance() {
  isPerformanceLoading.value = true
  try {
    const success = await featureTreeStore.testPerformance()
    if (success) {
      taskStore.addNotification('Performance test completed', 'success')
    } else {
      taskStore.addNotification('Failed to test performance', 'fail')
    }
  } finally {
    isPerformanceLoading.value = false
  }
}

async function handleGenerateModel() {
  isModelLoading.value = true
  try {
    const success = await featureTreeStore.generateModel()
    if (success) {
      taskStore.addNotification('Model generated and downloaded successfully', 'success')
    } else {
      taskStore.addNotification('Failed to generate model', 'fail')
    }
  } finally {
    isModelLoading.value = false
  }
}

function handleClearSelection() {
  featureTreeStore.clearSelection()
  taskStore.addNotification('Selection cleared', 'info')
}

// D3.js 树形图渲染
function renderTree(treeStructure: any) {
  if (!treeContainer.value) return

  // 清空容器
  d3.select(treeContainer.value).selectAll("*").remove()

  let { root_id, parent_child_relations, node_info, cur_selected_idx } = treeStructure

  // 将节点信息转换为字典
  const nodeInfoMap = node_info.reduce((map: any, info: any) => {
    map[info.node_id] = info
    return map
  }, {})

  // 构建树结构
  function buildTree(rootId: string, relations: [string, string][], nodeInfoMap: any) {
    const tree = {
      id: rootId,
      ...nodeInfoMap[rootId],
      children: [],
      selected: cur_selected_idx.includes(rootId)
    }
    const nodeMap: { [key: string]: any } = { [rootId]: tree }

    parent_child_relations.forEach(([parent_id, child_id]) => {
      const parentNode = nodeMap[parent_id]
      const childNode = {
        id: child_id,
        ...nodeMap[child_id],
        children: [],
        selected: cur_selected_idx.includes(child_id)
      }
      parentNode.children.push(childNode)
      nodeMap[child_id] = childNode
    })

    return tree
  }

  const data = buildTree(root_id, parent_child_relations, nodeInfoMap)
  renderD3Tree(data)
}

function renderD3Tree(data: any) {
  if (!treeContainer.value) return

  // 创建树布局
  const treeLayout = d3.tree()
    .size([800, 350])
    .separation(() => 1)

  // 创建SVG容器
  const svg = d3.select(treeContainer.value)
    .append("svg")
    .attr("width", "100%")
    .attr("height", 400)
    .attr("viewBox", "0 0 850 400")
    .append("g")
    .attr("transform", "translate(0, 25)")

  // 创建层次结构
  const root = d3.hierarchy(data)
  treeLayout(root)

  // 绘制连接线
  const links = svg.selectAll(".link")
    .data(root.links())
    .enter()
    .append("path")
    .attr("class", "link")
    .attr("d", d3.linkVertical()
      .x((d: any) => d.x)
      .y((d: any) => d.y))

  // 创建节点组
  const nodes = svg.selectAll(".node")
    .data(root.descendants())
    .enter()
    .append("g")
    .attr("class", "node")
    .attr("transform", (d: any) => `translate(${d.x},${d.y})`)
    .classed("selected", (d: any) => d.data.selected)
    .on("click", function (event, d: any) {
      handleNodeClick(d.data)
    })
    .on("mouseover", function (event, d: any) {
      showNodeInfo(d.data)
    })
    .on("mouseout", hideNodeInfo)

  // 绘制节点矩形
  nodes.append("rect")
    .attr("width", 180)
    .attr("height", 35)
    .attr("x", -90)
    .attr("y", -20)
    .attr("fill", (d: any) => d.data.selected ? "#2ecc71" : "#c8c8c8")
    .attr("stroke", "#b4b4b4")
    .attr("stroke-width", 2)
    .attr("rx", 6)
    .on("mouseover", function (event, d: any) {
      d3.select(this).attr("fill", d.data.selected ? "#27ae60" : "#b4b4b4")
    })
    .on("mouseout", function (event, d: any) {
      d3.select(this).attr("fill", d.data.selected ? "#2ecc71" : "#c8c8c8")
    })

  // 添加节点文字
  nodes.append("text")
    .attr("dy", -6)
    .style("font-weight", "bold")
    .style("font-size", "12px")
    .text((d: any) => `${d.data.feature_name}`)

  nodes.append("text")
    .attr("dy", 10)
    .style("font-weight", "bold")
    .text((d: any) => `ID: ${d.data.node_id}`)

  // 设置根节点引用
  featureTreeStore.setRoot(root)
}

function handleNodeClick(nodeData: any) {
  featureTreeStore.toggleNodeSelection(nodeData.node_id)
  // 重新渲染树以更新选中状态
  if (featureTreeStore.treeData) {
    renderTree(featureTreeStore.treeData)
  }
}

function showNodeInfo(nodeData: any) {
  featureTreeStore.setSelectedNode(nodeData)
}

function hideNodeInfo() {
  featureTreeStore.setSelectedNode(null)
}
</script>

<style scoped>
.feature-generation-panel {
  height: 100%;
  overflow: hidden;
}

.info-card {
  height: 100%;
  background-color: var(--bg-secondary);
  border-radius: 8px;
  border: 1px solid var(--border-color);
  display: flex;
  flex-direction: column;
  box-shadow: var(--shadow-sm);
  /* 确保样式优先级 */
  background-color: #fafafa !important;
  border: 1px solid #e0e0e0 !important;
}

.info-header {
  padding: var(--spacing-md) var(--spacing-lg);
  border-bottom: 1px solid var(--border-color);
  background-color: var(--bg-primary);
  border-radius: 8px 8px 0 0;
  /* 确保样式优先级 */
  background-color: #ffffff !important;
  border-bottom: 1px solid #e0e0e0 !important;
}

.info-title {
  color: var(--text-primary);
  font-weight: 600;
  margin: 0;
  font-size: var(--font-size-md);
  display: flex;
  align-items: center;
}

.info-content {
  flex: 1;
  padding: 1rem;
  overflow-y: auto;
}

.tree-container {
  background-color: #f0f0f0;
  border-radius: 8px;
  padding: 1rem;
  min-height: 400px;
  position: relative;
}

.tree-visualization {
  height: 400px;
  overflow: auto;
}

.empty-state,
.loading-state {
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: #6c757d;
}

.feature-info {
  background-color: #f8f9fa;
  border-radius: 6px;
  padding: 1rem;
}

.info-item {
  display: flex;
  align-items: center;
  margin-bottom: 0.5rem;
  flex-wrap: wrap;
}

.info-item strong {
  min-width: 280px;
  margin-right: 0.5rem;
}

.features-list {
  padding: 0.25rem 0.5rem;
  border-radius: 4px;
  background-color: #e9ecef;
  color: #333333;
  font-weight: 500;
  font-size: 0.9rem;
  flex: 1;
}

.features-list.has-features {
  background-color: #d4edda;
  color: #155724;
}

.performance-display {
  display: flex;
  align-items: center;
  color: #007bff;
  font-weight: 600;
}

.control-buttons {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.button-row {
  display: flex;
  gap: 0.75rem;
  flex-wrap: wrap;
}

.button-row button {
  flex: 1;
  min-width: 150px;
}

.node-info-container {
  background-color: #f8f9fa;
  border-radius: 6px;
  padding: 1rem;
  margin-top: auto;
  max-height: 200px;
  overflow-y: auto;
}

.node-info-content {
  margin-top: 0.5rem;
}

.node-detail {
  display: flex;
  margin-bottom: 0.25rem;
  align-items: flex-start;
}

.node-info-label {
  font-weight: 600;
  color: #495057;
  min-width: 120px;
  margin-right: 0.5rem;
}

.node-info-value {
  color: #6c757d;
  word-break: break-word;
  flex: 1;
}

.btn {
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 500;
  transition: all 0.2s ease-in-out;
}

.btn:hover:not(:disabled) {
  transform: translateY(-1px);
}

.btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

/* D3.js 样式 */
:deep(.link) {
  fill: none;
  stroke: #666;
  stroke-width: 1.5px;
}

:deep(.node) {
  cursor: pointer;
}

:deep(.node.selected rect) {
  stroke: #27ae60;
  stroke-width: 3px;
}

:deep(.node rect) {
  stroke: #b4b4b4;
  stroke-width: 2px;
  transition: all 0.2s ease;
}

:deep(.node:hover rect) {
  filter: brightness(0.9);
}

:deep(.node text) {
  pointer-events: none;
  user-select: none;
}

/* 响应式设计 */
@media (max-width: 768px) {
  .info-item {
    flex-direction: column;
    align-items: flex-start;
  }

  .info-item strong {
    min-width: auto;
    margin-bottom: 0.25rem;
  }

  .button-row {
    flex-direction: column;
  }

  .button-row button {
    min-width: auto;
  }
}
</style>
