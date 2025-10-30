<template>
  <div class="performance-comparison-chart">
    <div class="panel-header">
      <div class="panel-title">
        <i class="bi bi-bar-chart-line"></i>
        Performance Comparison
      </div>
      <div class="panel-actions">
        <div class="metric-toggle">
          <button
            class="metric-btn"
            :class="{ active: selectedMetric === 'auc' }"
            @click="setMetric('auc')"
          >
            AUC
          </button>
          <button
            class="metric-btn"
            :class="{ active: selectedMetric === 'f1' }"
            @click="setMetric('f1')"
          >
            F1-Score
          </button>
        </div>
        <button
          class="btn-icon"
          @click="exportChart"
          title="Export chart"
        >
          <i class="bi bi-download"></i>
        </button>
      </div>
    </div>

    <div class="chart-container">
      <div ref="chartRef" class="performance-chart"></div>

      <!-- 图表说明 -->
      <div class="chart-legend">
        <div class="legend-item">
          <div class="legend-color adda-color"></div>
          <span>Adda (Our Method)</span>
        </div>
        <div class="legend-item">
          <div class="legend-color baseline-color"></div>
          <span>Baseline Methods</span>
        </div>
      </div>

      <!-- 统计信息 -->
      <div class="stats-summary">
        <div class="stat-item">
          <span class="stat-label">Best Method:</span>
          <span class="stat-value best-method">{{ bestMethod }}</span>
        </div>
        <div class="stat-item">
          <span class="stat-label">Improvement:</span>
          <span class="stat-value improvement">+{{ improvement.toFixed(2) }}%</span>
        </div>
        <div class="stat-item">
          <span class="stat-label">Average:</span>
          <span class="stat-value">{{ averageScore.toFixed(3) }}</span>
        </div>
      </div>
    </div>

    <!-- 鼠标悬停提示 -->
    <div
      v-if="tooltip.show"
      class="chart-tooltip"
      :style="tooltip.style"
    >
      <div class="tooltip-header">{{ tooltip.data.method }}</div>
      <div class="tooltip-content">
        <div class="tooltip-row">
          <span>{{ selectedMetric.toUpperCase() }}:</span>
          <strong>{{ tooltip.data.value.toFixed(3) }}</strong>
        </div>
        <div class="tooltip-row">
          <span>Rank:</span>
          <strong>#{{ tooltip.data.rank }}</strong>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'
import * as d3 from 'd3'
import type { PerformanceData } from './mockData'

const props = defineProps<{
  performanceData: PerformanceData
}>()

const chartRef = ref<HTMLElement>()
const selectedMetric = ref<'auc' | 'f1'>('auc')
const tooltip = ref({
  show: false,
  data: {
    method: '',
    value: 0,
    rank: 0
  },
  style: {
    left: '0px',
    top: '0px'
  }
})

let svg: d3.Selection<SVGSVGElement, unknown, null, undefined> | null = null
let currentChart: any = null

const chartData = computed(() => {
  const data = props.performanceData.methods.map((method, index) => ({
    method,
    value: selectedMetric.value === 'auc'
      ? props.performanceData.auc[index]
      : props.performanceData.f1[index],
    isAdda: method === 'Adda'
  }))

  // 按值排序
  return data.sort((a, b) => b.value - a.value)
})

const bestMethod = computed(() => {
  const best = chartData.value[0]
  return best ? best.method : 'N/A'
})

const improvement = computed(() => {
  const addaData = chartData.value.find(d => d.isAdda)
  const baselineData = chartData.value.find(d => !d.isAdda)

  if (!addaData || !baselineData) return 0

  const baselineAvg = chartData.value
    .filter(d => !d.isAdda)
    .reduce((sum, d) => sum + d.value, 0) /
    chartData.value.filter(d => !d.isAdda).length

  return ((addaData.value - baselineAvg) / baselineAvg) * 100
})

const averageScore = computed(() => {
  const values = chartData.value.map(d => d.value)
  return values.reduce((sum, val) => sum + val, 0) / values.length
})

const setMetric = (metric: 'auc' | 'f1') => {
  selectedMetric.value = metric
  updateChart()
}

const createChart = () => {
  if (!chartRef.value) return

  const container = chartRef.value
  const width = container.clientWidth
  const height = 300

  // 确保有有效的数据
  const validData = chartData.value.filter(d =>
    d.method &&
    typeof d.value === 'number' &&
    d.value >= 0 &&
    d.value <= 1 // AUC和F1值应该在0-1之间
  )

  if (validData.length === 0) {
    // 显示无数据提示而不是报错
    showNoDataMessage(container)
    return
  }

  // 清除现有图表
  d3.select(container).selectAll('*').remove()

  svg = d3.select(container)
    .append('svg')
    .attr('width', width)
    .attr('height', height)

  const margin = { top: 20, right: 30, bottom: 60, left: 50 }
  const innerWidth = width - margin.left - margin.right
  const innerHeight = height - margin.top - margin.bottom

  const g = svg.append('g')
    .attr('transform', `translate(${margin.left},${margin.top})`)

  // 比例尺
  const xScale = d3.scaleBand()
    .domain(validData.map(d => d.method))
    .range([0, innerWidth])
    .padding(0.2)

  const yScale = d3.scaleLinear()
    .domain([0, d3.max(validData, d => d.value) || 1])
    .nice()
    .range([innerHeight, 0])

  // 颜色比例尺
  const colorScale = d3.scaleOrdinal()
    .domain(['Adda', 'Baseline'])
    .range(['#007bff', '#6c757d'])

  // X轴
  g.append('g')
    .attr('transform', `translate(0,${innerHeight})`)
    .call(d3.axisBottom(xScale))
    .selectAll('text')
    .style('text-anchor', 'end')
    .attr('dx', '-.8em')
    .attr('dy', '.15em')
    .attr('transform', 'rotate(-45)')

  // Y轴
  g.append('g')
    .call(d3.axisLeft(yScale)
      .tickFormat(d3.format('.2f'))
    )

  // Y轴标签
  g.append('text')
    .attr('transform', 'rotate(-90)')
    .attr('y', 0 - margin.left)
    .attr('x', 0 - (innerHeight / 2))
    .attr('dy', '1em')
    .style('text-anchor', 'middle')
    .style('font-size', '12px')
    .style('fill', '#6c757d')
    .text(selectedMetric.value.toUpperCase())

  // 柱状图
  const bars = g.selectAll('.bar')
    .data(validData)
    .enter().append('rect')
    .attr('class', 'bar')
    .attr('x', d => xScale(d.method) || 0)
    .attr('width', xScale.bandwidth())
    .attr('y', innerHeight)
    .attr('height', 0)
    .attr('fill', d => d.isAdda ? '#007bff' : '#6c757d')
    .attr('rx', 4)
    .style('cursor', 'pointer')

  // 动画
  bars.transition()
    .duration(800)
    .delay((d, i) => i * 100)
    .attr('y', d => yScale(d.value))
    .attr('height', d => innerHeight - yScale(d.value))

  // 鼠标事件
  bars
    .on('mouseover', function(event, d) {
      d3.select(this)
        .transition()
        .duration(200)
        .attr('opacity', 0.8)

      const rank = chartData.value.findIndex(item => item.method === d.method) + 1
      showTooltip(event, {
        method: d.method,
        value: d.value,
        rank: rank
      })
    })
    .on('mousemove', function(event) {
      updateTooltipPosition(event)
    })
    .on('mouseout', function() {
      d3.select(this)
        .transition()
        .duration(200)
        .attr('opacity', 1)

      hideTooltip()
    })

  // 数值标签
  g.selectAll('.label')
    .data(validData)
    .enter().append('text')
    .attr('class', 'label')
    .attr('x', d => (xScale(d.method) || 0) + xScale.bandwidth() / 2)
    .attr('y', d => yScale(d.value) - 5)
    .attr('text-anchor', 'middle')
    .style('font-size', '16px')
    .style('font-weight', 'bold')
    .style('fill', d => d.isAdda ? '#007bff' : '#6c757d')
    .style('opacity', 0)
    .text(d => d.value.toFixed(3))
    .transition()
    .duration(800)
    .delay((d, i) => i * 100 + 400)
    .style('opacity', 1)

  currentChart = { svg, g, xScale, yScale, bars }
}

const updateChart = () => {
  nextTick(() => {
    createChart()
  })
}

const showTooltip = (event: MouseEvent, data: any) => {
  const rank = validData.findIndex(item => item.method === data.method) + 1
  tooltip.value.show = true
  tooltip.value.data = {
    ...data,
    rank
  }
  updateTooltipPosition(event)
}

const updateTooltipPosition = (event: MouseEvent) => {
  const rect = (event.currentTarget as HTMLElement).getBoundingClientRect()
  tooltip.value.style = {
    left: `${event.clientX - rect.left + 10}px`,
    top: `${event.clientY - rect.top - 10}px`
  }
}

const hideTooltip = () => {
  tooltip.value.show = false
}

const showNoDataMessage = (container: HTMLElement) => {
  // 清除现有内容
  d3.select(container).selectAll('*').remove()

  const noDataDiv = d3.select(container)
    .append('div')
    .style('display', 'flex')
    .style('flex-direction', 'column')
    .style('align-items', 'center')
    .style('justify-content', 'center')
    .style('height', '300px')
    .style('color', '#6c757d')
    .style('font-size', '14px')

  noDataDiv.append('i')
    .attr('class', 'bi bi-bar-chart-line')
    .style('font-size', '48px')
    .style('margin-bottom', '16px')
    .style('opacity', '0.5')

  noDataDiv.append('div')
    .style('text-align', 'center')
    .html('No performance data available<br><small>Run the analysis to see performance metrics</small>')
}

const exportChart = () => {
  if (!svg) return

  const svgData = new XMLSerializer().serializeToString(svg.node()!)
  const canvas = document.createElement('canvas')
  const ctx = canvas.getContext('2d')!
  const img = new Image()

  img.onload = () => {
    canvas.width = img.width
    canvas.height = img.height
    ctx.drawImage(img, 0, 0)

    const link = document.createElement('a')
    link.download = `performance-comparison-${selectedMetric.value}-${Date.now()}.png`
    link.href = canvas.toDataURL()
    link.click()
  }

  img.src = 'data:image/svg+xml;base64,' + btoa(svgData)
}

// 响应式处理
const handleResize = () => {
  if (chartRef.value) {
    createChart()
  }
}

onMounted(() => {
  createChart()
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
})

watch(() => props.performanceData, () => {
  updateChart()
}, { deep: true })
</script>

<style scoped>
.performance-comparison-chart {
  background: var(--bg-white);
  border-radius: 12px;
  box-shadow: var(--shadow-sm);
  border: 1px solid var(--border-color);
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  border-bottom: 1px solid var(--border-color);
  background: var(--bg-light);
  flex-shrink: 0;
}

.panel-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 600;
  color: var(--text-primary);
  font-size: 18px;
}

.panel-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.metric-toggle {
  display: flex;
  background: var(--bg-primary);
  border-radius: 6px;
  padding: 2px;
  border: 1px solid var(--border-color);
}

.metric-btn {
  background: none;
  border: none;
  padding: 6px 12px;
  border-radius: 4px;
  font-size: 14px;
  font-weight: 500;
  color: var(--text-secondary);
  cursor: pointer;
  transition: all 0.2s ease;
}

.metric-btn.active {
  background: var(--primary-color);
  color: white;
}

.metric-btn:hover:not(.active) {
  color: var(--text-primary);
}

.btn-icon {
  background: none;
  border: none;
  padding: 6px;
  border-radius: 6px;
  cursor: pointer;
  color: var(--text-secondary);
  transition: all 0.2s ease;
  display: flex;
  align-items: center;
  justify-content: center;
}

.btn-icon:hover {
  background: var(--bg-primary);
  color: var(--primary-color);
}

.chart-container {
  flex: 1;
  padding: 16px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  min-height: 0;
}

.performance-chart {
  flex: 1;
  min-height: 0;
  overflow: hidden;
}

.chart-legend {
  display: flex;
  justify-content: center;
  gap: 20px;
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid var(--border-color);
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  color: var(--text-secondary);
}

.legend-color {
  width: 12px;
  height: 12px;
  border-radius: 2px;
}

.adda-color {
  background: #007bff;
}

.baseline-color {
  background: #6c757d;
}

.stats-summary {
  display: flex;
  justify-content: space-around;
  margin-top: 16px;
  padding: 12px;
  background: var(--bg-light);
  border-radius: 8px;
  border: 1px solid var(--border-color);
}

.stat-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
}

.stat-label {
  font-size: 14px;
  color: var(--text-secondary);
  text-transform: uppercase;
  font-weight: 500;
}

.stat-value {
  font-size: 20px;
  font-weight: 600;
  color: var(--text-primary);
}

.best-method {
  color: var(--primary-color);
}

.improvement {
  color: var(--success-color, #28a745);
}

.chart-tooltip {
  position: absolute;
  background: rgba(0, 0, 0, 0.9);
  color: white;
  padding: 8px 12px;
  border-radius: 6px;
  font-size: 14px;
  pointer-events: none;
  z-index: 1000;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
}

.tooltip-header {
  font-weight: 600;
  margin-bottom: 4px;
  padding-bottom: 4px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.2);
}

.tooltip-content {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.tooltip-row {
  display: flex;
  justify-content: space-between;
  gap: 12px;
}

.tooltip-row strong {
  color: #4dabf7;
}

/* 响应式设计 */
@media (max-width: 768px) {
  .panel-header {
    padding: 10px 12px;
  }

  .chart-container {
    padding: 12px;
  }

  .stats-summary {
    flex-direction: column;
    gap: 8px;
  }

  .stat-item {
    flex-direction: row;
    justify-content: space-between;
  }

  .metric-btn {
    padding: 4px 8px;
    font-size: 11px;
  }
}

/* D3图表样式 */
:deep(.bar) {
  transition: opacity 0.2s ease;
}

:deep(.bar:hover) {
  filter: brightness(1.1);
}

:deep(.domain) {
  stroke: #dee2e6;
}

:deep(.tick line) {
  stroke: #dee2e6;
}

:deep(.tick text) {
  fill: #6c757d;
  font-size: 16px;
}
</style>