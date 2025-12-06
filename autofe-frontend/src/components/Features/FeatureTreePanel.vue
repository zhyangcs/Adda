<template>
  <div class="feature-tree-panel">
    <div class="info-card">
      <div class="info-header">
        <h6 class="info-title">
          <GitBranch :size="18" class="me-2" />
          Feature Generation
        </h6>
      </div>
      <div class="info-content">
        <div class="feature-tree-container">
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
                Please configure and initialize a task first.
              </p>
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

        <!-- 特征选择信息（简化显示） -->
        <div class="feature-selection-info">
          <div class="feature-list">
            <div v-if="featureTreeStore.currentFeatures.length === 0" class="no-features">
              <span class="feature-label">Current Feature Set:</span> No features selected (click node for choose/delete)
            </div>
            <div v-else class="features-container">
              <span class="feature-label">Current Feature Set:</span>
              <span class="features-text">{{ featureTreeStore.currentFeatures.join(', ') }}</span>
            </div>
          </div>
          <div class="performance-info">
            <strong>Performance:</strong>
            <span class="performance-value">{{ featureTreeStore.performance }}</span>
            <div v-if="isPerformanceLoading" class="spinner-border spinner-border-sm ms-2"></div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { GitBranch } from 'lucide-vue-next'
import { useFeatureTreeStore } from '@/stores/featureTree'
import * as d3 from 'd3'

const featureTreeStore = useFeatureTreeStore()
const treeContainer = ref<HTMLElement>()
const isPerformanceLoading = ref(false)

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
  function buildTree(rootId: string, _relations: [string, string][], nodeInfoMap: any) {
    const tree = {
      id: rootId,
      ...nodeInfoMap[rootId],
      children: [],
      selected: cur_selected_idx.includes(rootId)
    }
    const nodeMap: { [key: string]: any } = { [rootId]: tree }

    parent_child_relations.forEach(([parent_id, child_id]: [string, string]) => {
      const parentNode = nodeMap[parent_id]
      const childNode = {
        id: child_id,
        ...nodeInfoMap[child_id],
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
    .size([280, 200])
    .separation(() => 1)

  // 创建SVG容器
  const svg = d3.select(treeContainer.value)
    .append("svg")
    .attr("width", "100%")
    .attr("height", 250)
    .attr("viewBox", "0 0 300 250")
    .append("g")
    .attr("transform", "translate(10, 25)")

  // 创建层次结构
  const root = d3.hierarchy(data)
  treeLayout(root)

  // 绘制连接线
  svg.selectAll(".link")
    .data(root.links())
    .enter()
    .append("path")
    .attr("class", "link")
    .attr("d", d3.linkVertical<any, d3.HierarchyNode<any>>()
      .x((d: any) => d.x)
      .y((d: any) => d.y) as any)

  // 创建节点组
  const nodes = svg.selectAll(".node")
    .data(root.descendants())
    .enter()
    .append("g")
    .attr("class", "node")
    .attr("transform", (d: any) => `translate(${d.x},${d.y})`)
    .classed("selected", (d: any) => d.data.selected)
    .on("click", function (_event: any, d: any) {
      handleNodeClick(d.data)
    })
    .on("mouseover", function (_event: any, d: any) {
      showNodeInfo(d.data)
    })
    .on("mouseout", hideNodeInfo)

  // 绘制节点矩形
  nodes.append("rect")
    .attr("width", 80)
    .attr("height", 30)
    .attr("x", -40)
    .attr("y", -15)
    .attr("fill", (d: any) => d.data.selected ? "#2ecc71" : "#c8c8c8")
    .attr("stroke", "#b4b4b4")
    .attr("stroke-width", 2)
    .attr("rx", 4)
    .on("mouseover", function (_event: any, d: any) {
      d3.select(this).attr("fill", d.data.selected ? "#27ae60" : "#b4b4b4")
    })
    .on("mouseout", function (_event: any, d: any) {
      d3.select(this).attr("fill", d.data.selected ? "#2ecc71" : "#c8c8c8")
    })

  // 添加节点文字
  nodes.append("text")
    .attr("dy", -5)
    .style("font-weight", "bold")
    .style("font-size", "10px")
    .text((d: any) => `${d.data.feature_name?.substring(0, 8) || ''}`)

  nodes.append("text")
    .attr("dy", 8)
    .style("font-size", "9px")
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

// 监听树数据变化，重新渲染
watch(() => featureTreeStore.treeData, (newData) => {
  if (newData && treeContainer.value) {
    nextTick(() => {
      renderTree(newData)
    })
  }
}, { deep: true })

onMounted(() => {
  if (featureTreeStore.treeData && treeContainer.value) {
    nextTick(() => {
      renderTree(featureTreeStore.treeData)
    })
  }
})
</script>

<style scoped>
.feature-tree-panel {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.info-card {
  height: 100%;
  background-color: #fff;
  border-radius: 12px;
  border: none;
  display: flex;
  flex-direction: column;
  box-shadow: none;
}

.info-header {
  padding: 10px 14px;
  border-bottom: 2px solid var(--accent-blue, #2a7de1);
  background-color: transparent;
  border-radius: 12px 12px 0 0;
}

.info-title {
  color: var(--text-primary);
  font-weight: 600;
  margin: 0;
  font-size: var(--font-size-lg);
  display: flex;
  align-items: center;
}

.info-content {
  flex: 1;
  padding: 0.85rem;
  overflow-y: auto;
}

.feature-tree-container {
  height: 75%; /* 减少到原来的3/4 */
  background-color: #f7f9fc;
  border-radius: 10px;
  border: none;
  padding: 0.6rem;
  min-height: 150px; /* 相应减少最小高度 */
}

.tree-visualization {
  height: 100%;
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

/* 特征选择信息样式（简化显示） */
.feature-selection-info {
  margin-top: 0.8rem;
  padding: 0.7rem 0.9rem;
  border: none;
  border-radius: 8px;
  background-color: #fff;
  box-shadow: none;
}

.feature-list {
  margin-bottom: 1rem;
}

.no-features {
  color: #6c757d;
  font-style: italic;
}

.feature-label {
  color: #495057;
  font-weight: 500;
}

.features-container {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.25rem;
}

.features-text {
  color: #155724;
  background-color: #d4edda;
  padding: 0.5rem;
  border-radius: 4px;
  font-weight: 500;
  line-height: 1.4;
}

.performance-info {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.performance-value {
  color: #007bff;
  font-weight: 600;
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
  stroke-width: 2px;
}

:deep(.node rect) {
  transition: all 0.2s ease;
}

:deep(.node:hover rect) {
  filter: brightness(0.9);
}

:deep(.node text) {
  pointer-events: none;
  user-select: none;
}
</style>
