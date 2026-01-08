<template>
  <div class="time-comparison-chart">
    <div class="panel-header">
      <div class="panel-title">
        <i class="bi bi-clock-history"></i>
        Time Comparison
      </div>
      <div class="panel-actions">
        <div class="unit-toggle">
          <button
            class="unit-btn"
            :class="{ active: timeUnit === 'seconds' }"
            @click="setTimeUnit('seconds')"
          >
            Seconds
          </button>
          <button
            class="unit-btn"
            :class="{ active: timeUnit === 'minutes' }"
            @click="setTimeUnit('minutes')"
          >
            Minutes
          </button>
        </div>
        <button
          class="btn-icon export-btn"
          @click="exportChart"
          title="Export HD chart"
        >
          <i class="bi bi-download"></i>
        </button>
      </div>
    </div>

    <div class="chart-container">
      <div ref="chartRef" class="time-chart"></div>
    </div>

    <div
      v-if="tooltip.show"
      class="chart-tooltip"
      :style="tooltip.style"
    >
      <div class="tooltip-header">{{ tooltip.data.method }}</div>
      <div class="tooltip-content">
        <div class="tooltip-row">
          <span>Total Time:</span>
          <strong>{{ formatTime(tooltip.data.totalTime) }}</strong>
        </div>
        <div class="tooltip-row">
          <span>Training:</span>
          <strong>{{ formatTime(tooltip.data.trainingTime) }}</strong>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, onActivated, watch, nextTick } from 'vue'
import * as d3 from 'd3'
import type { TimeData } from '@/types'

const props = defineProps<{
  timeData: TimeData | null
}>()

const chartRef = ref<HTMLElement>()
let resizeObserver: ResizeObserver | null = null
const timeUnit = ref<'seconds' | 'minutes'>('seconds')
const tooltip = ref({
  show: false,
  data: {
    method: '',
    totalTime: 0,
    trainingTime: 0
  },
  style: {
    left: '0px',
    top: '0px'
  }
})

let svg: d3.Selection<SVGSVGElement, unknown, null, undefined> | null = null
let currentChart: any = null

const chartData = computed(() => {
  const data = props.timeData
  if (!data) return []

  return data.methods.map((method, index) => {
    const trainingTime = data.trainingTime?.[index] || 0
    const featureGenTimeRaw = data.featureGenerationTime?.[index]
    const legacyTotal = data.totalTime?.[index] || 0
    const featureGenerationTime = typeof featureGenTimeRaw === 'number'
      ? featureGenTimeRaw
      : Math.max(0, legacyTotal - trainingTime)
    const endToEndLatency = Math.max(0, trainingTime + featureGenerationTime)

    return {
      method,
      totalTime: endToEndLatency,
      trainingTime,
      isAdda: method === 'Adda'
    }
  }).sort((a, b) => (a.totalTime || 0) - (b.totalTime || 0))
})

const formatTime = (seconds: number): string => {
  if (!seconds || isNaN(seconds) || seconds <= 0) {
    return '0 s'
  }

  if (timeUnit.value === 'minutes') {
    const minutes = seconds / 60
    return minutes >= 1
      ? `${minutes.toFixed(1)} min`
      : `${seconds.toFixed(1)} s`
  }
  return seconds >= 60
    ? `${(seconds / 60).toFixed(1)} min`
    : `${seconds.toFixed(1)} s`
}

const setTimeUnit = (unit: 'seconds' | 'minutes') => {
  timeUnit.value = unit
  updateChart()
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

  d3.select(container).selectAll('*').remove()

  svg = d3.select(container)
    .append('svg')
    .attr('width', width)
    .attr('height', height)
    .style('display', 'block')
    .style('margin', '0 auto')
    .style('background', '#fff')

  svg.append('rect')
    .attr('x', 1)
    .attr('y', 1)
    .attr('width', width - 2)
    .attr('height', height - 2)
    .attr('rx', 12)
    .attr('ry', 12)
    .attr('fill', 'none')
    .attr('stroke', '#dee2e6')
    .attr('stroke-width', 2)

  const margin = { top: 20, right: 20, bottom: 60, left: 90 }
  const innerWidth = width - margin.left - margin.right
  const innerHeight = height - margin.top - margin.bottom

  const g = svg.append('g')
    .attr('transform', `translate(${margin.left},${margin.top})`)

  const validData = chartData.value.filter(d =>
    d.method &&
    typeof d.totalTime === 'number' &&
    d.totalTime > 0 &&
    typeof d.trainingTime === 'number' &&
    d.trainingTime >= 0
  )

  if (validData.length === 0) {
    showEmptyChart(g, innerWidth, innerHeight)
    return
  }

  const timeScale = timeUnit.value === 'minutes' ? 60 : 1
  const maxTimeValue = Math.max(...validData.map(d => (d.totalTime || 0) / timeScale), 1) * 1.15

  const xScale = d3.scaleLinear()
    .domain([0, maxTimeValue])
    .nice()
    .range([0, innerWidth])

  const yScale = d3.scaleBand()
    .domain(validData.map(d => d.method))
    .range([0, innerHeight])
    .padding(0.22)

  const grid = g.append('g')
    .attr('class', 'x-grid')
    .attr('transform', `translate(0,${innerHeight})`)
    .call(
      d3.axisBottom(xScale)
        .ticks(6)
        .tickSize(-innerHeight)
        .tickFormat(() => '')
    )
  grid.selectAll('.domain').remove()
  grid.selectAll('line')
    .attr('stroke', '#dfe3eb')
    .attr('stroke-width', 1)
    .attr('shape-rendering', 'crispEdges')

  const yAxis = g.append('g')
    .call(d3.axisLeft(yScale).tickSize(0).tickPadding(10))

  yAxis.select('.domain').remove()
  yAxis.selectAll('text')
    .style('text-anchor', 'end')
    .style('font-size', '16px')
    .style('font-weight', '600')
    .style('fill', '#374151')

  const xAxis = g.append('g')
    .attr('transform', `translate(0,${innerHeight})`)
    .call(
      d3.axisBottom(xScale)
        .ticks(6)
        .tickPadding(8)
        .tickFormat(d => {
          const value = Number(d)
          if (timeUnit.value === 'minutes') {
            const minutes = value
            return minutes >= 1 ? `${minutes.toFixed(1)} min` : `${(minutes * 60).toFixed(0)} s`
          }
          return `${value.toFixed(0)} s`
        })
    )
  xAxis.select('.domain').remove()
  xAxis.selectAll('line').attr('stroke', '#cbd5e1')
  xAxis.selectAll('text')
    .style('font-size', '14px')
    .style('fill', '#1f2937')

  g.append('text')
    .attr('x', innerWidth / 2)
    .attr('y', innerHeight + margin.bottom - 10)
    .style('text-anchor', 'middle')
    .style('font-size', '20px')
    .style('font-weight', '700')
    .style('fill', '#1f2937')
    .text(`Latency (${timeUnit.value === 'minutes' ? 'minutes' : 'seconds'})`)

  const groupedData = validData.map(d => ({
    method: d.method,
    isAdda: d.isAdda,
    total: Math.max(0, d.totalTime / timeScale),
    training: Math.max(0, d.trainingTime / timeScale)
  }))

  const colorScale = d3.scaleOrdinal<string, string>()
    .domain(['training', 'endToEnd'])
    .range(['#9ca3af', '#f59e0b'])

  const subScale = d3.scaleBand()
    .domain(['training', 'endToEnd'])
    .range([0, yScale.bandwidth()])
    .padding(0.18)

  const groups = g.selectAll('.method-group')
    .data(groupedData)
    .enter()
    .append('g')
    .attr('class', 'method-group')
    .attr('transform', (d: any) => `translate(0,${yScale(d.method) || 0})`)

  const barRows = groups.selectAll('rect')
    .data((d: any) => ([
      { method: d.method, isAdda: d.isAdda, key: 'training', value: d.training },
      { method: d.method, isAdda: d.isAdda, key: 'endToEnd', value: d.total }
    ]))
    .enter()
    .append('rect')
    .attr('class', 'stacked-bar')
    .attr('x', 0)
    .attr('y', (d: any) => subScale(d.key) || 0)
    .attr('height', subScale.bandwidth())
    .attr('width', 0)
    .attr('fill', (d: any) => colorScale(d.key as string) || '#9ca3af')
    .attr('rx', 3)
    .style('cursor', 'pointer')

  barRows.transition()
    .duration(800)
    .delay((_d, i) => i * 30)
    .attr('width', (d: any) => xScale(d.value))

  groups.selectAll('.value-label')
    .data((d: any) => ([
      { method: d.method, key: 'training', value: d.training },
      { method: d.method, key: 'endToEnd', value: d.total }
    ]))
    .enter()
    .append('text')
    .attr('class', 'value-label')
    .attr('x', (d: any) => xScale(d.value) + 6)
    .attr('y', (d: any) => (subScale(d.key) || 0) + subScale.bandwidth() / 2)
    .attr('dy', '0.35em')
    .text((d: any) => {
      const val = d.value
      if (val <= 0) return ''
      if (timeUnit.value === 'minutes') {
        return `${val.toFixed(1)} min`
      }
      return `${val.toFixed(0)} s`
    })
    .style('font-size', '20px')
    .style('fill', '#000000')
    .style('opacity', 0)
    .transition()
    .duration(800)
    .delay((_d, i) => i * 30 + 300)
    .style('opacity', 1)

  groups
    .filter((d: any) => d.isAdda)
    .append('rect')
    .attr('x', -2)
    .attr('y', -2)
    .attr('height', yScale.bandwidth() + 4)
    .attr('width', (d: any) => xScale(d.total) + 4)
    .attr('fill', 'none')
    .attr('stroke', '#007bff')
    .attr('stroke-width', 2)
    .attr('stroke-dasharray', '5,3')
    .attr('rx', 6)
    .style('opacity', 0)
    .transition()
    .duration(800)
    .delay(800)
    .style('opacity', 1)

  groups
    .on('mouseover', function(event, d: any) {
      d3.select(this).selectAll('.stacked-bar')
        .transition()
        .duration(200)
        .attr('opacity', 0.85)

      const originalData = chartData.value.find(item => item.method === d.method)
      if (originalData) {
        showTooltip(event, {
          method: originalData.method,
          totalTime: originalData.totalTime,
          trainingTime: originalData.trainingTime
        })
      }
    })
    .on('mousemove', function(event) {
      updateTooltipPosition(event)
    })
    .on('mouseout', function() {
      d3.select(this).selectAll('.stacked-bar')
        .transition()
        .duration(200)
        .attr('opacity', 1)
      hideTooltip()
    })

  const legendGroup = svg.append('g')
    .attr('class', 'chart-legend-d3')
    .attr('transform', `translate(${width - margin.right - 240}, ${margin.top + 10})`)

  legendGroup.append('rect')
    .attr('width', 230)
    .attr('height', 74)
    .attr('fill', 'rgba(255, 255, 255, 0.95)')
    .attr('stroke', '#cbd5e1')
    .attr('stroke-width', 1)
    .attr('rx', 8)
    .style('filter', 'drop-shadow(0 2px 4px rgba(0,0,0,0.05))')

  const legendItem1 = legendGroup.append('g').attr('transform', 'translate(16, 18)')
  legendItem1.append('rect')
    .attr('width', 18)
    .attr('height', 14)
    .attr('fill', '#9ca3af')
    .attr('rx', 2)
  legendItem1.append('text')
    .attr('x', 26)
    .attr('y', 12)
    .style('font-size', '18px')
    .style('font-weight', '600')
    .style('fill', '#374151')
    .text('Training Time')

  const legendItem2 = legendGroup.append('g').attr('transform', 'translate(16, 50)')
  legendItem2.append('rect')
    .attr('width', 18)
    .attr('height', 14)
    .attr('fill', '#f59e0b')
    .attr('rx', 2)
  legendItem2.append('text')
    .attr('x', 26)
    .attr('y', 12)
    .style('font-size', '18px')
    .style('font-weight', '600')
    .style('fill', '#374151')
    .text('End-to-End Latency')

  currentChart = { svg, g, xScale, yScale, bars: barRows }
}

const updateChart = () => {
  nextTick(() => {
    createChart()
  })
}

const showTooltip = (event: MouseEvent, data: any) => {
  tooltip.value.show = true
  tooltip.value.data = data
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
    .text('Time')

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
    link.download = `time-comparison-${timeUnit.value}-${Date.now()}.png`
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

onActivated(() => {
  nextTick(() => {
    createChart()
  })
})

onMounted(() => {
  createChart()
  window.addEventListener('resize', handleResize)

  if (chartRef.value && 'ResizeObserver' in window) {
    resizeObserver = new ResizeObserver(() => {
      createChart()
    })
    resizeObserver.observe(chartRef.value)
  }
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)

  if (resizeObserver) {
    resizeObserver.disconnect()
    resizeObserver = null
  }
})

watch(() => props.timeData, () => {
  updateChart()
}, { deep: true })
</script>

<style scoped>
.time-comparison-chart {
  background: #fff;
  border-radius: 12px;
  box-shadow: none;
  border: none;
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
  position: relative;
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
  font-size: 27px;
}

.panel-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}

.unit-toggle {
  display: flex;
  align-items: center;
  background: #f7f9fc;
  border-radius: 8px;
  padding: 4px 6px;
  border: 1px solid var(--border-color);
  min-height: 40px;
  box-shadow: none;
}

.unit-btn {
  background: none;
  border: none;
  padding: 6px 12px;
  border-radius: 4px;
  font-size: 21px;
  font-weight: 500;
  color: var(--text-secondary);
  cursor: pointer;
  transition: all 0.2s ease;
}

.unit-btn.active {
  background: var(--accent-blue, #2a7de1);
  color: white;
}

.unit-btn:hover:not(.active) {
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

.export-btn {
  margin-left: 8px;
  background-color: #f1f5f9;
  color: #2a7de1;
  border: 1px solid #e2e8f0;
}

.export-btn:hover {
  background-color: #e2e8f0;
  color: #1a60c0;
}

.chart-container {
  position: relative;
  flex: 1;
  padding: 0;
  display: flex;
  flex-direction: column;
  overflow: visible;
  min-height: 0;
}

.time-chart {
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
  font-size: 21px;
  pointer-events: none;
  z-index: 1000;
  box-shadow: none;
  min-width: 160px;
}

.tooltip-header {
  font-weight: 600;
  margin-bottom: 6px;
  padding-bottom: 4px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.2);
}

.tooltip-content {
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.tooltip-row {
  display: flex;
  justify-content: space-between;
  gap: 8px;
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

  .unit-btn {
    padding: 4px 8px;
    font-size: 11px;
  }
}

::deep(.stacked-bar) {
  transition: opacity 0.2s ease;
}

::deep(.stacked-bar:hover) {
  filter: brightness(1.1);
}

::deep(.domain) {
  stroke: #cbd5e1;
  stroke-width: 1;
}

::deep(.tick line) {
  stroke: #cbd5e1;
  stroke-width: 1;
}

::deep(.tick text) {
  fill: #1f2937;
  font-size: 18px;
  font-weight: 500;
}

::deep(.method-group text) {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
}
</style>

