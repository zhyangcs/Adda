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
          <strong>{{ (tooltip.data.value || 0).toFixed(3) }}</strong>
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
import type { PerformanceData } from '@/types'

const props = defineProps<{
  performanceData: PerformanceData | null
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
  if (!props.performanceData) return []

  const data = props.performanceData.methods.map((method, index) => ({
    method,
    value: selectedMetric.value === 'auc'
      ? (props.performanceData?.auc?.[index] || 0)
      : (props.performanceData?.f1?.[index] || 0),
    isAdda: method === 'Adda'
  }))

  // 按值排序
  return data.sort((a, b) => (b.value || 0) - (a.value || 0))
})

// 有效数据计算属性
const validData = computed(() => {
  return chartData.value.filter(d =>
    d.method &&
    typeof d.value === 'number' &&
    d.value >= 0 &&
    d.value <= 1 // AUC和F1值应该在0-1之间
  )
})

const bestMethod = computed(() => {
  if (chartData.value.length === 0) return 'N/A'
  const best = chartData.value[0]
  return best ? best.method : 'N/A'
})

const improvement = computed(() => {
  if (chartData.value.length === 0) return 0

  const addaData = chartData.value.find(d => d.isAdda)
  const baselineMethods = chartData.value.filter(d => !d.isAdda)

  if (!addaData || baselineMethods.length === 0) return 0

  const baselineAvg = baselineMethods
    .reduce((sum, d) => sum + (d.value || 0), 0) /
    baselineMethods.length

  return ((addaData.value || 0) - baselineAvg) / baselineAvg * 100
})

const averageScore = computed(() => {
  if (chartData.value.length === 0) return 0
  const values = chartData.value.map(d => d.value || 0)
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
  const height = (() => {
    const h = container.clientHeight && container.clientHeight > 0 ? container.clientHeight : 0
    return Math.max(h, 360)
  })()

  if (width === 0 || height === 0) {
    requestAnimationFrame(() => createChart())
    return
  }

  // 清除现有图表
  d3.select(container).selectAll('*').remove()

  svg = d3.select(container)
    .append('svg')
    .attr('width', width)
    .attr('height', height)

  // 为右上角图例预留顶部空间
  const margin = { top: 48, right: 40, bottom: 70, left: 70 }
  const innerWidth = width - margin.left - margin.right
  const innerHeight = height - margin.top - margin.bottom

  const g = svg.append('g')
    .attr('transform', `translate(${margin.left},${margin.top})`)

  if (validData.value.length === 0) {
    // 显示空图表
    showEmptyChart(g, innerWidth, innerHeight)
    return
  }

  // 比例尺
  const xScale = d3.scaleBand()
    .domain(validData.value.map((d: any) => d.method))
    .range([0, innerWidth])
    .padding(0.2)

  const yScale = d3.scaleLinear()
    .domain([0, d3.max(validData.value, (d: any) => d.value) || 1])
    .nice()
    .range([innerHeight, 0])

  
  // X轴
  g.append('g')
    .attr('transform', `translate(0,${innerHeight})`)
    .call(d3.axisBottom(xScale))
    .selectAll('text')
    .style('text-anchor', 'middle')
    .attr('dx', '0')
    .attr('dy', '0.75em')
    .attr('transform', 'rotate(0)')

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
    .style('font-size', '15px')
    .style('font-weight', '600')
    .style('fill', '#495057')
    .text(selectedMetric.value.toUpperCase())

  // 柱状图
  const bars = g.selectAll('.bar')
    .data(validData.value)
    .enter().append('rect')
    .attr('class', 'bar')
    .attr('x', (d: any) => xScale(d.method) || 0)
    .attr('width', xScale.bandwidth())
    .attr('y', innerHeight)
    .attr('height', 0)
    .attr('fill', (d: any) => d.isAdda ? '#007bff' : '#6c757d')
    .attr('rx', 4)
    .style('cursor', 'pointer')

  // 动画
  bars.transition()
    .duration(800)
    .delay((_: any, i: number) => i * 100)
    .attr('y', (d: any) => yScale(d.value))
    .attr('height', (d: any) => innerHeight - yScale(d.value))

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
    .data(validData.value)
    .enter().append('text')
    .attr('class', 'label')
    .attr('x', (d: any) => (xScale(d.method) || 0) + xScale.bandwidth() / 2)
    .attr('y', (d: any) => yScale(d.value) - 5)
    .attr('text-anchor', 'middle')
    .style('font-size', '16px')
    .style('font-weight', 'bold')
    .style('fill', (d: any) => d.isAdda ? '#007bff' : '#6c757d')
    .style('opacity', 0)
    .text((d: any) => d.value.toFixed(3))
    .transition()
    .duration(800)
    .delay((_: any, i: number) => i * 100 + 400)
    .style('opacity', 1)

  currentChart = { svg, g, xScale, yScale, bars }
}

const updateChart = () => {
  nextTick(() => {
    createChart()
  })
}

const showTooltip = (event: MouseEvent, data: any) => {
  const rank = validData.value.findIndex((item: any) => item.method === data.method) + 1
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

const showEmptyChart = (g: d3.Selection<SVGGElement, unknown, null, undefined>, width: number, height: number) => {
  // 绘制空的坐标轴
  const xScale = d3.scaleBand()
    .domain([])
    .range([0, width])
    .padding(0.2)

  const yScale = d3.scaleLinear()
    .domain([0, 1])
    .nice()
    .range([height, 0])

  // X轴
  g.append('g')
    .attr('transform', `translate(0,${height})`)
    .call(d3.axisBottom(xScale))

  // Y轴
  g.append('g')
    .call(d3.axisLeft(yScale))

  // Y轴标签
  g.append('text')
    .attr('transform', 'rotate(-90)')
    .attr('y', 0 - 50)
    .attr('x', 0 - (height / 2))
    .attr('dy', '1em')
    .style('text-anchor', 'middle')
    .style('font-size', '12px')
    .style('fill', '#6c757d')
    .text('Score')

  // X轴标签
  g.append('text')
    .attr('transform', `translate(${width / 2}, ${height + 50})`)
    .style('text-anchor', 'middle')
    .style('font-size', '12px')
    .style('fill', '#6c757d')
    .text('Methods')

  // 空状态提示
  g.append('text')
    .attr('x', width / 2)
    .attr('y', height / 2)
    .attr('text-anchor', 'middle')
    .style('font-size', '14px')
    .style('fill', '#6c757d')
    .style('opacity', 0.6)
    .text('No data available')
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
  background: #fff;
  border-radius: 12px;
  box-shadow: none;
  border: none;
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 14px;
  min-height: 54px;
  gap: 12px;
  border-bottom: 2px solid var(--accent-blue, #2a7de1);
  background: transparent;
  flex-shrink: 0;
}

.panel-title {
  display: flex;
  align-items: center;
  gap: 10px;
  font-weight: 700;
  color: var(--text-primary);
  font-size: 20px;
}

.panel-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}

.metric-toggle {
  display: flex;
  align-items: center;
  background: #f7f9fc;
  border-radius: 8px;
  padding: 4px 6px;
  border: 1px solid var(--border-color);
  min-height: 40px;
  box-shadow: none;
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
  background: var(--accent-blue, #2a7de1);
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
  background: rgba(42, 125, 225, 0.08);
  color: var(--accent-blue, #2a7de1);
}

.chart-container {
  position: relative;
  flex: 1;
  padding: 16px;
  display: flex;
  flex-direction: column;
  overflow: visible;
  min-height: 360px;
}

.performance-chart {
  flex: 1;
  min-height: 320px;
  overflow: hidden;
}

.chart-legend {
  position: absolute;
  top: 12px;
  right: 12px;
  display: flex;
  gap: 12px;
  align-items: center;
  padding: 8px 12px;
  border: 1px solid var(--border-color);
  border-radius: 8px;
  background: #fff;
  box-shadow: var(--shadow-sm, 0 2px 4px rgba(0,0,0,0.08));
  z-index: 5;
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

.chart-tooltip {
  position: absolute;
  background: rgba(0, 0, 0, 0.9);
  color: white;
  padding: 8px 12px;
  border-radius: 6px;
  font-size: 14px;
  pointer-events: none;
  z-index: 1000;
  box-shadow: none;
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
