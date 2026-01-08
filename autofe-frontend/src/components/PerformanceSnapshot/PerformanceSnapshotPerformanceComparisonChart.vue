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
          class="export-btn"
          @click="exportChart"
          title="Export HD chart"
        >
          <i class="bi bi-download"></i>
          Export HD
        </button>
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

  return data.sort((a, b) => (b.value || 0) - (a.value || 0))
})

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
    .style('background-color', '#ffffff')

  const margin = { top: 60, right: 36, bottom: 40, left: 90 }
  const innerWidth = width - margin.left - margin.right
  const innerHeight = height - margin.top - margin.bottom

  const g = newSvg.append('g')
    .attr('transform', `translate(${margin.left},${margin.top})`)

  if (validData.value.length === 0) {
    showEmptyChart(g, innerWidth, innerHeight)
    return { svg: newSvg, g }
  }

  const xScale = d3.scaleBand()
    .domain(validData.value.map((d: any) => d.method))
    .range([0, innerWidth])
    .padding(0.47)

  const yScale = d3.scaleLinear()
    .domain([0, d3.max(validData.value, (d: any) => d.value) || 1])
    .nice()
    .range([innerHeight, 0])

  g.append('g')
    .attr('transform', `translate(0,${innerHeight})`)
    .call(d3.axisBottom(xScale))
    .selectAll('text')
    .style('font-size', '16px')
    .style('text-anchor', 'middle')
    .attr('dx', '0')
    .attr('dy', '0.75em')
    .attr('transform', 'rotate(0)')

  g.append('g')
    .call(d3.axisLeft(yScale).tickFormat(d3.format('.2f')))
    .selectAll('text')
    .style('font-size', '16px')

  g.append('text')
    .attr('transform', 'rotate(-90)')
    .attr('y', 0 - margin.left + 20)
    .attr('x', 0 - (innerHeight / 2))
    .attr('dy', '1em')
    .style('text-anchor', 'middle')
    .style('font-size', '16px')
    .style('font-weight', '700')
    .style('fill', '#1f2937')
    .text(`Performance (${selectedMetric.value.toUpperCase()})`)

  const bars = g.selectAll('.bar')
    .data(validData.value)
    .enter().append('rect')
    .attr('class', 'bar')
    .attr('x', (d: any) => xScale(d.method) || 0)
    .attr('width', xScale.bandwidth())
    .attr('y', animate ? innerHeight : (d: any) => yScale(d.value))
    .attr('height', animate ? 0 : (d: any) => innerHeight - yScale(d.value))
    .attr('fill', (_d: any, i: number) => {
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

  const labels = g.selectAll('.label')
    .data(validData.value)
    .enter().append('text')
    .attr('class', 'label')
    .attr('x', (d: any) => (xScale(d.method) || 0) + xScale.bandwidth() / 2)
    .attr('y', (d: any) => yScale(d.value) - 5)
    .attr('text-anchor', 'middle')
    .style('font-size', '16px')
    .style('font-weight', 'bold')
    .style('fill', (_d: any, i: number) => {
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
  const rect = container.getBoundingClientRect()
  const availableHeight = rect.height && rect.height > 0 ? rect.height : (container.clientHeight || 360)
  const height = Math.max(availableHeight, 360)

  const targetWidth = height * 1.5
  const width = Math.min(container.clientWidth, targetWidth)

  if (width === 0 || height === 0) {
    requestAnimationFrame(() => createChart())
    return
  }

  const result = drawChart(container, width, height, true)
  svg = result.svg

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
  const xScale = d3.scaleBand()
    .domain([])
    .range([0, width])
    .padding(0.2)

  const yScale = d3.scaleLinear()
    .domain([0, 1])
    .nice()
    .range([height, 0])

  g.append('g')
    .attr('transform', `translate(0,${height})`)
    .call(d3.axisBottom(xScale))

  g.append('g')
    .call(d3.axisLeft(yScale))

  g.append('text')
    .attr('transform', 'rotate(-90)')
    .attr('y', 0 - 50)
    .attr('x', 0 - (height / 2))
    .attr('dy', '1em')
    .style('text-anchor', 'middle')
    .style('font-size', '12px')
    .style('fill', '#6c757d')
    .text('Score')

  g.append('text')
    .attr('transform', `translate(${width / 2}, ${height + 50})`)
    .style('text-anchor', 'middle')
    .style('font-size', '12px')
    .style('fill', '#6c757d')
    .text('Methods')

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

  const svgNode = svg.node()!
  const svgData = new XMLSerializer().serializeToString(svgNode)
  const canvas = document.createElement('canvas')
  const ctx = canvas.getContext('2d')!
  const img = new Image()

  const width = +svg.attr('width')
  const height = +svg.attr('height')

  const scale = 3

  img.onload = () => {
    canvas.width = width * scale
    canvas.height = height * scale

    ctx.scale(scale, scale)

    ctx.fillStyle = '#ffffff'
    ctx.fillRect(0, 0, width, height)

    ctx.drawImage(img, 0, 0)

    const link = document.createElement('a')
    link.download = `performance-comparison-${selectedMetric.value}-${Date.now()}.png`
    link.href = canvas.toDataURL('image/png')
    link.click()
  }

  img.src = 'data:image/svg+xml;base64,' + btoa(unescape(encodeURIComponent(svgData)))
}

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

.export-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  background: #fff;
  border: 1px solid #e2e8f0;
  padding: 6px 12px;
  border-radius: 6px;
  font-size: 13px;
  font-weight: 500;
  color: #64748b;
  cursor: pointer;
  transition: all 0.2s ease;
  margin-left: 8px;
}

.export-btn:hover {
  background: #f8fafc;
  color: #2a7de1;
  border-color: #2a7de1;
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

@media (max-width: 768px) {
  .panel-header {
    padding: 10px 12px;
  }

  .chart-container {
    padding: 12px;
  }

  .metric-btn {
    padding: 4px 8px;
    font-size: 11px;
  }
}

::deep(.bar) {
  transition: opacity 0.2s ease;
}

::deep(.bar:hover) {
  filter: brightness(1.1);
}

::deep(.domain) {
  stroke: #cbd5e1;
  stroke-width: 1.2;
}

::deep(.tick line) {
  stroke: #cbd5e1;
  stroke-width: 1.2;
}

::deep(.tick text) {
  fill: #1f2937;
  font-size: 15px;
  font-weight: 600;
}
</style>

