<template>
  <div class="in-db-panel">
    <div class="card">
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
import { computed, onMounted, ref, watch } from 'vue'
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
  const nodeWidth = 180
  const nodeHeight = 60

  const inDegree = new Map(nodes.map(n => [n.nodeId, 0]))
  const adjacency = new Map(nodes.map(n => [n.nodeId, [] as number[]]))
  edges.forEach(edge => {
    if (adjacency.has(edge.from)) adjacency.get(edge.from)!.push(edge.to)
    inDegree.set(edge.to, (inDegree.get(edge.to) || 0) + 1)
  })

  const startNodes = nodes.filter(n => (inDegree.get(n.nodeId) || 0) === 0)
  const isLinear =
    edges.length === nodes.length - 1 &&
    nodes.every(n => (inDegree.get(n.nodeId) || 0) <= 1 && (adjacency.get(n.nodeId)?.length || 0) <= 1) &&
    startNodes.length === 1

  const positions = new Map<number, { x: number; y: number }>()
  let width = 740
  let height = 300

  if (isLinear) {
    const order: Py2SqlDagNode[] = []
    let cur = startNodes[0]
    const visited = new Set<number>()
    while (cur && !visited.has(cur.nodeId)) {
      order.push(cur)
      visited.add(cur.nodeId)
      const nextId = (adjacency.get(cur.nodeId) || [])[0]
      cur = nodes.find(n => n.nodeId === nextId) as Py2SqlDagNode
    }

    const perRow = 4
    const rowCount = Math.ceil(order.length / perRow)
    const colWidth = 260
    const rowHeight = 160
    width = Math.max(740, perRow * colWidth)
    height = Math.max(300, rowCount * rowHeight + 60)

    order.forEach((node, idx) => {
      const row = Math.floor(idx / perRow)
      const colInRow = idx % perRow
      const rowNodes = order.slice(row * perRow, row * perRow + perRow)
      const actualCols = rowNodes.length
      const col = row % 2 === 0 ? colInRow : (actualCols - 1 - colInRow)
      const x = (col + 1) * (width / (Math.max(actualCols, 1) + 1))
      const y = (row + 1) * rowHeight
      positions.set(node.nodeId, { x, y })
    })
  } else {
    const level = new Map<number, number>()
    const indeg = new Map(inDegree)
    const queue: number[] = []
    nodes.forEach(n => {
      if ((indeg.get(n.nodeId) || 0) === 0) {
        queue.push(n.nodeId)
        level.set(n.nodeId, 0)
      }
    })
    while (queue.length > 0) {
      const curNode = queue.shift()!
      const curLevel = level.get(curNode) || 0
      const nexts = adjacency.get(curNode) || []
      nexts.forEach(next => {
        const nextLevel = Math.max(level.get(next) || 0, curLevel + 1)
        level.set(next, nextLevel)
        indeg.set(next, (indeg.get(next) || 0) - 1)
        if ((indeg.get(next) || 0) === 0) queue.push(next)
      })
    }
    nodes.forEach(n => {
      if (!level.has(n.nodeId)) level.set(n.nodeId, 0)
    })

    const levels: Record<number, Py2SqlDagNode[]> = {}
    nodes.forEach(n => {
      const l = level.get(n.nodeId) || 0
      if (!levels[l]) levels[l] = []
      levels[l].push(n)
    })

    const levelKeys = Object.keys(levels).map(Number).sort((a, b) => a - b)
    const maxPerLevel = Math.max(...levelKeys.map(k => (levels[k]?.length ?? 0)), 1)
    width = Math.max(740, maxPerLevel * 240)
    height = Math.max(300, levelKeys.length * 160)

    levelKeys.forEach((lvl, idx) => {
      const row = levels[lvl] || []
      row.forEach((node, i) => {
        const x = (i + 1) * (width / (row.length + 1))
        const y = (idx + 1) * 140
        positions.set(node.nodeId, { x, y })
      })
    })
  }

  const svg = d3.select(container)
    .append('svg')
    .attr('width', '100%')
    .attr('height', height)
    .attr('viewBox', `0 0 ${width} ${height}`)
    .attr('preserveAspectRatio', 'xMidYMid meet')
    .style('overflow', 'visible')

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
    .attr('fill', '#64748b')

  const pattern = defs.append('pattern')
    .attr('id', `grid-pattern-${markerId}`)
    .attr('width', 20)
    .attr('height', 20)
    .attr('patternUnits', 'userSpaceOnUse')
  pattern.append('circle')
    .attr('cx', 1)
    .attr('cy', 1)
    .attr('r', 1)
    .attr('fill', '#e2e8f0')

  svg.append('rect')
    .attr('width', '100%')
    .attr('height', '100%')
    .attr('fill', `url(#grid-pattern-${markerId})`)

  const edgePath = (src?: { x: number; y: number }, dst?: { x: number; y: number }) => {
    if (!src || !dst) return ''
    const dx = dst.x - src.x
    const dy = dst.y - src.y
    if (dx === 0 && dy === 0) return ''

    const absDx = Math.abs(dx)
    const absDy = Math.abs(dy)

    if (absDx >= absDy) {
      const sx = src.x + Math.sign(dx) * (nodeWidth / 2)
      const ex = dst.x - Math.sign(dx) * (nodeWidth / 2)
      const sy = src.y
      const ey = dst.y
      const c1x = sx + dx * 0.4
      const c1y = sy
      const c2x = ex - dx * 0.4
      const c2y = ey
      return `M${sx},${sy} C${c1x},${c1y} ${c2x},${c2y} ${ex},${ey}`
    }

    const sy = src.y + Math.sign(dy) * (nodeHeight / 2)
    const ey = dst.y - Math.sign(dy) * (nodeHeight / 2)
    const sx = src.x
    const ex = dst.x
    const c1x = sx
    const c1y = sy + dy * 0.4
    const c2x = ex
    const c2y = ey - dy * 0.4
    return `M${sx},${sy} C${c1x},${c1y} ${c2x},${c2y} ${ex},${ey}`
  }

  const linkGroup = svg.append('g').attr('class', 'links')
  linkGroup.selectAll('.pipeline-link-halo')
    .data(edges)
    .enter()
    .append('path')
    .attr('class', 'pipeline-link-halo')
    .attr('d', d => edgePath(positions.get(d.from), positions.get(d.to)))
    .style('fill', 'none')
    .style('stroke', '#ffffff')
    .style('stroke-width', '4px')

  linkGroup.selectAll('.pipeline-link')
    .data(edges)
    .enter()
    .append('path')
    .attr('class', 'pipeline-link')
    .attr('marker-end', `url(#${markerId})`)
    .attr('d', d => edgePath(positions.get(d.from), positions.get(d.to)))
    .style('fill', 'none')
    .style('stroke', '#64748b')
    .style('stroke-width', '2px')

  const nodeGroup = svg.selectAll('.pipeline-node')
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
      svg.selectAll('.node-stroke')
        .style('stroke', '#94a3b8')
        .style('stroke-width', 1)
      d3.select(_event.currentTarget).selectAll('.node-stroke')
        .style('stroke', '#3b82f6')
        .style('stroke-width', 2)
    })

  nodeGroup.each(function (d) {
    const g = d3.select(this)
    const isUdf = (d.udfSnippets && d.udfSnippets.length > 0) || d.opType === 'UDF' || d.opType === 'APPLY'

    if (d.opType === 'START') {
      const r = 24
      const h = 16
      const stackH = 14
      g.append('path')
        .attr('class', 'node-stroke')
        .attr('d', `M ${-r} ${stackH} v ${stackH} c 0 ${h} ${2 * r} ${h} ${2 * r} 0 v ${-stackH}`)
        .style('fill', '#ffffff')
        .style('stroke', '#94a3b8')
        .style('stroke-width', 1)

      g.append('ellipse')
        .attr('class', 'node-stroke')
        .attr('cx', 0).attr('cy', stackH)
        .attr('rx', r).attr('ry', h / 2)
        .style('fill', '#ffffff')
        .style('stroke', '#94a3b8')
        .style('stroke-width', 1)

      g.append('path')
        .attr('class', 'node-stroke')
        .attr('d', `M ${-r} 0 v ${stackH} c 0 ${h} ${2 * r} ${h} ${2 * r} 0 v ${-stackH}`)
        .style('fill', '#ffffff')
        .style('stroke', '#94a3b8')
        .style('stroke-width', 1)

      g.append('ellipse')
        .attr('class', 'node-stroke')
        .attr('cx', 0).attr('cy', 0)
        .attr('rx', r).attr('ry', h / 2)
        .style('fill', '#ffffff')
        .style('stroke', '#94a3b8')
        .style('stroke-width', 1)

      g.append('path')
        .attr('class', 'node-stroke')
        .attr('d', `M ${-r} ${-stackH} v ${stackH} c 0 ${h} ${2 * r} ${h} ${2 * r} 0 v ${-stackH}`)
        .style('fill', '#ffffff')
        .style('stroke', '#94a3b8')
        .style('stroke-width', 1)

      g.append('ellipse')
        .attr('class', 'node-stroke')
        .attr('cx', 0).attr('cy', -stackH)
        .attr('rx', r).attr('ry', h / 2)
        .style('fill', '#ffffff')
        .style('stroke', '#94a3b8')
        .style('stroke-width', 1)

      const bitSz = 4
      const bitX = r - 8
      const bitY1 = -stackH + 4
      const bitY2 = 4
      const bitY3 = stackH + 4
      const drawBits = (y: number) => {
        g.append('rect').attr('x', bitX).attr('y', y).attr('width', bitSz).attr('height', bitSz).style('fill', '#334155')
        g.append('rect').attr('x', bitX - 6).attr('y', y).attr('width', bitSz).attr('height', bitSz).style('fill', '#334155')
        g.append('rect').attr('x', bitX).attr('y', y + 6).attr('width', bitSz).attr('height', bitSz).style('fill', '#334155')
        g.append('rect').attr('x', bitX - 6).attr('y', y + 6).attr('width', bitSz).attr('height', bitSz).style('fill', '#334155')
      }
      drawBits(bitY1)
      drawBits(bitY2)
      drawBits(bitY3)
      return
    }

    if (d.opType === 'END') {
      const w = 60
      const h = 50
      const x = -w / 2
      const y = -h / 2

      g.append('rect')
        .attr('class', 'node-stroke')
        .attr('x', x).attr('y', y)
        .attr('width', w).attr('height', h)
        .attr('rx', 2)
        .style('fill', '#ffffff')
        .style('stroke', '#94a3b8')
        .style('stroke-width', 1)

      g.append('rect')
        .attr('x', x).attr('y', y)
        .attr('width', w).attr('height', 12)
        .attr('rx', 2)
        .style('fill', '#1e40af')

      g.append('line').attr('x1', x + w / 4).attr('y1', y + 12).attr('x2', x + w / 4).attr('y2', y + h).style('stroke', '#cbd5e1').style('stroke-width', 1)
      g.append('line').attr('x1', x + w / 2).attr('y1', y + 12).attr('x2', x + w / 2).attr('y2', y + h).style('stroke', '#cbd5e1').style('stroke-width', 1)
      g.append('line').attr('x1', x + 3 * w / 4).attr('y1', y + 12).attr('x2', x + 3 * w / 4).attr('y2', y + h).style('stroke', '#cbd5e1').style('stroke-width', 1)

      const rowH = (h - 12) / 4
      for (let i = 1; i < 4; i++) {
        g.append('line')
          .attr('x1', x).attr('y1', y + 12 + i * rowH)
          .attr('x2', x + w).attr('y2', y + 12 + i * rowH)
          .style('stroke', '#cbd5e1').style('stroke-width', 1)
      }

      g.append('rect').attr('x', x).attr('y', y + 12).attr('width', w / 4).attr('height', rowH).style('fill', '#f1f5f9')
      g.append('rect').attr('x', x).attr('y', y + 12 + 2 * rowH).attr('width', w / 4).attr('height', rowH).style('fill', '#f1f5f9')
      return
    }

    const headerColor = isUdf ? '#ea580c' : '#3b82f6'
    const headerH = 26
    const bodyColor = isUdf ? '#ffedd5' : '#ffffff'
    const headerText = (d.opType || 'NODE').toUpperCase()
    const cols = d.writeColumns?.length ? d.writeColumns : d.readColumns
    const labelText = (cols && cols.length) ? cols.slice(0, 2).join(',') : 'feature'

    g.append('rect')
      .attr('class', 'node-stroke')
      .attr('x', -nodeWidth / 2).attr('y', -nodeHeight / 2)
      .attr('width', nodeWidth).attr('height', nodeHeight)
      .attr('rx', 8).attr('ry', 8)
      .style('fill', bodyColor)
      .style('stroke', '#94a3b8')
      .style('stroke-width', 1)

    g.append('path')
      .attr('d', `M ${-nodeWidth / 2} ${-nodeHeight / 2 + headerH} L ${-nodeWidth / 2} ${-nodeHeight / 2 + 8} Q ${-nodeWidth / 2} ${-nodeHeight / 2} ${-nodeWidth / 2 + 8} ${-nodeHeight / 2} L ${nodeWidth / 2 - 8} ${-nodeHeight / 2} Q ${nodeWidth / 2} ${-nodeHeight / 2} ${nodeWidth / 2} ${-nodeHeight / 2 + 8} L ${nodeWidth / 2} ${-nodeHeight / 2 + headerH} Z`)
      .style('fill', headerColor)

    g.append('text')
      .attr('x', 0)
      .attr('y', -nodeHeight / 2 + 18)
      .attr('text-anchor', 'middle')
      .style('font-size', '12px')
      .style('font-weight', '700')
      .style('fill', '#ffffff')
      .style('pointer-events', 'none')
      .text(headerText)

    g.append('text')
      .attr('x', 0)
      .attr('y', 10)
      .attr('text-anchor', 'middle')
      .style('font-family', 'monospace')
      .style('font-size', '14px')
      .style('font-weight', '600')
      .style('fill', '#1e293b')
      .style('pointer-events', 'none')
      .text(labelText)

    if (isUdf) {
      const iconX = nodeWidth / 2 - 10
      const iconY = -nodeHeight / 2 - 10
      const pyGroup = g.append('g').attr('transform', `translate(${iconX}, ${iconY}) scale(0.8)`)
      pyGroup.append('path')
        .attr('d', 'M 9.9 0 C 4.5 0 2.5 3 2.5 3 L 2.5 5.5 L 6 5.5 C 6 5.5 6 3 9.9 3 C 13.8 3 13.8 5.7 13.8 5.7 L 13.8 7.3 L 5.5 7.3 C 1 7.3 0 11.5 0 11.5 L 0 16.5 C 0 21 5.5 21 5.5 21 L 9.5 21 L 9.5 17.5 C 9.5 14.5 9.5 13.5 12.5 13.5 L 18.5 13.5 C 18.5 13.5 18.5 10 18.5 5.5 C 18.5 0 9.9 0 9.9 0 Z M 7 1.5 C 7.8 1.5 8.5 2.2 8.5 3 C 8.5 3.8 7.8 4.5 7 4.5 C 6.2 4.5 5.5 3.8 5.5 3 C 5.5 2.2 6.2 1.5 7 1.5 Z')
        .style('fill', '#3776ab')
      pyGroup.append('path')
        .attr('d', 'M 12.3 22 C 17.7 22 19.7 19 19.7 19 L 19.7 16.5 L 16.2 16.5 C 16.2 16.5 16.2 19 12.3 19 C 8.4 19 8.4 16.3 8.4 16.3 L 8.4 14.7 L 16.7 14.7 C 21.2 14.7 22.2 10.5 22.2 10.5 L 22.2 5.5 C 22.2 1 16.7 1 16.7 1 L 12.7 1 L 12.7 4.5 C 12.7 7.5 12.7 8.5 9.7 8.5 L 3.7 8.5 C 3.7 8.5 3.7 12 3.7 16.5 C 3.7 22 12.3 22 12.3 22 Z M 15.2 20.5 C 14.4 20.5 13.7 19.8 13.7 19 C 13.7 18.2 14.4 17.5 15.2 17.5 C 16 17.5 16.7 18.2 16.7 19 C 16.7 19.8 16 20.5 15.2 20.5 Z')
        .style('fill', '#ffd343')
    }
  })
}

watch(dag, () => {
  renderDag()
})

watch(() => taskStore.featureSearchStartedAt, (ts) => {
  if (ts) {
    loadDag()
  }
})

onMounted(() => {
  // Keep this lightweight: the DAG is loaded when feature search starts.
  // If a search is already in progress (reload page), load it immediately.
  if (taskStore.agentSearchStatus === 'running') {
    loadDag()
  }
})
</script>

<style scoped>
.in-db-panel {
  display: flex;
  flex-direction: column;
  gap: 12px;
  height: 100%;
  min-height: 0;
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

.dag-layout {
  position: relative;
}

.dag-canvas {
  position: relative;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  background: #ffffff;
  min-height: 260px;
  overflow: hidden;
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
