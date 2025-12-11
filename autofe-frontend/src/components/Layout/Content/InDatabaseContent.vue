<template>
  <div class="in-db-content">
    <div class="intro-card">
      <div>
        <h3>Python ➜ SQL AST Visualization</h3>
        <p>Locate stored pipeline code and visualize how py2sql matches operators to SQL.</p>
      </div>
      <button class="primary-btn" :disabled="loading" @click="loadAst">
        {{ loading ? 'Loading...' : 'Generate AST' }}
      </button>
    </div>

    <div class="controls-card">
      <div class="field">
        <label>Dataset</label>
        <select v-model="selectedDataset">
          <option v-for="opt in datasetOptions" :key="opt.value" :value="opt.value">
            {{ opt.label }}
          </option>
        </select>
      </div>
      <div class="field">
        <label>Downstream ML Model</label>
        <select v-model="selectedMlModel">
          <option v-for="opt in mlModelOptions" :key="opt.value" :value="opt.value">
            {{ opt.label }}
          </option>
        </select>
      </div>
      <div class="field">
        <label>Pipeline Hint (optional)</label>
        <input v-model="pipelineId" type="text" placeholder="e.g. pipeline_2" />
      </div>
      <div class="status">
        <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
        <span v-else-if="loading" class="info-text">Parsing pipeline and building AST...</span>
        <span v-else class="muted-text">Uses stored pycodes and py2sql logic to build the tree.</span>
      </div>
    </div>

    <div v-if="astData" class="results">
      <div class="meta-card">
        <div><strong>Dataset:</strong> {{ astData.dataset }}</div>
        <div><strong>Model:</strong> {{ astData.mlModel }}</div>
        <div><strong>Pipeline:</strong> {{ astData.pipelinePath }}</div>
        <div><strong>Detected Columns:</strong> {{ astData.columns.join(', ') || 'N/A' }}</div>
      </div>

      <div
        v-if="astData.finalSql || astData.finalSqlPath"
        class="sql-card"
      >
        <div class="sql-card-header">
          <div class="title">
            最终生成的 SQL
            <span v-if="astData.finalSqlGenerated" class="badge success">实时生成</span>
            <span v-else-if="astData.finalSqlFound" class="badge info">已存在</span>
          </div>
          <div class="sql-actions">
            <button class="ghost-btn" :disabled="!astData.finalSql" @click="copyFinalSql">复制SQL</button>
            <button class="ghost-btn" :disabled="!astData.finalSqlPath" @click="copyFinalSqlPath">复制路径</button>
          </div>
        </div>
        <div class="sql-path" v-if="astData.finalSqlPath">
          <strong>路径:</strong> {{ astData.finalSqlPath }}
        </div>
        <pre class="sql-view" v-if="astData.finalSql">{{ astData.finalSql }}</pre>
        <div v-else class="muted-text">未获取到SQL内容，但路径已提供。</div>
        <div v-if="astData.finalSqlError" class="warning">SQL生成警告：{{ astData.finalSqlError }}</div>
      </div>

      <div class="blocks">
        <div
          v-for="(block, idx) in astData.blocks"
          :key="block.nodeId ?? idx"
          class="block-card"
        >
          <div class="block-header">
            <div class="title">
              Step {{ idx + 1 }} · Node {{ block.nodeId ?? 'N/A' }}
            </div>
            <span class="badge">{{ block.opType }}</span>
          </div>

          <div class="block-meta">
            <div><strong>Read:</strong> {{ block.readColumns.join(', ') || 'N/A' }}</div>
            <div><strong>Write:</strong> {{ block.writeColumns.join(', ') || 'N/A' }}</div>
            <div class="sql-line">
              <strong>SQL:</strong>
              <code>{{ block.sqlSnippet || 'N/A' }}</code>
            </div>
          </div>

          <div class="code-view">
            <div class="label">Python</div>
            <pre>{{ block.code }}</pre>
          </div>

          <div v-if="block.executionError" class="warning">
            Execution warning (dummy scope): {{ block.executionError }}
          </div>

          <div class="tree-section">
            <div class="label">AST</div>
            <AstTreeD3 v-if="block.ast" :node="block.ast" :block-index="idx" />
          </div>
        </div>
      </div>
    </div>

    <div v-else class="placeholder-card">
      <h4>How it works</h4>
      <ul>
        <li>Pick dataset + downstream ML model to locate a test/store folder (e.g., heart_RF_Full).</li>
        <li>Backend loads pycodes/pipeline*.py, runs py2sql parsing (CheckTransformer, etc.), and returns AST.</li>
        <li>Each step lists read/write columns, op type, a SQL sketch, and the Python AST tree.</li>
      </ul>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, defineComponent, onMounted, onUnmounted, watch, ref, h, type PropType } from 'vue'
import { apiService } from '@/services/APIService'
import { useTaskStore } from '@/stores/task'
import type { Py2SqlAstData, Py2SqlAstNode } from '@/types'
import * as d3 from 'd3'

const taskStore = useTaskStore()

const datasetOptions = [
  { label: 'Titanic', value: '1' },
  { label: 'Heart', value: '2' },
  { label: 'Bank', value: '3' },
  { label: 'Diabetes', value: '4' },
  { label: 'Bike', value: '5' },
  { label: 'House', value: '6' }
]

const mlModelOptions = [
  { label: 'Random Forest (RF)', value: 'RF' },
  { label: 'XGBoost (XGB)', value: 'XGB' },
  { label: 'LightGBM', value: 'LightGBM' },
  { label: 'CART', value: 'CART' }
]

const datasetNameMap: Record<string, string> = {
  '1': 'Titanic',
  '2': 'Heart',
  '3': 'Bank',
  '4': 'Diabetes',
  '5': 'Bike',
  '6': 'House'
}

const selectedDataset = ref(taskStore.config.dataset)
const selectedMlModel = ref(taskStore.config.mlModel)
const pipelineId = ref('')

const loading = ref(false)
const errorMessage = ref('')
const astData = ref<Py2SqlAstData | null>(null)

const requestDataset = computed(() => datasetNameMap[selectedDataset.value] || selectedDataset.value)

const AstTreeD3 = defineComponent({
  name: 'AstTreeD3',
  props: {
    node: { type: Object as PropType<Py2SqlAstNode>, required: true },
    blockIndex: { type: Number, required: true }
  },
  setup(props) {
    const container = ref<HTMLElement | null>(null)
    let svgRoot: d3.Selection<SVGSVGElement, unknown, null, undefined> | null = null

    const labelOf = (n: Py2SqlAstNode) => {
      if (n.func) return n.func
      if (n.attr) return n.attr
      if (n.id) return n.id
      if (n.targets) return Array.isArray(n.targets) ? n.targets.join(',') : String(n.targets)
      if (n.value !== undefined) return String(n.value)
      return n.type
    }

    const renderTree = () => {
      if (!container.value || !props.node) return
      d3.select(container.value).selectAll('*').remove()
      svgRoot = null

      const root = d3.hierarchy(props.node as any)
      const nodeW = 140
      const nodeH = 54
      const hSpace = 32
      const vSpace = 76
      const treeLayout = d3.tree<any>().nodeSize([nodeW + hSpace, nodeH + vSpace])
      treeLayout(root)

      let xMin = Infinity; let xMax = -Infinity; let yMin = Infinity; let yMax = -Infinity
      root.descendants().forEach(d => {
        const dx = d.x ?? 0
        const dy = d.y ?? 0
        xMin = Math.min(xMin, dx); xMax = Math.max(xMax, dx)
        yMin = Math.min(yMin, dy); yMax = Math.max(yMax, dy)
      })
      const margin = { top: 32, right: 16, bottom: 32, left: 16 }
      const width = (xMax - xMin) + nodeW + margin.left + margin.right
      const height = Math.max((yMax - yMin) + nodeH + margin.top + margin.bottom, 260)
      const translateX = width / 2 - (xMin + xMax) / 2
      const translateY = margin.top - yMin

      svgRoot = d3.select(container.value)
        .append('svg')
        .attr('width', '100%')
        .attr('height', '100%')
        .attr('viewBox', `0 0 ${width} ${height}`)
        .attr('preserveAspectRatio', 'xMidYMid meet')

      const g = svgRoot.append('g')
        .attr('transform', `translate(${translateX},${translateY})`)

      g.selectAll('.ast-link')
        .data(root.links())
        .enter()
        .append('path')
        .attr('class', 'ast-link')
        .attr('d', d3.linkVertical<any, d3.HierarchyNode<any>>()
          .x((d: any) => d.x ?? 0)
          .y((d: any) => d.y ?? 0) as any)

      const nodes = g.selectAll('.ast-node')
        .data(root.descendants())
        .enter()
        .append('g')
        .attr('class', 'ast-node')
        .attr('transform', (d: any) => `translate(${d.x ?? 0},${d.y ?? 0})`)

      nodes.append('rect')
        .attr('class', 'ast-node-card')
        .attr('x', -nodeW / 2)
        .attr('y', -nodeH / 2)
        .attr('rx', 10)
        .attr('ry', 10)
        .attr('width', nodeW)
        .attr('height', nodeH)

      nodes.append('text')
        .attr('class', 'ast-node-text label')
        .attr('y', -6)
        .attr('text-anchor', 'middle')
        .text((d: any) => labelOf(d.data))

      nodes.append('text')
        .attr('class', 'ast-node-text type')
        .attr('y', 14)
        .attr('text-anchor', 'middle')
        .text((d: any) => d.data.type)
    }

    watch(() => props.node, () => renderTree(), { deep: true, immediate: true })
    onMounted(renderTree)
    onUnmounted(() => {
      if (svgRoot) svgRoot.remove()
    })

    return () => h('div', { class: 'ast-tree', ref: container })
  }
})

async function loadAst() {
  loading.value = true
  errorMessage.value = ''
  try {
    const response = await apiService.getPy2SqlAst({
      dataset: requestDataset.value,
      mlModel: selectedMlModel.value,
      pipelineId: pipelineId.value || undefined
    })
    if (response.status === 'success' && response.data) {
      astData.value = response.data
    } else {
      errorMessage.value = response.message || 'Failed to load AST data'
    }
  } catch (e: any) {
    errorMessage.value = e?.message || 'Unexpected error while loading AST'
  } finally {
    loading.value = false
  }
}

function copyText(text?: string) {
  if (!text) return
  if (navigator?.clipboard?.writeText) {
    navigator.clipboard.writeText(text)
    taskStore.addNotification('已复制到剪贴板', 'success')
  }
}

function copyFinalSql() {
  copyText(astData.value?.finalSql)
}

function copyFinalSqlPath() {
  copyText(astData.value?.finalSqlPath)
}
</script>

<style scoped>
.in-db-content {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 16px;
  background: #f7f9fc;
  min-height: 100%;
}

.intro-card,
.controls-card,
.meta-card,
.block-card,
.placeholder-card {
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  box-shadow: 0 8px 24px rgba(15, 23, 42, 0.06);
}

.intro-card {
  padding: 16px 20px;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.primary-btn {
  background: #2563eb;
  color: #fff;
  border: none;
  border-radius: 8px;
  padding: 10px 16px;
  cursor: pointer;
  font-weight: 600;
}

.primary-btn:disabled {
  opacity: 0.7;
  cursor: not-allowed;
}

.controls-card {
  padding: 16px;
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 12px;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.field label {
  font-weight: 600;
  color: #0f172a;
}

.field select,
.field input {
  border: 1px solid #d7dde7;
  border-radius: 8px;
  padding: 8px 10px;
}

.status {
  grid-column: 1 / -1;
  display: flex;
  align-items: center;
  min-height: 22px;
}

.error-text {
  color: #dc2626;
}

.info-text {
  color: #2563eb;
}

.muted-text {
  color: #475569;
}

.results {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.meta-card {
  padding: 14px 16px;
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 8px;
}

.sql-card {
  padding: 14px 16px;
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  box-shadow: 0 8px 24px rgba(15, 23, 42, 0.06);
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.sql-card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.sql-card .title {
  font-weight: 700;
  color: #0f172a;
  display: flex;
  align-items: center;
  gap: 8px;
}

.sql-actions {
  display: flex;
  gap: 8px;
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

.badge.success {
  background: #ecfdf3;
  color: #15803d;
}

.badge.info {
  background: #eff6ff;
  color: #2563eb;
}

.sql-path {
  font-size: 13px;
  color: #475569;
  word-break: break-all;
}

.sql-view {
  background: #0b1224;
  color: #e2e8f0;
  padding: 12px;
  border-radius: 10px;
  overflow-x: auto;
  font-size: 13px;
  line-height: 1.5;
}

.blocks {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.block-card {
  padding: 14px 16px;
}

.block-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}

.block-header .title {
  font-weight: 700;
  color: #0f172a;
}

.badge {
  background: #eef2ff;
  color: #4338ca;
  border-radius: 999px;
  padding: 4px 10px;
  font-size: 12px;
  font-weight: 700;
}

.block-meta {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 8px;
  margin-bottom: 10px;
  color: #0f172a;
}

.sql-line code {
  background: #0f172a;
  color: #f8fafc;
  padding: 3px 6px;
  border-radius: 6px;
  font-family: "JetBrains Mono", monospace;
}

.code-view,
.tree-section {
  margin-top: 10px;
}

.label {
  font-size: 12px;
  color: #475569;
  margin-bottom: 4px;
}

pre {
  background: #0b1224;
  color: #e2e8f0;
  padding: 12px;
  border-radius: 10px;
  overflow-x: auto;
  font-size: 13px;
  line-height: 1.5;
}

.warning {
  margin-top: 6px;
  color: #b45309;
  background: #fff7ed;
  border: 1px solid #fed7aa;
  padding: 8px 10px;
  border-radius: 8px;
}

.tree-section {
  border: 1px dashed #cbd5e1;
  border-radius: 10px;
  padding: 10px;
  background: #f8fafc;
}

.ast-tree {
  width: 100%;
  min-height: 260px;
  height: 280px;
}

.ast-tree :deep(svg) {
  width: 100%;
  height: 100%;
}

.ast-tree :deep(.ast-link) {
  fill: none;
  stroke: #cbd5e1;
  stroke-width: 1.4px;
}

.ast-tree :deep(.ast-node-card) {
  fill: #ffffff;
  stroke: #d7dde7;
  stroke-width: 1.1px;
  filter: drop-shadow(0px 2px 6px rgba(15, 23, 42, 0.08));
}

.ast-tree :deep(.ast-node-text) {
  font-family: "Inter", "Helvetica Neue", Arial, sans-serif;
  fill: #0f172a;
}

.ast-tree :deep(.ast-node-text.label) {
  font-weight: 700;
  font-size: 12px;
}

.ast-tree :deep(.ast-node-text.type) {
  fill: #64748b;
  font-size: 11px;
}

.placeholder-card {
  padding: 16px;
}

.placeholder-card ul {
  margin: 0;
  padding-left: 18px;
  color: #475569;
}
</style>