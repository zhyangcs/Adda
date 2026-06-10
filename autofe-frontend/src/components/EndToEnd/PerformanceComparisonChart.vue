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
      </div>
    </div>

    <div class="chart-container">
      <div ref="chartRef" class="performance-chart"></div>
    </div>

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
    d.value <= 1
  )
})

const setMetric = (metric: 'auc' | 'f1') => {
  selectedMetric.value = metric
  updateChart()
}

const drawChart = (container: HTMLElement, width: number, height: number, animate: boolean = true) => {
  d3.select(container).selectAll('*').remove()

  const newSvg = d3.select(container)
    .append('svg')
    .attr('width', width)
    .attr('height', height)
    // Add white background for export
    .style('background-color', '#ffffff')

  // Tighter margins so the chart fills the panel better on /performance.
  const margin = { top: 28, right: 28, bottom: 44, left: 84 }
  const innerWidth = width - margin.left - margin.right
  const innerHeight = height - margin.top - margin.bottom

  const g = newSvg.append('g')
    .attr('transform', `translate(${margin.left},${margin.top})`)

  if (validData.value.length === 0) {
    showEmptyChart(g, innerWidth, innerHeight)
    return { svg: newSvg, g }
  }

  // 比例尺
  const xScale = d3.scaleBand()
    .domain(validData.value.map((d: any) => d.method))
    .range([0, innerWidth])
    .padding(0.47)

  const yScale = d3.scaleLinear()
    .domain([0, d3.max(validData.value, (d: any) => d.value) || 1])
    .nice()
    .range([innerHeight, 0])

  // Add horizontal grid lines
  const grid = g.append('g')
    .attr('class', 'y-grid')
    .call(d3.axisLeft(yScale).ticks(6).tickSize(-innerWidth).tickFormat(() => ''))
  grid.selectAll('.domain').remove()
  grid.selectAll('line')
    .attr('stroke', '#dfe3eb')
    .attr('stroke-width', 1)
    .attr('shape-rendering', 'crispEdges')

  // X-axis (bottom) - only show tick labels, no tick lines
  const xAxis = g.append('g')
    .attr('transform', `translate(0,${innerHeight})`)
    .call(d3.axisBottom(xScale).tickSize(0).tickPadding(10))
  xAxis.select('.domain').remove()
  xAxis.selectAll('text')
    .style('font-size', '14px')
    .style('font-weight', '600')
    .style('fill', '#374151')
    .style('text-anchor', 'middle')
    .attr('dx', '0')
    .attr('dy', '0.75em')
    .attr('transform', 'rotate(0)')

  // Y-axis (left) - only show tick labels, no tick lines
  const yAxis = g.append('g')
    .call(d3.axisLeft(yScale).tickFormat(d3.format('.2f')).tickSize(0).tickPadding(8))
  yAxis.select('.domain').remove()
  yAxis.selectAll('text')
    .style('font-size', '14px')
    .style('fill', '#1f2937')

  // Y轴标签
  g.append('text')
    .attr('transform', 'rotate(-90)')
    .attr('y', 0 - margin.left + 20) // Moves text closer to center of margin
    .attr('x', 0 - (innerHeight / 2))
    .attr('dy', '1em')
    .style('text-anchor', 'middle')
    .style('font-size', '20px')
    .style('font-weight', '700')
    .style('fill', '#1f2937')
    .text(`Performance (${selectedMetric.value.toUpperCase()})`)

  // 柱状图
  const bars = g.selectAll('.bar')
    .data(validData.value)
    .enter().append('rect')
    .attr('class', 'bar')
    .attr('x', (d: any) => xScale(d.method) || 0)
    .attr('width', xScale.bandwidth())
    .attr('y', animate ? innerHeight : (d: any) => yScale(d.value))
    .attr('height', animate ? 0 : (d: any) => innerHeight - yScale(d.value))
    .attr('fill', (d: any, i: number) => {
      // Darker Academic/Scientific color palette
      const colors = ['#2c4b74', '#a8560d', '#96282b', '#316a66', '#2d5e2e', '#947814', '#63405c', '#a3525b', '#5c4031', '#6e6662']
      return colors[i % colors.length]
    })
    .attr('rx', 4)
    .style('cursor', 'pointer')

  if (animate) {
    bars.transition()
      .duration(800)
      .delay((_: any, i: number) => i * 100)
      .attr('y', (d: any) => yScale(d.value))
      .attr('height', (d: any) => innerHeight - yScale(d.value))
  }

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
  const labels = g.selectAll('.label')
    .data(validData.value)
    .enter().append('text')
    .attr('class', 'label')
    .attr('x', (d: any) => (xScale(d.method) || 0) + xScale.bandwidth() / 2)
    .attr('y', (d: any) => yScale(d.value) - 5)
    .attr('text-anchor', 'middle')
    .style('font-size', '16px')
    .style('font-weight', 'bold')
    .style('fill', (d: any, i: number) => {
      // Darker Academic/Scientific color palette
      const colors = ['#2c4b74', '#a8560d', '#96282b', '#316a66', '#2d5e2e', '#947814', '#63405c', '#a3525b', '#5c4031', '#6e6662']
      return colors[i % colors.length]
    })
    .style('opacity', animate ? 0 : 1)
    .text((d: any) => d.value.toFixed(3))
  
  if (animate) {
    labels.transition()
      .duration(800)
      .delay((_: any, i: number) => i * 100 + 400)
      .style('opacity', 1)
  }

  return { svg: newSvg, g, xScale, yScale, bars }
}

const createChart = () => {
  if (!chartRef.value) return

  const container = chartRef.value
  // Fill available space (avoid forcing an aspect ratio / minimum height,
  // which can cause clipping inside the /performance grid layout).
  const rect = container.getBoundingClientRect()
  const width = rect.width || container.clientWidth
  const height = rect.height || container.clientHeight

  if (width === 0 || height === 0) {
    requestAnimationFrame(() => createChart())
    return
  }

  const result = drawChart(container, width, height, true)
  svg = result.svg
  
  // 让图表居中
  if (svg) {
    svg.style('display', 'block')
       .style('margin', '0 auto')
  }

  currentChart = result
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

.chart-container {
  position: relative;
  flex: 1;
  padding: 14px;
  display: flex;
  flex-direction: column;
  overflow: visible;
  min-height: 0;
}

.performance-chart {
  flex: 1;
  min-height: 0;
  width: 100%;
  height: 100%;
  overflow: hidden;
}

.chart-legend {
  position: absolute;
  top: 12px;
  right: 12px;
  display: flex;
  gap: 14px;
  align-items: center;
  padding: 10px 14px;
  border: 1px solid #cbd5e1;
  border-radius: 10px;
  background: #fff;
  box-shadow: var(--shadow-md, 0 4px 8px rgba(0,0,0,0.08));
  z-index: 5;
  color: #1f2937;
  font-size: 15px;
  font-weight: 600;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 10px;
}

.legend-color {
  width: 14px;
  height: 14px;
  border-radius: 3px;
  box-shadow: inset 0 0 0 1px rgba(0,0,0,0.05);
}

.adda-color {
  background: #007bff;
}

.baseline-color {
  background: #4b5563;
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

/* D3 chart styles */
:deep(.bar) {
  transition: opacity 0.2s ease;
}

:deep(.bar:hover) {
  filter: brightness(1.1);
}

:deep(.domain) {
  display: none;
}

:deep(.tick text) {
  fill: #1f2937;
  font-size: 18px;
  font-weight: 500;
}
</style>
