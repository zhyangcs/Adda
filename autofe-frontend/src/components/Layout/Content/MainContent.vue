<template>
  <div class="main-content">
    <!-- 上方区域：Agent思考过程 + 特征搜索树 -->
    <div class="upper-section">
      <!-- 左侧：Agent协作流程图 -->
      <div class="agent-flow-section">
        <div class="section-header">
          <h6 class="section-title">
            <Users :size="18" class="me-2" />
            Agent Thinking Process
          </h6>
        </div>

        <div class="agent-flow-diagram">
          <!-- 环形布局的Agent协作图 -->
          <div class="flow-container">
            <!-- 中心标题 -->
            <div class="flow-center">
              <div class="flow-title">Agent Flow</div>
              <div class="flow-status">{{ getCurrentFlowStatus() }}</div>
            </div>

            <!-- Agent图标环形布局 -->
            <div class="agents-container">
              <!-- Main Agent -->
              <div
                class="agent-node main-agent"
                :class="{ active: activeAgent === 'main', working: workingAgents.includes('main') }"
                @click="setActiveAgent('main')"
              >
                <div class="agent-icon">
                  <img src="/demo_main.png" alt="Main Agent" class="agent-image" />
                </div>
                <div class="agent-label">Main Agent</div>
                <div class="agent-goal">Feature Engineering</div>
                <div v-if="workingAgents.includes('main')" class="working-indicator"></div>
              </div>

              <!-- Optimization Agent -->
              <div
                class="agent-node opt-agent"
                :class="{ active: activeAgent === 'optimization', working: workingAgents.includes('optimization') }"
                @click="setActiveAgent('optimization')"
              >
                <div class="agent-icon">
                  <img src="/demo_opt.png" alt="Optimization Agent" class="agent-image" />
                </div>
                <div class="agent-label">Opt Agent</div>
                <div class="agent-goal">Performance Tuning</div>
                <div v-if="workingAgents.includes('optimization')" class="working-indicator"></div>
              </div>

              <!-- Node Validation Process -->
              <div
                class="agent-node validation-agent"
                :class="{ active: activeAgent === 'validation', working: workingAgents.includes('validation') }"
                @click="setActiveAgent('validation')"
              >
                <div class="agent-icon">
                  <Cog :size="32" />
                </div>
                <div class="agent-label">Node Validation</div>
                <div class="agent-goal">Feature Validation</div>
                <div v-if="workingAgents.includes('validation')" class="working-indicator"></div>
              </div>

              <!-- 连接线 - L型循环 -->
              <svg class="connection-lines" viewBox="0 0 500 400">
                <!-- 定义箭头 -->
                <defs>
                  <marker
                    id="arrowhead-main-opt"
                    markerWidth="10"
                    markerHeight="7"
                    refX="9"
                    refY="3.5"
                    orient="auto"
                  >
                    <polygon
                      points="0 0, 10 3.5, 0 7"
                      :fill="connectionActive ? '#007bff' : '#dee2e6'"
                    />
                  </marker>
                  <marker
                    id="arrowhead-opt-validation"
                    markerWidth="10"
                    markerHeight="7"
                    refX="9"
                    refY="3.5"
                    orient="auto"
                  >
                    <polygon
                      points="0 0, 10 3.5, 0 7"
                      :fill="connectionActiveReverse ? '#007bff' : '#dee2e6'"
                    />
                  </marker>
                  <marker
                    id="arrowhead-validation-main"
                    markerWidth="10"
                    markerHeight="7"
                    refX="9"
                    refY="3.5"
                    orient="auto"
                  >
                    <polygon
                      points="0 0, 10 3.5, 0 7"
                      :fill="connectionActiveValidation ? '#007bff' : '#dee2e6'"
                    />
                  </marker>
                </defs>

                <!-- Main to Opt (straight arrow: from right edge of Main icon to left edge of Opt icon) -->
                <path
                  d="M 130 85 L 370 85"
                  class="connection-line"
                  :class="{ active: connectionActive }"
                  marker-end="url(#arrowhead-main-opt)"
                />

                <!-- Opt to Validation (polyline: from bottom edge of Opt to left edge of Validation) -->
                <path
                  d="M 420 145 L 420 230 A 50 50 0 0 1 370 280 L 130 280"
                  class="connection-line curved"
                  :class="{ active: connectionActiveReverse }"
                  marker-end="url(#arrowhead-opt-validation)"
                />

                <!-- Validation to Main (straight arrow: from top edge of Validation to bottom edge of Main) -->
                <path
                  d="M 85 280 L 85 170"
                  class="connection-line"
                  :class="{ active: connectionActiveValidation }"
                  marker-end="url(#arrowhead-validation-main)"
                />
              </svg>
            </div>
          </div>
        </div>
      </div>

      <!-- 右侧：特征搜索树可视化 -->
      <div class="feature-tree-section">
        <div class="section-header">
          <h6 class="section-title">
            <GitBranch :size="18" class="me-2" />
            Feature Generation - 特征搜索树可视化
          </h6>
        </div>

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
      </div>
    </div>

    <!-- 下方区域：当前特征集和节点信息 -->
    <div class="lower-section">
      <!-- 当前特征集信息 -->
      <div class="current-features-section">
        <div class="info-card">
          <div class="info-header">
            <h6 class="info-title">Current Feature Set</h6>
          </div>
          <div class="info-content">
            <div class="feature-list">
              <span v-if="featureTreeStore.currentFeatures.length === 0" class="no-features">
                No features selected (click node for choose/delete)
              </span>
              <span v-else class="features-text">
                {{ featureTreeStore.currentFeatures.join(', ') }}
              </span>
            </div>
            <div class="performance-info">
              <strong>Performance:</strong>
              <span class="performance-value">{{ featureTreeStore.performance }}</span>
              <div v-if="isPerformanceLoading" class="spinner-border spinner-border-sm ms-2"></div>
            </div>
          </div>
        </div>
      </div>

      <!-- 节点信息面板 -->
      <div class="node-info-section">
        <div class="info-card">
          <div class="info-header">
            <h6 class="info-title">Node Information</h6>
          </div>
          <div class="info-content">
            <div v-if="featureTreeStore.selectedNode" class="node-details">
              <div class="node-detail">
                <span class="detail-label">Node ID:</span>
                <span class="detail-value">{{ featureTreeStore.selectedNode.node_id }}</span>
              </div>
              <div class="node-detail">
                <span class="detail-label">Feature Name:</span>
                <span class="detail-value">{{ featureTreeStore.selectedNode.feature_name }}</span>
              </div>
              <div class="node-detail">
                <span class="detail-label">Task Code:</span>
                <span class="detail-value">{{ featureTreeStore.selectedNode.task_code }}</span>
              </div>
              <div class="node-detail">
                <span class="detail-label">Operation:</span>
                <span class="detail-value">{{ featureTreeStore.selectedNode.op_type }}</span>
              </div>
              <div class="node-detail">
                <span class="detail-label">Description:</span>
                <span class="detail-value">{{ featureTreeStore.selectedNode.operation_desc }}</span>
              </div>
              <div class="node-detail">
                <span class="detail-label">Score:</span>
                <span class="detail-value">{{ featureTreeStore.selectedNode.score?.toFixed(4) }}</span>
              </div>
            </div>
            <div v-else class="no-node-info">
              Hover over a node to see details.
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, watch, nextTick } from 'vue'
import { Users, User, Settings, GitBranch, Cog } from 'lucide-vue-next'
import { useTaskStore } from '@/stores/task'
import { useFeatureTreeStore } from '@/stores/featureTree'
import * as d3 from 'd3'

const taskStore = useTaskStore()
const featureTreeStore = useFeatureTreeStore()

const treeContainer = ref<HTMLElement>()
const activeAgent = ref<'main' | 'optimization' | 'validation'>('main')
const workingAgents = ref<string[]>([])
const connectionActive = ref(false)
const connectionActiveReverse = ref(false)
const connectionActiveValidation = ref(false)
const isPerformanceLoading = ref(false)

// Agent flow status
const getCurrentFlowStatus = () => {
  if (taskStore.status === 'running') {
    return workingAgents.value.length > 0 ? 'Processing...' : 'Initializing...'
  }
  return taskStore.statusText
}

// Agent interaction
function setActiveAgent(agent: 'main' | 'optimization' | 'validation') {
  activeAgent.value = agent
  taskStore.addNotification(`Selected ${agent} agent`, 'info')
}

// 模拟agent工作状态
function simulateAgentWork() {
  if (taskStore.status === 'running') {
    workingAgents.value = ['main']
    connectionActive.value = true

    setTimeout(() => {
      workingAgents.value = ['optimization']
      connectionActive.value = false
      connectionActiveReverse.value = true

      setTimeout(() => {
        workingAgents.value = ['validation']
        connectionActiveReverse.value = false
        connectionActiveValidation.value = true

        setTimeout(() => {
          workingAgents.value = []
          connectionActiveValidation.value = false
        }, 2000)
      }, 2000)
    }, 2000)
  }
}

// 监听树数据变化，重新渲染
watch(() => featureTreeStore.treeData, (newData) => {
  if (newData && treeContainer.value) {
    nextTick(() => {
      renderTree(newData)
    })
  }
}, { deep: true })

// 监听任务状态变化
watch(() => taskStore.status, (newStatus) => {
  if (newStatus === 'running') {
    simulateAgentWork()
  } else {
    workingAgents.value = []
    connectionActive.value = false
    connectionActiveReverse.value = false
    connectionActiveValidation.value = false
  }
})

onMounted(() => {
  if (taskStore.isInitialized) {
    featureTreeStore.loadTreeData()
  }
})

// D3.js 树形图渲染 (从FeatureGenerationPanel复制)
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
</script>

<style scoped>
.main-content {
  display: flex;
  flex: 1;
  flex-direction: column;
  padding: 1rem;
  gap: 0; /* 移除gap以消除空白 */
  overflow: hidden;
  background-color: #ffffff;
  height: 100%;
}

/* 上方区域 */
.upper-section {
  display: flex;
  gap: 1rem;
  flex: 7; /* 占据70%的高度 */
  min-height: 0;
  padding-bottom: 0.5rem;
}

.agent-flow-section {
  flex: 6.5; /* 占据65%的宽度 */
  min-width: 300px;
  display: flex;
  flex-direction: column;
}

.feature-tree-section {
  flex: 3.5; /* 占据35%的宽度 */
  min-width: 250px;
  display: flex;
  flex-direction: column;
}

/* 下方区域 */
.lower-section {
  display: flex;
  gap: 1rem;
  flex: 3; /* 占据30%的高度 */
  min-height: 0;
  padding-top: 0.5rem;
}

.current-features-section {
  flex: 1;
  min-width: 300px;
}

.node-info-section {
  flex: 1;
  min-width: 300px;
}

/* 通用样式 */
.section-header {
  margin-bottom: 0.75rem;
  padding-bottom: 0.5rem;
  border-bottom: 2px solid #e9ecef;
}

.section-title {
  color: #495057;
  font-weight: 600;
  margin: 0;
  display: flex;
  align-items: center;
}

.info-card {
  height: 100%;
  background-color: #f8f9fa;
  border-radius: 8px;
  border: 1px solid #dee2e6;
  display: flex;
  flex-direction: column;
}

.info-header {
  padding: 0.75rem 1rem;
  border-bottom: 1px solid #dee2e6;
  background-color: #ffffff;
  border-radius: 8px 8px 0 0;
}

.info-title {
  color: #495057;
  font-weight: 600;
  margin: 0;
  font-size: 0.875rem;
}

.info-content {
  flex: 1;
  padding: 1rem;
  overflow-y: auto;
}

/* Agent Flow Diagram */
.agent-flow-diagram {
  flex: 1;
  background-color: #f8f9fa;
  border-radius: 8px;
  border: 1px solid #dee2e6;
  position: relative;
  min-height: 200px;
}

.flow-container {
  position: relative;
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
}

.flow-center {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  text-align: center;
  z-index: 1;
}

.flow-title {
  font-weight: 600;
  color: #495057;
  margin-bottom: 0.25rem;
}

.flow-status {
  font-size: 0.75rem;
  color: #6c757d;
}

.agents-container {
  position: relative;
  width: 100%;
  height: 100%;
}

.agent-node {
  position: absolute;
  width: 100px;
  text-align: center;
  cursor: pointer;
  transition: all 0.3s ease;
}

/* 矩形三角落布局 */
.main-agent {
  top: 40px;
  left: 40px;
}

.opt-agent {
  top: 40px;
  right: 40px;
}

.validation-agent {
  bottom: 40px;
  left: 40px;
}

.agent-icon {
  width: 90px;
  height: 90px;
  background-color: transparent;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto 0.5rem;
  border: 3px solid transparent;
  transition: all 0.3s ease;
  color: #6c757d;
}

.agent-image {
  width: 100%;
  height: 100%;
  object-fit: contain;
  border-radius: 4px;
}

.agent-node.active .agent-icon {
  background-color: #007bff;
  color: white;
  border-color: #0056b3;
}

.agent-node.working .agent-icon {
  background-color: #28a745;
  color: white;
  animation: breathe 2s ease-in-out infinite;
}

.agent-label {
  font-weight: 600;
  font-size: 0.875rem;
  color: #495057;
  margin-bottom: 0.25rem;
}

.agent-goal {
  font-size: 0.75rem;
  color: #6c757d;
}

.working-indicator {
  position: absolute;
  top: -5px;
  right: -5px;
  width: 12px;
  height: 12px;
  background-color: #ffc107;
  border-radius: 50%;
  animation: pulse 1.5s ease-in-out infinite;
}

.connection-lines {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
  width: 500px;
  height: 400px;
  left: 50%;
  top: 50%;
  transform: translate(-50%, -50%);
}

.connection-line {
  fill: none;
  stroke: #dee2e6;
  stroke-width: 4;
  stroke-dasharray: 5, 5;
  transition: all 0.3s ease;
}

.connection-line.curved {
  stroke-width: 4;
  fill: none;
}

.connection-line.active {
  stroke: #007bff;
  stroke-dasharray: none;
  animation: flow 2s ease-in-out;
}

.connection-line.curved.active {
  stroke: #007bff;
}

/* Feature Tree */
.feature-tree-container {
  flex: 1;
  background-color: #f0f0f0;
  border-radius: 8px;
  border: 1px solid #dee2e6;
  padding: 0.5rem;
  min-height: 200px;
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

/* 特征信息 */
.feature-list {
  margin-bottom: 1rem;
}

.no-features {
  color: #6c757d;
  font-style: italic;
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

/* 节点信息 */
.node-details {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.node-detail {
  display: flex;
  align-items: flex-start;
  gap: 0.5rem;
}

.detail-label {
  font-weight: 600;
  color: #495057;
  min-width: 80px;
  flex-shrink: 0;
}

.detail-value {
  color: #6c757d;
  word-break: break-word;
  flex: 1;
}

.no-node-info {
  color: #6c757d;
  font-style: italic;
  text-align: center;
  padding: 2rem 0;
}

/* 动画 */
@keyframes breathe {
  0%, 100% {
    box-shadow: 0 0 0 0 rgba(40, 167, 69, 0.7);
  }
  50% {
    box-shadow: 0 0 0 10px rgba(40, 167, 69, 0);
  }
}

@keyframes pulse {
  0%, 100% {
    opacity: 1;
  }
  50% {
    opacity: 0.5;
  }
}

@keyframes flow {
  0% {
    stroke-dashoffset: 10;
  }
  100% {
    stroke-dashoffset: 0;
  }
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

/* 响应式设计 */
@media (max-width: 1200px) {
  .upper-section {
    flex-direction: column;
  }

  .lower-section {
    flex-direction: column;
    height: auto;
  }

  .agent-flow-section,
  .feature-tree-section {
    min-width: auto;
  }
}
</style>