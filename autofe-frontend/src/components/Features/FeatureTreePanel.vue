<template>
  <div class="feature-tree-panel">
    <div class="info-card">
      <div class="info-header">
        <h6 class="info-title">
          <GitBranch :size="18" class="me-2" />
          Feature search tree
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

// 缩放行为引用（滚轮/拖拽），以及当前变换（用于保持用户缩放/平移）
let zoomBehavior: d3.ZoomBehavior<SVGSVGElement, unknown> | null = null
let svgRootSelection: d3.Selection<SVGSVGElement, unknown, null, undefined> | null = null
let currentTransform: d3.ZoomTransform = d3.zoomIdentity
let hasUserTransform = false
let resizeObserver: ResizeObserver | null = null
let lastTreeSignature: string | null = null

const isScoreReady = (score: unknown) => {
  return typeof score === 'number' && score >= 0
}

// D3.js 树形图渲染
function renderTree(treeStructure: any) {
  if (!treeContainer.value) return

  // 清空容器
  d3.select(treeContainer.value).selectAll("*").remove()
  zoomBehavior = null
  svgRootSelection = null

  const { root_id, parent_child_relations, node_info } = treeStructure
  const selectedNodeId = featureTreeStore.selectedNode?.node_id

  // 若树结构发生变化（例如节点数/关系变化），重置用户变换，确保新树自动居中并按容器 fit
  const treeSignature = `${root_id}|${parent_child_relations?.length ?? 0}|${node_info?.length ?? 0}`
  if (lastTreeSignature !== treeSignature) {
    lastTreeSignature = treeSignature
    hasUserTransform = false
    currentTransform = d3.zoomIdentity
  }

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
  const nodeHeight = 38
  const nodePaddingX = 10
  const minNodeWidth = 140
  const maxNodeWidth = 2000
  const horizontalSpacing = 34
  const verticalSpacing = 44

  // 创建层次结构
  const root = d3.hierarchy(data)

  // ---- node width auto-fit (by feature name length) ----
  const canvas = document.createElement('canvas')
  const ctx = canvas.getContext('2d')
  const fontFamily =
    "'Inter', ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, sans-serif"
  const titleFont = `700 15px ${fontFamily}`
  const metaFont = `700 15px ${fontFamily}`

  const measure = (text: string, font: string) => {
    if (!ctx) return text.length * 8
    ctx.font = font
    return ctx.measureText(text).width
  }

  root.descendants().forEach((d: any) => {
    const fullName = d.data.feature_name || 'Unknown'
    const idText = `id: ${d.data.node_id}`
    const scoreText =
      isScoreReady(d.data.score) ? `${(Number(d.data.score) - 0.15).toFixed(4)}` : 'validating'

    const nameW = measure(fullName, titleFont)
    const bottomW = Math.max(measure(idText, metaFont), measure(scoreText, metaFont))
    const contentW = Math.max(nameW, bottomW)

    const boxW = Math.max(minNodeWidth, Math.min(maxNodeWidth, contentW + nodePaddingX * 2))
    d._boxWidth = boxW
    d._fullName = fullName
    d._displayName = fullName
    d._scoreText = scoreText
  })

  const layoutNodeWidth =
    d3.max(root.descendants() as any, (d: any) => Number(d._boxWidth)) ?? minNodeWidth

  // 使用 nodeSize 而不是 size，这样树可以根据内容自动扩展
  const treeLayout = d3.tree()
    .nodeSize([layoutNodeWidth + horizontalSpacing, nodeHeight + verticalSpacing])
  
  treeLayout(root)

  // ---- auto-fit to container by content bounds (use real per-node width) ----
  const containerWidth = treeContainer.value.clientWidth || 1
  const containerHeight = treeContainer.value.clientHeight || 1

  // 计算实际内容边界：x 需要考虑节点宽度，y 需要考虑节点高度
  let xMin = Infinity
  let xMax = -Infinity
  let yMin = Infinity
  let yMax = -Infinity

  root.descendants().forEach((d: any) => {
    const w = d._boxWidth ?? layoutNodeWidth
    const left = d.x - w / 2
    const right = d.x + w / 2
    const top = d.y
    const bottom = d.y + nodeHeight

    if (left < xMin) xMin = left
    if (right > xMax) xMax = right
    if (top < yMin) yMin = top
    if (bottom > yMax) yMax = bottom
  })

  // 内容很少时避免 Infinity
  if (!Number.isFinite(xMin) || !Number.isFinite(xMax) || !Number.isFinite(yMin) || !Number.isFinite(yMax)) {
    xMin = 0
    xMax = minNodeWidth
    yMin = 0
    yMax = nodeHeight
  }

  const padding = 24
  const contentWidth = Math.max(1, xMax - xMin)
  const contentHeight = Math.max(1, yMax - yMin)
  const availableWidth = Math.max(1, containerWidth - padding * 2)
  const availableHeight = Math.max(1, containerHeight - padding * 2)

  // fit 内容到容器，保留 padding。
  // 1 节点时容易过度放大，这里用 maxScale 限制。
  const maxScale = 2.4
  const minScale = 0.4
  let scale = Math.min(availableWidth / contentWidth, availableHeight / contentHeight)
  scale = Math.max(minScale, Math.min(maxScale, scale))

  // 特殊情况：只有一个节点时，不做 auto-fit 放大，保持原始尺寸（scale=1）
  if (root.descendants().length === 1) {
    scale = 1
  }

  // 计算平移：让内容中心对齐容器中心
  const cx = (xMin + xMax) / 2
  const cy = (yMin + yMax) / 2
  const translateX = containerWidth / 2 - scale * cx
  const translateY = containerHeight / 2 - scale * cy

  // 创建SVG容器
  svgRootSelection = d3.select(treeContainer.value)
    .append("svg")
    .attr("width", "100%")
    .attr("height", "100%")
    // 让坐标系直接等于容器尺寸，这样 fit/居中计算更直观
    .attr("viewBox", `0 0 ${containerWidth} ${containerHeight}`)
    .attr("preserveAspectRatio", "xMidYMid meet")

  // 平移到居中位置（初始 auto-fit）
  const zoomGroup = svgRootSelection.append("g")
    .attr("transform", `translate(${translateX}, ${translateY}) scale(${scale})`)

  // 设置缩放行为（包含拖拽平移）
  zoomBehavior = d3.zoom<SVGSVGElement, unknown>()
    .scaleExtent([minScale, 3])
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

  // 绘制连接线：黑色圆角折线（orthogonal / elbow） + 箭头
  const svg = zoomGroup

  // Arrow marker (created per render since we clear SVG each time)
  const defs = svgRootSelection!.append("defs")
  defs.append("marker")
    .attr("id", "feature-tree-arrowhead")
    .attr("viewBox", "0 -5 10 10")
    .attr("refX", 10)
    .attr("refY", 0)
    .attr("markerWidth", 8)
    .attr("markerHeight", 8)
    .attr("orient", "auto")
    .append("path")
    .attr("d", "M0,-5L10,0L0,5")
    .attr("fill", "#111827")

  svg.selectAll(".link")
    .data(root.links())
    .enter()
    .append("path")
    .attr("class", "link")
    .attr("d", (d: any) => {
      // Start at bottom-center of parent node and end at top-center of child node.
      const sx = d.source.x
      const sy = d.source.y + nodeHeight
      const tx = d.target.x
      const ty = d.target.y

      const dx = tx - sx
      const dy = ty - sy
      if (Math.abs(dx) < 1e-6 || Math.abs(dy) < 1e-6) {
        return `M${sx},${sy} L${tx},${ty}`
      }

      const midY = sy + dy / 2
      const signX = dx > 0 ? 1 : -1
      const signY = dy > 0 ? 1 : -1
      const r = Math.min(10, Math.abs(dx) / 2, Math.abs(dy) / 2)
      if (r <= 0) return `M${sx},${sy} L${tx},${ty}`

      const v1 = midY - signY * r
      const h1 = sx + signX * r
      const h2 = tx - signX * r
      const v2 = midY + signY * r

      // Rounded elbows via quadratic Beziers at both corners
      return `M${sx},${sy} V${v1} Q${sx},${midY} ${h1},${midY} H${h2} Q${tx},${midY} ${tx},${v2} V${ty}`
    })
    .attr("marker-end", "url(#feature-tree-arrowhead)")

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

  // 绘制节点矩形 (卡片样式)
  nodes.append("rect")
    .attr("width", (d: any) => d._boxWidth)
    .attr("height", nodeHeight)
    .attr("x", (d: any) => -d._boxWidth / 2)
    .attr("y", 0) // 从 y=0 开始
    .attr("rx", 10)
    .attr("ry", 10)
    .attr("fill", (d: any) => d.data.selected ? "#e5e7eb" : "#f3f4f6")
    .attr("stroke", (d: any) => d.data.selected ? "#111827" : "#6b7280")
    .attr("stroke-width", (d: any) => d.data.selected ? 3 : 2)
    .on("mouseover", function (_event: any, d: any) {
      if (!d.data.selected) {
        d3.select(this).attr("stroke", "#374151")
      }
    })
    .on("mouseout", function (_event: any, d: any) {
      if (!d.data.selected) {
        d3.select(this).attr("stroke", "#6b7280")
      }
    })

  // Top row: feature name
  nodes.append("text")
    .attr("x", 0)
    .attr("y", 14)
    .attr("text-anchor", "middle")
    .style("font-weight", "700")
    .style("font-size", "15px")
    .style("fill", "#111827")
    .text((d: any) => d._displayName || (d.data.feature_name || 'Unknown'))
    .append("title") // Tooltip
    .text((d: any) => d._fullName || d.data.feature_name)

  // Bottom row: id (left)
  nodes.append("text")
    .attr("x", (d: any) => -d._boxWidth / 2 + nodePaddingX)
    .attr("y", 30)
    .attr("text-anchor", "start")
    .style("font-size", "15px")
    .style("font-weight", "700")
    .style("fill", "#374151")
    .text((d: any) => `id: ${d.data.node_id}`)

  // Bottom row: performance metric (right)
  /*
  nodes.append("text")
    .attr("x", (d: any) => d._boxWidth / 2 - nodePaddingX)
    .attr("y", 30)
    .attr("text-anchor", "end")
    .style("font-size", "15px")
    .style("fill", (d: any) => isScoreReady(d.data.score) ? "#047857" : "#6b7280")
    .style("font-weight", "700")
    .text((d: any) => {
       return d._scoreText || (isScoreReady(d.data.score) ? `${(Number(d.data.score) - 0.15).toFixed(4)}` : 'validating')
    })
  */

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
  // 容器尺寸变化时：如果用户没手动缩放/平移，则重新 fit；否则保持用户视角
  if (treeContainer.value && !resizeObserver) {
    resizeObserver = new ResizeObserver(() => {
      if (!featureTreeStore.treeData) return
      if (hasUserTransform) return
      nextTick(() => {
        renderTree(featureTreeStore.treeData)
      })
    })
    resizeObserver.observe(treeContainer.value)
  }

  if (featureTreeStore.treeData && treeContainer.value) {
    nextTick(() => {
      renderTree(featureTreeStore.treeData)
    })
  }
})

onUnmounted(() => {
  if (resizeObserver && treeContainer.value) {
    resizeObserver.unobserve(treeContainer.value)
  }
  resizeObserver = null
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
  border-radius: 6px;
  border: none;
  display: flex;
  flex-direction: column;
  box-shadow: none;
}

.info-header {
  padding: 0.4rem 0.6rem 0.35rem;
  border-bottom: none;
  background-color: #fff;
  border-radius: 6px 6px 0 0;
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
  padding: 0.6rem;
  overflow-y: auto;
}

.feature-tree-container {
  height: 100%; /* 占满剩余空间 */
  background-color: #ffffff;
  border-radius: 6px;
  border: 1px solid #e5e7eb;
  padding: 0.4rem;
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
  stroke: #111827;
  stroke-width: 2px;
  stroke-linecap: round;
  stroke-linejoin: round;
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
