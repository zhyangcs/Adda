<template>
  <div class="in-db-panel">
    <div class="card dag-card">
      <div class="card-header">
        <div class="title">in-DB Computation</div>
        <div class="actions">
          <button class="ghost-btn" :disabled="loading" @click="loadDag">
            Refresh
          </button>
        </div>
      </div>
      <div class="card-body">
        <div v-if="error" class="warning">{{ error }}</div>
        <div class="dag-layout">
          <div class="dag-canvas" ref="containerRef">
            <div v-if="loading" class="muted-text">Loading…</div>
            <div v-else-if="!dag?.nodes?.length" class="muted-text">No DAG data.</div>
          </div>
        </div>
      </div>
    </div>

    <div class="card code-card">
      <div class="card-header">
        <div class="title">Selected Node</div>
      </div>
      <div class="card-body">
        <div class="node-title">{{ nodeTitle }}</div>

        <div class="code-section">
          <div class="code-label">Python</div>
          <pre class="code-block">{{ nodePython }}</pre>
        </div>

        <div class="code-section">
          <div class="code-label">SQL</div>
          <pre class="code-block">{{ nodeSql }}</pre>
        </div>

        <div class="code-section">
          <div class="code-label">UDF</div>
          <pre class="code-block">{{ nodeUdf }}</pre>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import * as d3 from 'd3'
import { apiService } from '@/services/APIService'
import { useTaskStore } from '@/stores/task'
import type { Py2SqlDagData, Py2SqlDagNode } from '@/types'

const taskStore = useTaskStore()

const datasetNameMap: Record<string, string> = {
  '1': 'Titanic',
  '2': 'Heart',
  '3': 'Bank',
  '4': 'Diabetes',
  '5': 'Bike',
  '6': 'House'
}

const containerRef = ref<HTMLDivElement | null>(null)
const dag = ref<Py2SqlDagData | null>(null)
const loading = ref(false)
const error = ref('')
const selected = ref<Py2SqlDagNode | null>(null)
const lastZoomTransform = ref<d3.ZoomTransform | null>(null)
let resizeObserver: ResizeObserver | null = null

const nodeTitle = computed(() => {
  if (!selected.value) return 'Select a node to see details.'
  const n = selected.value
  const cols = n.writeColumns?.length ? n.writeColumns : n.readColumns
  const label = (cols && cols.length) ? cols.slice(0, 2).join(',') : (n.opType || 'NODE')
  return `${label} · ${n.opType || 'NODE'}`
})

const nodePython = computed(() => selected.value?.pythonCode?.trim() || '(no python code)')

const nodeSql = computed(() => {
  const blocks = selected.value?.sqlSnippets || []
  if (!blocks.length) return '(no sql snippet)'
  return blocks.map(item => {
    const label = item.cte ? `-- cte: ${item.cte}` : '-- sql'
    return `${label}\n${item.sql}`
  }).join('\n\n')
})

const nodeUdf = computed(() => {
  const blocks = selected.value?.udfSnippets || []
  if (!blocks.length) return '(no udf snippet)'
  return blocks.join('\n\n')
})

function datasetLabel() {
  return datasetNameMap[taskStore.config.dataset] || taskStore.config.dataset || 'Heart'
}

async function loadDag() {
  loading.value = true
  error.value = ''
  try {
    const response = await apiService.getPy2SqlDag({
      dataset: datasetLabel(),
      mlModel: taskStore.config.mlModel,
      pipelineId: undefined
    })
    if (response.status === 'success' && response.data) {
      dag.value = response.data
      selected.value = response.data.nodes?.[0] || null
    } else {
      error.value = response.message || 'Failed to load pipeline DAG.'
    }
  } catch (e: any) {
    error.value = e?.message || 'Unexpected error while loading pipeline DAG.'
  } finally {
    loading.value = false
  }
}

function renderDag() {
  const container = containerRef.value
  if (!container) return
  d3.select(container).selectAll('svg').remove()

  const data = dag.value
  if (!data || !data.nodes?.length) return

  const nodes = data.nodes
  const edges = data.edges || []

  type NodeDims = { w: number; h: number; headerH?: number; isIcon?: boolean }

  const cornerR = 10
  const perRow = 3
  const colGap = 110
  const rowGap = 170
  const padX = 80
  const padY = 90
  const turnPad = 26
  const strokeColor = '#0f172a'

  const containerW = Math.max(320, container.clientWidth || 860)
  // Keep SVG size in sync with the container's actual height.
  // A too-large SVG will visually "bleed" outside the card when the panel is constrained.
  const MIN_CANVAS_H = 260
  const containerH = Math.max(MIN_CANVAS_H, container.clientHeight || 420)

  const COLORS = {
    sql: {
      top: 'rgb(58, 117, 147)',
      bottom: 'rgb(184, 197, 204)',
      border: 'rgb(48, 82, 102)'
    },
    python: {
      top: 'rgb(188, 114, 28)',
      bottom: 'rgb(220, 166, 102)',
      border: 'rgb(181, 115, 39)'
    }
  } as const

  const ICONS = {
    source: '/indb_icon/tp_source_database_icon.png',
    table: '/indb_icon/tp_table_indb_icon.png',
    python: '/indb_icon/tp_Python-Emblem.png'
  } as const

  // Make nodes more compact.
  const ICON_S = 92
  const BOX_H = 48
  const BOX_HEADER_H = 20
  const BOX_MIN_W = 140
  const BOX_MAX_W = 360

  // Text measurement for adaptive node width / truncation.
  const canvas = document.createElement('canvas')
  const ctx = canvas.getContext('2d')
  const labelFont = "800 13px Inconsolata, ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace"
  const headerFont = "700 11px Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, 'Noto Sans', sans-serif"

  const measure = (text: string, font: string) => {
    if (!ctx) return text.length * 8
    ctx.font = font
    return ctx.measureText(text).width
  }

  const truncateToWidth = (text: string, maxPx: number, font: string) => {
    if (measure(text, font) <= maxPx) return text
    const ellipsis = '…'
    const ellipsisW = measure(ellipsis, font)
    let lo = 0
    let hi = text.length
    while (lo < hi) {
      const mid = Math.ceil((lo + hi) / 2)
      const candidate = text.slice(0, mid)
      if (measure(candidate, font) + ellipsisW <= maxPx) lo = mid
      else hi = mid - 1
    }
    return text.slice(0, Math.max(0, lo)) + ellipsis
  }

  const getLabelText = (n: Py2SqlDagNode) => {
    const cols = n.writeColumns?.length ? n.writeColumns : n.readColumns
    if (cols && cols.length) return cols.slice(0, 2).join(',')
    return 'feature'
  }

  const dimsById = new Map<number, NodeDims>()
  nodes.forEach(n => {
    if (n.opType === 'START' || n.opType === 'END') {
      dimsById.set(n.nodeId, { w: ICON_S, h: ICON_S, isIcon: true })
      return
    }
    const headerText = (n.opType || 'NODE').toUpperCase()
    const labelText = getLabelText(n)
    const contentW = Math.max(measure(headerText, headerFont), measure(labelText, labelFont))
    const w = Math.max(BOX_MIN_W, Math.min(BOX_MAX_W, Math.ceil(contentW + 34)))
    dimsById.set(n.nodeId, { w, h: BOX_H, headerH: BOX_HEADER_H, isIcon: false })
  })

  const inDegree = new Map(nodes.map(n => [n.nodeId, 0]))
  const adjacency = new Map(nodes.map(n => [n.nodeId, [] as number[]]))
  edges.forEach(edge => {
    if (adjacency.has(edge.from)) adjacency.get(edge.from)!.push(edge.to)
    inDegree.set(edge.to, (inDegree.get(edge.to) || 0) + 1)
  })

  // Topological order (stable-ish by nodeId) → snake layout with max 3 per row.
  const topoOrder = (() => {
    const indeg = new Map(inDegree)
    const q: number[] = []
    nodes.forEach(n => {
      if ((indeg.get(n.nodeId) || 0) === 0) q.push(n.nodeId)
    })
    q.sort((a, b) => a - b)

    const order: number[] = []
    while (q.length) {
      const cur = q.shift()!
      order.push(cur)
      const nexts = (adjacency.get(cur) || []).slice().sort((a, b) => a - b)
      nexts.forEach(nx => {
        indeg.set(nx, (indeg.get(nx) || 0) - 1)
        if ((indeg.get(nx) || 0) === 0) {
          q.push(nx)
          q.sort((a, b) => a - b)
        }
      })
    }

    // If graph has cycles / missing nodes, append remaining by nodeId.
    const all = new Set(nodes.map(n => n.nodeId))
    order.forEach(id => all.delete(id))
    Array.from(all).sort((a, b) => a - b).forEach(id => order.push(id))

    const byId = new Map(nodes.map(n => [n.nodeId, n] as const))
    return order.map(id => byId.get(id)!).filter(Boolean)
  })()

  const positions = new Map<number, { x: number; y: number }>()
  const rowIndexById = new Map<number, number>()
  const colIndexById = new Map<number, number>()
  const rowBounds = new Map<number, { left: number; right: number }>()

  // Snake placement on a 3-column grid:
  // 0→1→2 then go down staying at 2, reverse: 2→1→0 then go down staying at 0...
  const gridPosById = new Map<number, { row: number; col: number }>()
  let curRow = 0
  let curCol = 0
  let dir = 1 // +1: move right, -1: move left
  topoOrder.forEach((n, idx) => {
    gridPosById.set(n.nodeId, { row: curRow, col: curCol })
    rowIndexById.set(n.nodeId, curRow)
    colIndexById.set(n.nodeId, curCol)

    if (idx === topoOrder.length - 1) return
    if (dir === 1) {
      if (curCol < perRow - 1) curCol += 1
      else {
        curRow += 1
        dir = -1
        // keep at last column to create a vertical connection
        curCol = perRow - 1
      }
    } else {
      if (curCol > 0) curCol -= 1
      else {
        curRow += 1
        dir = 1
        // keep at first column to create a vertical connection
        curCol = 0
      }
    }
  })

  const maxRow = Math.max(...Array.from(gridPosById.values()).map(p => p.row), 0)
  const rowCount = maxRow + 1

  // Column widths based on the widest node in each column.
  const colWidths: number[] = Array.from({ length: perRow }, () => 0)
  gridPosById.forEach((p, id) => {
    const d = dimsById.get(id) || { w: BOX_MIN_W, h: BOX_H }
    const cur = colWidths[p.col] ?? 0
    colWidths[p.col] = Math.max(cur, d.w)
  })
  for (let i = 0; i < perRow; i++) {
    if (!colWidths[i]) colWidths[i] = BOX_MIN_W
  }

  const colCenters: number[] = new Array(perRow)
  let runningX = padX
  for (let c = 0; c < perRow; c++) {
    const cw = colWidths[c] ?? BOX_MIN_W
    const cx = runningX + cw / 2
    colCenters[c] = cx
    runningX += cw + colGap
  }

  let layoutW = 0
  let layoutH = 0
  for (let r = 0; r < rowCount; r++) {
    const y = padY + r * rowGap
    let leftEdge = Number.POSITIVE_INFINITY
    let rightEdge = Number.NEGATIVE_INFINITY

    for (let c = 0; c < perRow; c++) {
      const cx = colCenters[c] ?? (padX + c * (BOX_MIN_W + colGap))
      const cw = colWidths[c] ?? BOX_MIN_W
      leftEdge = Math.min(leftEdge, cx - cw / 2)
      rightEdge = Math.max(rightEdge, cx + cw / 2)
    }

    rowBounds.set(r, { left: leftEdge, right: rightEdge })
    layoutW = Math.max(layoutW, rightEdge + padX)
    layoutH = Math.max(layoutH, y + rowGap / 2 + padY)
  }

  gridPosById.forEach((p, id) => {
    const x = colCenters[p.col] ?? (padX + p.col * (BOX_MIN_W + colGap))
    positions.set(id, { x, y: padY + p.row * rowGap })
  })

  layoutW = Math.max(layoutW, 860)
  layoutH = Math.max(layoutH, 360)

  const svg = d3.select(container)
    .append('svg')
    .attr('width', containerW)
    .attr('height', containerH)
    .attr('class', 'dag-svg')
    .style('display', 'block')
    .style('overflow', 'hidden')

  // Background to capture zoom/pan interactions.
  svg.append('rect')
    .attr('x', 0)
    .attr('y', 0)
    .attr('width', containerW)
    .attr('height', containerH)
    .style('fill', 'transparent')
    .style('pointer-events', 'all')

  const zoomRoot = svg.append('g').attr('class', 'zoom-root')

  const defs = svg.append('defs')

  const markerId = `arrow-${Date.now()}`
  defs.append('marker')
    .attr('id', markerId)
    .attr('viewBox', '0 0 10 10')
    .attr('refX', 8)
    .attr('refY', 5)
    .attr('markerWidth', 6)
    .attr('markerHeight', 6)
    .attr('orient', 'auto')
    .append('path')
    .attr('d', 'M 0 0 L 10 5 L 0 10 z')
    .attr('fill', strokeColor)

  const nodeShadowId = `node-shadow-${markerId}`
  const nodeShadow = defs.append('filter')
    .attr('id', nodeShadowId)
    .attr('x', '-40%')
    .attr('y', '-40%')
    .attr('width', '180%')
    .attr('height', '180%')
  nodeShadow.append('feDropShadow')
    .attr('dx', '0')
    .attr('dy', '2')
    .attr('stdDeviation', '2')
    .attr('flood-color', '#0f172a')
    .attr('flood-opacity', '0.12')

  const edgePath = (fromId: number, toId: number) => {
    const src = positions.get(fromId)
    const dst = positions.get(toId)
    if (!src || !dst) return ''

    const sDim = dimsById.get(fromId) || { w: BOX_MIN_W, h: BOX_H }
    const dDim = dimsById.get(toId) || { w: BOX_MIN_W, h: BOX_H }

    const sRow = rowIndexById.get(fromId) ?? 0
    const dRow = rowIndexById.get(toId) ?? 0
    const sCol = colIndexById.get(fromId) ?? 0
    const dCol = colIndexById.get(toId) ?? 0

    const dx = dst.x - src.x
    const sy = src.y
    const ey = dst.y

    // Same row: horizontal straight arrow.
    if (sRow === dRow) {
      const sx = src.x + Math.sign(dx || 1) * (sDim.w / 2)
      const ex = dst.x - Math.sign(dx || 1) * (dDim.w / 2)
      return `M${sx},${sy} L${ex},${ey}`
    }

    // Same column across rows: vertical straight arrow (e.g. node3 -> node4).
    if (sCol === dCol) {
      const dy = dst.y - src.y
      const ySign = Math.sign(dy || 1)
      const sx = src.x
      const sy2 = src.y + ySign * (sDim.h / 2)
      const ex = dst.x
      const ey2 = dst.y - ySign * (dDim.h / 2)
      return `M${sx},${sy2} L${ex},${ey2}`
    }

    // Different rows: orthogonal polyline (horizontal → vertical → horizontal).
    const bounds = rowBounds.get(sRow)
    const dir = sRow % 2 === 0 ? 1 : -1
    const sx = src.x + dir * (sDim.w / 2)
    const turnX = bounds
      ? (dir === 1 ? bounds.right + turnPad : bounds.left - turnPad)
      : sx + dir * turnPad

    const dy = dst.y - src.y
    const ySign = Math.sign(dy || 1)
    const midY = (src.y + dst.y) / 2

    // End on a vertical segment so the arrow can be vertical.
    const endY = dst.y - ySign * (dDim.h / 2)
    const endX = dst.x

    return `M${sx},${sy} L${turnX},${sy} L${turnX},${midY} L${endX},${midY} L${endX},${endY}`
  }

  const linkGroup = zoomRoot.append('g').attr('class', 'links')
  linkGroup.selectAll('.pipeline-link-halo')
    .data(edges)
    .enter()
    .append('path')
    .attr('class', 'pipeline-link-halo')
    .attr('d', d => edgePath(d.from, d.to))
    .style('fill', 'none')
    .style('stroke', '#ffffff')
    .style('stroke-width', '6px')
    .style('stroke-linecap', 'square')

  linkGroup.selectAll('.pipeline-link')
    .data(edges)
    .enter()
    .append('path')
    .attr('class', 'pipeline-link')
    .attr('marker-end', `url(#${markerId})`)
    .attr('d', d => edgePath(d.from, d.to))
    .style('fill', 'none')
    .style('stroke', strokeColor)
    .style('stroke-width', '2.5px')
    .style('stroke-linecap', 'square')

  const nodeGroup = zoomRoot.selectAll('.pipeline-node')
    .data(nodes)
    .enter()
    .append('g')
    .attr('class', 'pipeline-node')
    .attr('transform', d => {
      const pos = positions.get(d.nodeId)
      return `translate(${pos?.x ?? 0},${pos?.y ?? 0})`
    })
    .style('cursor', 'pointer')
    .on('click', (_event, d) => {
      selected.value = d
      zoomRoot.selectAll<SVGRectElement, Py2SqlDagNode>('.node-border')
        .each(function () {
          const base = (this as SVGRectElement).getAttribute('data-base-stroke') || '#94a3b8'
          d3.select(this).style('stroke', base).style('stroke-width', 2.5)
        })
      d3.select(_event.currentTarget).select<SVGRectElement>('.node-border')
        .style('stroke', '#0f172a')
        .style('stroke-width', 3.5)
    })

  nodeGroup.each(function (d) {
    const g = d3.select(this)
    const isPythonNode = (d.udfSnippets && d.udfSnippets.length > 0) || d.opType === 'UDF' || d.opType === 'APPLY'
    const dim = dimsById.get(d.nodeId) || { w: BOX_MIN_W, h: BOX_H, headerH: BOX_HEADER_H }

    if (d.opType === 'START') {
      const imgW = ICON_S
      const imgH = ICON_S
      g.append('image')
        .attr('href', ICONS.source)
        .attr('xlink:href', ICONS.source)
        .attr('x', -imgW / 2)
        .attr('y', -imgH / 2)
        .attr('width', imgW)
        .attr('height', imgH)
        .style('filter', `url(#${nodeShadowId})`)

      const label = g.append('text')
        .attr('x', 0)
        .attr('y', -imgH / 2 - 12)
        .attr('text-anchor', 'middle')
        .style('font-size', '12px')
        .style('font-weight', '700')
        .style('fill', strokeColor)
        .style('pointer-events', 'none')
      label.append('tspan').attr('x', 0).attr('dy', '0').text('Source Table')
      label.append('tspan').attr('x', 0).attr('dy', '14').text('(Input Layer)')
      return
    }

    if (d.opType === 'END') {
      const imgW = ICON_S
      const imgH = ICON_S
      g.append('image')
        .attr('href', ICONS.table)
        .attr('xlink:href', ICONS.table)
        .attr('x', -imgW / 2)
        .attr('y', -imgH / 2)
        .attr('width', imgW)
        .attr('height', imgH)
        .style('filter', `url(#${nodeShadowId})`)

      const label = g.append('text')
        .attr('x', 0)
        .attr('y', imgH / 2 + 20)
        .attr('text-anchor', 'middle')
        .style('font-size', '12px')
        .style('font-weight', '700')
        .style('fill', strokeColor)
        .style('pointer-events', 'none')
      label.append('tspan').attr('x', 0).attr('dy', '0').text('Training View')
      label.append('tspan').attr('x', 0).attr('dy', '14').text('(Output Layer)')
      return
    }

    const palette = isPythonNode ? COLORS.python : COLORS.sql
    const headerText = (d.opType || 'NODE').toUpperCase()
    const rawLabelText = getLabelText(d)
    const labelText = truncateToWidth(rawLabelText, dim.w - 28, labelFont)

    const border = g.append('rect')
      .attr('class', 'node-border')
      .attr('data-base-stroke', palette.border)
      .attr('x', -dim.w / 2).attr('y', -dim.h / 2)
      .attr('width', dim.w).attr('height', dim.h)
      .attr('rx', cornerR).attr('ry', cornerR)
      .style('fill', palette.bottom)
      .style('stroke', palette.border)
      .style('stroke-width', 2.2)
      .style('filter', `url(#${nodeShadowId})`)

    const headerH = dim.headerH ?? BOX_HEADER_H
    g.append('path')
      .attr('d', `M ${-dim.w / 2} ${-dim.h / 2 + headerH} L ${-dim.w / 2} ${-dim.h / 2 + cornerR} Q ${-dim.w / 2} ${-dim.h / 2} ${-dim.w / 2 + cornerR} ${-dim.h / 2} L ${dim.w / 2 - cornerR} ${-dim.h / 2} Q ${dim.w / 2} ${-dim.h / 2} ${dim.w / 2} ${-dim.h / 2 + cornerR} L ${dim.w / 2} ${-dim.h / 2 + headerH} Z`)
      .style('fill', palette.top)

    g.append('text')
      .attr('x', 0)
      .attr('y', -dim.h / 2 + headerH / 2)
      .attr('text-anchor', 'middle')
      .attr('dominant-baseline', 'middle')
      .style('font-size', '11px')
      .style('font-weight', '700')
      .style('fill', '#ffffff')
      .style('pointer-events', 'none')
      .text(headerText)

    const bottomCenterY = (-dim.h / 2 + headerH + dim.h / 2) / 2
    g.append('text')
      .attr('x', 0)
      .attr('y', bottomCenterY)
      .attr('text-anchor', 'middle')
      .attr('dominant-baseline', 'middle')
      .style('font-family', "'Inconsolata', ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace")
      .style('font-size', '13px')
      .style('font-weight', '800')
      .style('fill', '#0b1224')
      .style('pointer-events', 'none')
      .text(labelText)

    if (isPythonNode) {
      // Match the screenshot: icon sits at top-right, slightly outside the node.
      const iconSz = 28
      const iconX = dim.w / 2 - iconSz * 0.55
      const iconY = -dim.h / 2 - iconSz * 0.55
      g.append('image')
        .attr('href', ICONS.python)
        .attr('xlink:href', ICONS.python)
        .attr('x', iconX)
        .attr('y', iconY)
        .attr('width', iconSz)
        .attr('height', iconSz)
        .style('filter', `url(#${nodeShadowId})`)
    }
  })

  // Keep selected border highlighted after re-render.
  if (selected.value) {
    zoomRoot.selectAll<SVGGElement, Py2SqlDagNode>('.pipeline-node')
      .filter(d => d.nodeId === selected.value?.nodeId)
      .select<SVGRectElement>('.node-border')
      .style('stroke', '#0f172a')
      .style('stroke-width', 3.5)
  }

  // Zoom + pan (wheel zoom, drag to pan). Persist transform across rerenders.
  const zoom = d3.zoom<SVGSVGElement, unknown>()
    .scaleExtent([0.2, 3.2])
    .on('zoom', (event) => {
      lastZoomTransform.value = event.transform
      zoomRoot.attr('transform', event.transform.toString())
    })

  svg.call(zoom as any)

  if (lastZoomTransform.value) {
    svg.call(zoom.transform as any, lastZoomTransform.value)
  } else {
    const fitScale = Math.min(containerW / layoutW, containerH / layoutH, 1)
    const tx = (containerW - layoutW * fitScale) / 2
    const ty = (containerH - layoutH * fitScale) / 2
    const init = d3.zoomIdentity.translate(tx, ty).scale(fitScale)
    lastZoomTransform.value = init
    svg.call(zoom.transform as any, init)
  }
}

watch(dag, () => {
  renderDag()
})

onMounted(() => {
  // Keep DAG responsive to container resize.
  if (containerRef.value && 'ResizeObserver' in window) {
    resizeObserver = new ResizeObserver(() => {
      if (dag.value?.nodes?.length) renderDag()
    })
    resizeObserver.observe(containerRef.value)
  }
})

onBeforeUnmount(() => {
  if (resizeObserver && containerRef.value) {
    resizeObserver.unobserve(containerRef.value)
  }
  resizeObserver = null
})
</script>

<style scoped>
.in-db-panel {
  display: flex;
  flex-direction: column;
  gap: 12px;
  height: 100%;
  min-height: 0;
  overflow: hidden;
}

.card {
  background: #ffffff;
  border: none;
  border-radius: 6px;
  box-shadow: none;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.dag-card,
.code-card {
  flex: 1 1 0;
  min-height: 0;
  overflow: hidden;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 0.4rem 0.6rem 0.35rem;
  background: #ffffff;
  border-bottom: none !important;
  border-radius: 6px 6px 0 0;
}

.title {
  font-size: var(--font-size-lg, 1.5rem);
  font-weight: 700;
  color: #0f172a;
}

.actions {
  display: flex;
  gap: 8px;
}

.card-body {
  padding: 10px 12px 12px;
  min-height: 0;
}

.dag-card .card-body {
  display: flex;
  flex-direction: column;
  flex: 1 1 auto;
  min-height: 0;
  overflow: hidden;
}

.dag-layout {
  position: relative;
  display: flex;
  flex-direction: column;
  min-height: 0;
  height: 100%;
}

.dag-canvas {
  position: relative;
  border: 2px solid rgb(48, 82, 102);
  border-radius: 14px;
  background: #ffffff;
  flex: 1 1 auto;
  min-height: 260px;
  height: auto;
  max-height: 100%;
  overflow: hidden;
  touch-action: none;
}

.muted-text {
  color: #475569;
  padding: 10px;
}

.warning {
  margin-bottom: 10px;
  color: #b45309;
  background: #fff7ed;
  border: 1px solid #fed7aa;
  padding: 8px 10px;
  border-radius: 8px;
}

.ghost-btn {
  border: 1px solid #d7dde7;
  background: #fff;
  border-radius: 8px;
  padding: 6px 12px;
  cursor: pointer;
  color: #0f172a;
}

.ghost-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.code-card .card-body {
  display: flex;
  flex-direction: column;
  gap: 10px;
  flex: 1 1 auto;
  min-height: 0;
  overflow: auto;
}

.node-title {
  font-weight: 700;
  color: #0f172a;
}

.code-section {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.code-label {
  font-size: 12px;
  font-weight: 700;
  color: #475569;
}

.code-block {
  background: #0b1224;
  color: #e2e8f0;
  border-radius: 10px;
  padding: 10px;
  overflow: auto;
  max-height: 220px;
  white-space: pre-wrap;
  font-size: 12px;
  line-height: 1.45;
  font-family: "JetBrains Mono", Consolas, monospace;
}
</style>
