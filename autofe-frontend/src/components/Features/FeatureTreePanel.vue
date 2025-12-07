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

// 缩放行为引用（滚轮/拖拽），以及当前变换（用于保持用户缩放/平移）
let zoomBehavior: d3.ZoomBehavior<SVGSVGElement, unknown> | null = null
let svgRootSelection: d3.Selection<SVGSVGElement, unknown, null, undefined> | null = null
let currentTransform: d3.ZoomTransform = d3.zoomIdentity
let hasUserTransform = false

// D3.js 树形图渲染
function renderTree(treeStructure: any) {
  if (!treeContainer.value) return

  // 清空容器
  d3.select(treeContainer.value).selectAll("*").remove()
  zoomBehavior = null
  svgRootSelection = null

  let { root_id, parent_child_relations, node_info } = treeStructure
  const selectedNodeId = featureTreeStore.selectedNode?.node_id

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
      selected: selectedNodeId === rootId
    }
    const nodeMap: { [key: string]: any } = { [rootId]: tree }

    parent_child_relations.forEach(([parent_id, child_id]: [string, string]) => {
      const parentNode = nodeMap[parent_id]
      // 如果父节点不存在（可能是数据不一致），跳过
      if (!parentNode) return
      
      const childNode = {
        id: child_id,
        ...nodeInfoMap[child_id],
        children: [],
        selected: selectedNodeId === child_id
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

  // 清空容器
  d3.select(treeContainer.value).selectAll("*").remove()

  // 节点尺寸配置（字体大，但卡片更紧凑）
  const nodeWidth = 170
  const nodeHeight = 74
  const horizontalSpacing = 34
  const verticalSpacing = 72

  // 创建层次结构
  const root = d3.hierarchy(data)

  // 使用 nodeSize 而不是 size，这样树可以根据内容自动扩展
  const treeLayout = d3.tree()
    .nodeSize([nodeWidth + horizontalSpacing, nodeHeight + verticalSpacing])
  
  treeLayout(root)

  // 计算边界以设置 SVG 大小
  let xMin = Infinity
  let xMax = -Infinity
  let yMin = Infinity
  let yMax = -Infinity

  root.descendants().forEach((d: any) => {
    if (d.x < xMin) xMin = d.x
    if (d.x > xMax) xMax = d.x
    if (d.y < yMin) yMin = d.y
    if (d.y > yMax) yMax = d.y
  })

  // 加上边距
  const margin = { top: 40, right: 20, bottom: 40, left: 20 }
  const widthNeeded = (xMax - xMin) + nodeWidth + margin.left + margin.right
  const heightNeeded = (yMax - yMin) + nodeHeight + margin.top + margin.bottom
  const containerWidth = treeContainer.value.clientWidth || widthNeeded
  const containerHeight = treeContainer.value.clientHeight || heightNeeded

  const depth = root.height + 1
  // 根据层级设置填充比例，尽量填满容器但保留留白
  // 3 层场景放大展示，填充比例更高
  const fillRatio = depth >= 5 ? 0.7 : depth === 4 ? 0.78 : depth === 3 ? 0.95 : 0.9
  const targetScaleX = (containerWidth * fillRatio) / widthNeeded
  const targetScaleY = (containerHeight * fillRatio) / heightNeeded
  let scale = Math.min(targetScaleX, targetScaleY)

  // 3 层特例：整体再放大 2 倍
  if (depth === 3) {
    scale *= 2
  }

  // 不同层数的放大/缩小限制，保持既不太小也不撑满
  const maxScale = depth <= 2 ? 1.4 : depth === 3 ? 2.2 : depth === 4 ? 1.15 : 1.0
  const minScale = depth >= 5 ? 0.5 : depth === 4 ? 0.55 : depth === 3 ? 0.65 : 0.75
  scale = Math.max(minScale, Math.min(maxScale, scale))
  const needsScale = scale !== 1

  const svgWidth = Math.max(containerWidth, widthNeeded)
  const svgHeight = Math.max(containerHeight, heightNeeded)
  const translateX = svgWidth / 2 - (xMin + xMax) / 2
  const translateY = margin.top - yMin

  // 创建SVG容器
  svgRootSelection = d3.select(treeContainer.value)
    .append("svg")
    .attr("width", "100%")
    .attr("height", "100%")
    .attr("viewBox", `0 0 ${svgWidth} ${svgHeight}`)
    .attr("preserveAspectRatio", "xMidYMid meet")

  // 平移到居中位置
  const zoomGroup = svgRootSelection.append("g")
    .attr("transform", `translate(${translateX}, ${translateY}) scale(${scale})`)

  // 设置缩放行为（包含拖拽平移）
  zoomBehavior = d3.zoom<SVGSVGElement, unknown>()
    .scaleExtent([0.4, 3])
    .on("zoom", (event) => {
      zoomGroup.attr("transform", event.transform)
      currentTransform = event.transform
      hasUserTransform = true
    })

  const initialTransform = hasUserTransform
    ? currentTransform
    : d3.zoomIdentity.translate(translateX, translateY).scale(scale)
  svgRootSelection
    .call(zoomBehavior as any)
    .call(zoomBehavior!.transform as any, initialTransform)
  currentTransform = initialTransform

  // 绘制连接线 (曲线更美观)
  const svg = zoomGroup

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

  // 添加阴影滤镜
  const defs = svg.append("defs")
  const filter = defs.append("filter")
    .attr("id", "drop-shadow")
    .attr("height", "130%")
  
  filter.append("feGaussianBlur")
    .attr("in", "SourceAlpha")
    .attr("stdDeviation", 2)
    .attr("result", "blur")
  
  filter.append("feOffset")
    .attr("in", "blur")
    .attr("dx", 0)
    .attr("dy", 2)
    .attr("result", "offsetBlur")
  
  filter.append("feFlood")
    .attr("flood-color", "rgba(0,0,0,0.1)")
    .attr("result", "colorBlur")
    
  filter.append("feComposite")
    .attr("in", "colorBlur")
    .attr("in2", "offsetBlur")
    .attr("operator", "in")
  
  filter.append("feMerge")
    .append("feMergeNode")
  filter.select("feMerge")
    .append("feMergeNode")
    .attr("in", "SourceGraphic")

  // 绘制节点矩形 (卡片样式)
  nodes.append("rect")
    .attr("width", nodeWidth)
    .attr("height", nodeHeight)
    .attr("x", -nodeWidth / 2)
    .attr("y", 0) // 从 y=0 开始
    .attr("rx", 10) // 圆角略大
    .attr("ry", 10)
    .style("filter", "url(#drop-shadow)")
    .attr("fill", (d: any) => d.data.selected ? "#ecfdf5" : "#ffffff") // 选中背景改为浅绿
    .attr("stroke", (d: any) => d.data.selected ? "#10b981" : "#cbd5e1") // 选中边框改为绿色
    .attr("stroke-width", (d: any) => d.data.selected ? 2 : 1)
    .on("mouseover", function (_event: any, d: any) {
      if (!d.data.selected) {
        d3.select(this).attr("stroke", "#94a3b8")
      }
    })
    .on("mouseout", function (_event: any, d: any) {
      if (!d.data.selected) {
        d3.select(this).attr("stroke", "#cbd5e1")
      }
    })

  // 移除原来的左侧蓝色装饰线

  // 添加特征名称文字
  nodes.append("text")
    .attr("dy", 24)
    .attr("text-anchor", "middle")
    .style("font-weight", "700")
    .style("font-size", "16px") // 再增大字号
    .style("fill", "#1e293b")
    .text((d: any) => {
      const name = d.data.feature_name || 'Unknown'
      // 增加显示长度但保持卡片紧凑
      return name.length > 20 ? name.substring(0, 18) + '...' : name
    })
    .append("title") // Tooltip
    .text((d: any) => d.data.feature_name)

  // 添加 ID 文字
  nodes.append("text")
    .attr("dy", 42)
    .attr("text-anchor", "middle")
    .style("font-size", "13px") // 增大字号
    .style("fill", "#64748b")
    .style("font-family", "monospace")
    .text((d: any) => `ID: ${d.data.node_id}`)

  // 添加 Score 文字
  nodes.append("text")
    .attr("dy", 60)
    .attr("text-anchor", "middle")
    .style("font-size", "13px")
    .style("fill", (d: any) => d.data.score !== undefined ? "#059669" : "#94a3b8") // 有分数为绿色，否则灰色
    .style("font-weight", "500")
    .text((d: any) => {
       if (d.data.score !== undefined && d.data.score !== null) {
         // 格式化分数，保留4位小数
         return `Score: ${Number(d.data.score).toFixed(4)}`
       }
       return ''
    })

  // 设置根节点引用
  featureTreeStore.setRoot(root)
}

function handleNodeClick(nodeData: any) {
  featureTreeStore.setSelectedNode(nodeData)
  // 重新渲染树以更新高亮状态
  if (featureTreeStore.treeData) {
    renderTree(featureTreeStore.treeData)
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
  padding: 12px 16px;
  border-bottom: 2px solid var(--accent-blue, #2a7de1);
  background-color: transparent;
  border-radius: 12px 12px 0 0;
}

.info-title {
  color: var(--text-primary);
  font-weight: 700;
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
  height: 100%; /* 占满剩余空间 */
  background-color: #f7f9fc;
  border-radius: 10px;
  border: none;
  padding: 0.6rem;
  min-height: 150px;
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

/* D3.js 样式 */
:deep(.link) {
  fill: none;
  stroke: #cbd5e1;
  stroke-width: 2px;
  transition: stroke 0.3s ease;
}

:deep(.node) {
  cursor: pointer;
}

:deep(.node rect) {
  transition: all 0.2s ease;
}

:deep(.node text) {
  pointer-events: none;
  user-select: none;
  font-family: 'Inter', ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, sans-serif;
}
</style>
