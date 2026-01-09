<template>
  <div class="in-db-content">
    <div class="intro-card">
      <div>
        <h3>Python ➜ SQL Visualization</h3>
        <!-- <p>Locate stored pipeline code and visualize how py2sql matches operators to SQL.</p> -->
      </div>
    </div>


  <div v-if="astData" class="results">
      <!-- <div class="meta-card">
        <div><strong>Dataset:</strong> {{ astData.dataset }}</div>
        <div><strong>Model:</strong> {{ astData.mlModel }}</div>
        <div><strong>Pipeline:</strong> {{ astData.pipelinePath }}</div>
        <div><strong>Detected Columns:</strong> {{ astData.columns.join(', ') || 'N/A' }}</div>
      </div> -->

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

      <!-- 分页器 -->
      <div v-if="totalPages > 1" class="pagination-container">
        <button
          class="pagination-btn"
          :disabled="currentPage === 0"
          @click="goToPrevPage"
        >
          上一页
        </button>

        <span class="pagination-info">
          {{ currentPage + 1 }} / {{ totalPages }}
        </span>

        <button
          class="pagination-btn"
          :disabled="currentPage >= totalPages - 1"
          @click="goToNextPage"
        >
          下一页
        </button>
      </div>

      <div class="blocks">
        <div
          v-if="currentBlock"
          :key="currentBlock.nodeId ?? currentPage"
          class="block-card"
        >
          <div class="block-header">
            <div class="title">
              Step {{ currentPage + 1 }} · Node {{ currentBlock.nodeId ?? 'N/A' }}
            </div>
            <span class="badge">{{ currentBlock.opType }}</span>
          </div>

          <!-- 语义聚合视图 -->
          <div v-if="displaySemanticNode" class="semantic-card">
            <div class="semantic-header">
              <div class="semantic-title">
                <span class="dot" :style="{ backgroundColor: displaySemanticNode.color || '#6c757d' }"></span>
                {{ displaySemanticNode.displayName }}
              </div>
              <div class="semantic-badges">
                <span class="chip" :class="displaySemanticNode.type === 'udf' ? 'chip-error' : 'chip-primary'">
                  {{ displaySemanticNode.type === 'udf' ? 'UDF (Python)' : 'Operator' }}
                </span>
                <span v-if="displaySemanticNode.sqlConvertible" class="chip chip-success">可转SQL</span>
                <span v-else class="chip chip-warning">需UDF / 暂不转SQL</span>
              </div>
            </div>

            <div class="semantic-flow">
              <div class="flow-column">
                <div class="flow-label">Inputs</div>
                <div class="tag" v-for="inp in displaySemanticNode.inputs" :key="`in-${inp}`">{{ inp }}</div>
              </div>

              <div
                class="flow-operator"
                :style="{ backgroundColor: displaySemanticNode.color || '#6c757d' }"
              >
                <div class="op-name">{{ displaySemanticNode.displayName }}</div>
                <div class="op-sub">{{ currentBlock.opType }}</div>
                <div v-if="paramSummary" class="op-params">参数: {{ paramSummary }}</div>
              </div>

              <div class="flow-column">
                <div class="flow-label">Outputs</div>
                <div class="tag" v-for="out in displaySemanticNode.outputs" :key="`out-${out}`">{{ out }}</div>
              </div>
            </div>

            <div class="semantic-actions">
              <label class="toggle">
                <input type="checkbox" v-model="showPreviewAst" :disabled="!hasAnyAst" />
                <span>展示AST预览</span>
              </label>
              <label class="toggle">
                <input type="checkbox" v-model="showRawAst" :disabled="!hasAnyAst" />
                <span>下钻完整AST</span>
              </label>
            </div>
          </div>

          <div class="block-meta">
            <div><strong>Read:</strong> {{ currentBlock.readColumns.join(', ') || 'N/A' }}</div>
            <div><strong>Write:</strong> {{ currentBlock.writeColumns.join(', ') || 'N/A' }}</div>
            <div class="sql-line">
              <strong>SQL:</strong>
              <code>{{ currentBlock.sqlSnippet || 'N/A' }}</code>
            </div>
          </div>

          <div v-if="currentBlock.executionError" class="warning">
            Execution warning (dummy scope): {{ currentBlock.executionError }}
          </div>

          <div class="code-ast-container">
            <div class="tree-section">
              <div class="label">
                AST
                <span v-if="showRawAst" class="muted-text">(完整)</span>
                <span v-else-if="showPreviewAst" class="muted-text">(预览)</span>
              </div>
              <div v-if="currentAstNode" class="ast-wrapper">
                <AstTreeD3 :node="currentAstNode" :block-index="currentPage" />
              </div>
              <div v-else class="muted-text">已隐藏AST</div>
            </div>

            <div class="code-view monaco-card">
              <div class="label">Python</div>
              <div class="monaco-wrapper">
                <VueMonacoEditor
                  v-model:value="monacoCode"
                  theme="vs-dark"
                  language="python"
                  :options="monacoOptions"
                />
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

          <!-- 分页器 -->
          <div v-if="totalPages > 1" class="pagination-container">
        <button
          class="pagination-btn"
          :disabled="currentPage === 0"
          @click="goToPrevPage"
        >
          Previous
        </button>

        <span class="pagination-info">
          {{ currentPage + 1 }} / {{ totalPages }}
        </span>

        <button
          class="pagination-btn"
          :disabled="currentPage >= totalPages - 1"
          @click="goToNextPage"
        >
          Next
        </button>
      </div>

    <!-- <div v-else class="placeholder-card">
      <h4>How it works</h4>
      <ul>
        <li>Pick dataset + downstream ML model to locate a test/store folder (e.g., heart_RF_Full).</li>
        <li>Backend loads pycodes/pipeline*.py, runs py2sql parsing (CheckTransformer, etc.), and returns AST.</li>
        <li>Each step lists read/write columns, op type, a SQL sketch, and the Python AST tree.</li>
      </ul>
    </div> -->
  </div>
</template>

<script setup lang="ts">
import { computed, defineComponent, onMounted, onUnmounted, watch, ref, h, type PropType } from 'vue'
import { apiService } from '@/services/APIService'
import { useTaskStore } from '@/stores/task'
import { useWorkspaceStore } from '@/stores/workspace'
import type { Py2SqlAstData, Py2SqlAstNode } from '@/types'
import * as d3 from 'd3'
import { VueMonacoEditor } from '@guolao/vue-monaco-editor'

const taskStore = useTaskStore()
const workspaceStore = useWorkspaceStore()

// Dataset name mapping for display
const datasetNameMap: Record<string, string> = {
  '1': 'Titanic',
  '2': 'Heart',
  '3': 'Bank',
  '4': 'Diabetes',
  '5': 'Bike',
  '6': 'House'
}

const loading = ref(false)
const errorMessage = ref('')
const astData = ref<Py2SqlAstData | null>(null)
const monacoCode = ref('')
const monacoOptions = {
  readOnly: true,
  minimap: { enabled: false },
  wordWrap: 'on',
  lineNumbers: 'on',
  scrollBeyondLastLine: false,
  automaticLayout: true,
  fontSize: 14,
  fontFamily: 'JetBrains Mono, Consolas, monospace'
}

// 分页状态
const currentPage = ref(0)
const itemsPerPage = 1

// 分页计算属性
const totalPages = computed(() => {
  if (!astData.value?.blocks) return 0
  return Math.ceil(astData.value.blocks.length / itemsPerPage)
})

const currentBlock = computed(() => {
  if (!astData.value?.blocks || currentPage.value >= totalPages.value) return null
  return astData.value.blocks[currentPage.value]
})

const displaySemanticNode = computed(() => {
  const block = currentBlock.value
  if (!block) return null
  if (block.semanticNode) return block.semanticNode
  // 后端未升级时的回退：用 opType + read/write 生成简易节点
  return {
    type: block.opType === 'UNSUPPORT' ? 'udf' : 'operator',
    displayName: block.opType || 'Operator',
    inputs: block.readColumns || [],
    outputs: block.writeColumns || (block.readColumns || []),
    parameters: {},
    color: '#6c757d',
    sqlConvertible: block.opType !== 'UNSUPPORT'
  }
})

const displaySemanticAst = computed(() => {
  const block = currentBlock.value
  if (!block) return null
  if (block.semanticAst) return block.semanticAst
  // 回退：用现有AST作为预览/原始，构造简单连边
  const edges = (block.readColumns || []).flatMap(src =>
    (block.writeColumns || []).map(dst => ({ from: src, to: dst }))
  )
  return {
    summaryNode: displaySemanticNode.value!,
    previewAst: block.ast,
    rawAst: block.ast,
    edges,
    drillDownAvailable: !!block.ast
  }
})

const showPreviewAst = ref(true)
const showRawAst = ref(false)

const hasAnyAst = computed(() => {
  const block = currentBlock.value
  return !!(displaySemanticAst.value?.previewAst || displaySemanticAst.value?.rawAst || block?.ast)
})

const currentAstNode = computed(() => {
  const block = currentBlock.value
  if (!block) return null
  const astView = displaySemanticAst.value
  if (showRawAst.value) return astView?.rawAst || block.ast
  if (showPreviewAst.value) return astView?.previewAst || block.ast
  return null
})

const paramSummary = computed(() => {
  const params = displaySemanticNode.value?.parameters || {}
  const entries = Object.entries(params)
  if (!entries.length) return ''
  return entries.slice(0, 3).map(([k, v]) => `${k}: ${String(v)}`).join(' · ')
})

watch(currentBlock, (block) => {
  monacoCode.value = block?.code || ''
  showPreviewAst.value = true
  showRawAst.value = false
}, { immediate: true })

// 监听执行触发器
watch(() => workspaceStore.executionTrigger, () => {
  loadAst()
})


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
      const height = Math.max((yMax - yMin) + nodeH + margin.top + margin.bottom, 500)
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
      dataset: datasetNameMap[taskStore.config.dataset] || taskStore.config.dataset,
      mlModel: taskStore.config.mlModel,
      pipelineId: undefined // Removed pipeline hint for now
    })
    if (response.status === 'success' && response.data) {
      astData.value = response.data
      resetPagination()
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
    taskStore.addNotification('Copied to clipboard', 'success')
  }
}

function copyFinalSql() {
  copyText(astData.value?.finalSql)
}

function copyFinalSqlPath() {
  copyText(astData.value?.finalSqlPath)
}

// 分页方法
function goToPage(page: number) {
  if (page >= 0 && page < totalPages.value) {
    currentPage.value = page
  }
}

function goToPrevPage() {
  goToPage(currentPage.value - 1)
}

function goToNextPage() {
  goToPage(currentPage.value + 1)
}

function resetPagination() {
  currentPage.value = 0
}

onMounted(() => {
  loadAst()
})
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
.meta-card,
.dag-card,
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

.dag-card {
  padding: 14px 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.dag-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.dag-layout {
  position: relative;
  display: block;
  gap: 16px;
}

.dag-canvas {
  position: relative;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  background: #ffffff;
  min-height: 260px;
  padding: 0;
  overflow: hidden;
}

.pipeline-link {
  fill: none;
  stroke: #64748b;
  stroke-width: 2;
  transition: stroke 0.2s;
}

.pipeline-link:hover {
  stroke: #3b82f6;
}

.pipeline-node rect {
  fill: #2563eb;
  stroke: #1e40af;
  stroke-width: 1.5;
  rx: 6;
}

.pipeline-node text {
  fill: #f8fafc;
  font-size: 11px;
  text-anchor: middle;
  pointer-events: none;
}

.dag-tooltip {
  position: absolute;
  z-index: 10;
  width: 320px;
  max-height: min(520px, calc(100% - 24px));
  overflow: auto;
  border-radius: 14px;
  background: #0b1224;
  color: #e2e8f0;
  border: 1px solid rgba(148, 163, 184, 0.4);
  box-shadow: 0 18px 40px rgba(15, 23, 42, 0.4);
  padding: 12px;
  pointer-events: auto;
}

.tooltip-title {
  font-weight: 700;
  color: #f8fafc;
  margin-bottom: 8px;
}

.tooltip-section {
  margin-bottom: 8px;
}

.tooltip-label {
  font-size: 11px;
  font-weight: 600;
  color: #93c5fd;
  margin-bottom: 4px;
}

.tooltip-code {
  background: #111b33;
  border-radius: 8px;
  padding: 8px;
  font-size: 11px;
  line-height: 1.4;
  max-height: none;
  overflow: visible;
  white-space: pre-wrap;
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

.code-ast-container {
  display: flex;
  flex-direction: column;
  gap: 16px;
  margin-top: 10px;
}

.semantic-card {
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  padding: 12px 14px;
  background: #f9fafb;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.semantic-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
}

.semantic-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 600;
  color: #0f172a;
}

.semantic-badges {
  display: flex;
  gap: 6px;
  align-items: center;
}

.dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  display: inline-block;
}

.chip {
  padding: 2px 8px;
  border-radius: 999px;
  font-size: 12px;
  background: #e2e8f0;
  color: #0f172a;
}

.chip-primary { background: #e0ecff; color: #1d4ed8; }
.chip-success { background: #e6f9f0; color: #15803d; }
.chip-warning { background: #fff4e6; color: #b45309; }
.chip-error { background: #fdecee; color: #b91c1c; }

.semantic-flow {
  display: grid;
  grid-template-columns: 1fr auto 1fr;
  align-items: center;
  gap: 12px;
}

.flow-column {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.flow-label {
  font-size: 12px;
  color: #475569;
}

.flow-operator {
  min-width: 220px;
  padding: 12px;
  border-radius: 12px;
  color: #ffffff;
  text-align: center;
  box-shadow: 0 4px 14px rgba(0, 0, 0, 0.08);
}

.op-name {
  font-weight: 700;
  font-size: 15px;
}

.op-sub {
  font-size: 12px;
  opacity: 0.9;
}

.op-params {
  margin-top: 6px;
  font-size: 12px;
  opacity: 0.9;
}

.tag {
  display: inline-flex;
  align-items: center;
  padding: 4px 10px;
  background: #eef2ff;
  color: #4338ca;
  border-radius: 8px;
  width: fit-content;
  font-size: 13px;
}

.semantic-actions {
  display: flex;
  gap: 12px;
  align-items: center;
  flex-wrap: wrap;
  color: #475569;
  font-size: 13px;
}

.toggle {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.ast-wrapper {
  border: 1px dashed #e2e8f0;
  border-radius: 10px;
  padding: 8px;
  background: #fff;
}

.code-ast-container .code-view {
  margin-top: 0;
}

.code-ast-container .tree-section {
  margin-top: 0;
}

.code-view,
.tree-section {
  margin-top: 10px;
}

.monaco-card {
  display: flex;
  flex-direction: column;
}

.monaco-wrapper {
  border: 1px solid #334155;
  border-radius: 10px;
  overflow: hidden;
  background: #0b1224;
  min-height: 280px;
  height: 320px;
  max-height: 380px;
}

.monaco-wrapper :deep(.monaco-editor),
.monaco-wrapper :deep(.monaco-editor .overflow-guard) {
  height: 100% !important;
}

.monaco-wrapper :deep(.monaco-editor) {
  background: #0b1224;
}

.label {
  font-size: 12px;
  color: #475569;
  margin-bottom: 4px;
}

/* 原有的pre样式已移至code-content */

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
  min-height: 400px;
  height: 500px;
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

/* 分页器样式 */
.pagination-container {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 16px;
  padding: 12px 0;
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  box-shadow: 0 8px 24px rgba(15, 23, 42, 0.06);
  margin-bottom: 12px;
}

.pagination-btn {
  border: 1px solid #d7dde7;
  background: #fff;
  border-radius: 8px;
  padding: 8px 16px;
  cursor: pointer;
  color: #0f172a;
  font-weight: 500;
  transition: all 0.2s ease;
}

.pagination-btn:hover:not(:disabled) {
  background: #f8fafc;
  border-color: #cbd5e1;
}

.pagination-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
  background: #f1f5f9;
}

.pagination-info {
  font-weight: 600;
  color: #0f172a;
  font-size: 14px;
  min-width: 60px;
  text-align: center;
}
</style>
