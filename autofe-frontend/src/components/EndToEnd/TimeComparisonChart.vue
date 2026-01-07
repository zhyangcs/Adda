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
          class="btn-icon"
          @click="exportChart"
          title="Export chart"
        >
          <i class="bi bi-download"></i>
        </button>
      </div>
    </div>

    <div class="chart-container">
      <div ref="chartRef" class="time-chart"></div>

      <!-- 图表说明 -->
      <div class="chart-legend">
        <div class="legend-item">
          <div class="legend-segment training-segment"></div>
          <span>Training Time</span>
        </div>
        <div class="legend-item">
          <div class="legend-segment other-segment"></div>
          <span>Feature Generation</span>
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
          <span>Total Time:</span>
          <strong>{{ formatTime(tooltip.data.totalTime) }}</strong>
        </div>
        <div class="tooltip-row">
          <span>Training:</span>
          <strong>{{ formatTime(tooltip.data.trainingTime) }}</strong>
        </div>
        <div class="tooltip-row">
          <span>Feature Generation:</span>
          <strong>{{ formatTime(tooltip.data.otherTime) }}</strong>
        </div>
        <div class="tooltip-row">
          <span>Training Ratio:</span>
          <strong>{{ tooltip.data.trainingRatio }}%</strong>
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
    trainingTime: 0,
    otherTime: 0,
    trainingRatio: 0
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
    const totalTime = data.totalTime?.[index] || 0
    const trainingTime = data.trainingTime?.[index] || 0
    const otherTime = totalTime - trainingTime
    const trainingRatio = totalTime > 0 ? Math.round((trainingTime / totalTime) * 100) : 0

    return {
      method,
      totalTime,
      trainingTime,
      otherTime,
      trainingRatio,
      isAdda: method === 'Adda'
    }
  }).sort((a, b) => (a.totalTime || 0) - (b.totalTime || 0)) // 按总时间升序排序
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
  // 动态使用可用空间高度，避免固定 320px 导致在 100% 缩放时图表被裁切
  const width = container.clientWidth
  const height = (() => {
    const rectHeight = container.getBoundingClientRect().height
    const h = rectHeight && rectHeight > 0 ? rectHeight : container.clientHeight
    return Math.max(h || 0, 320) // 保留较高最小值，但为下方图例腾出空间
  })()

  // 如果容器当前不可见或尺寸为0，延迟到下一帧再尝试，避免缓存/切换后刻度错位
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

  // 调整边距：给顶部留出空间放图例，避免与柱体重叠
  const margin = { top: 56, right: 36, bottom: 44, left: 160 }
  const innerWidth = width - margin.left - margin.right
  const innerHeight = height - margin.top - margin.bottom

  const g = svg.append('g')
    .attr('transform', `translate(${margin.left},${margin.top})`)

  // 确保有有效的数据
  const validData = chartData.value.filter(d =>
    d.method &&
    typeof d.totalTime === 'number' &&
    d.totalTime > 0 &&
    typeof d.trainingTime === 'number' &&
    d.trainingTime >= 0
  )

  if (validData.length === 0) {
    // 显示空图表
    showEmptyChart(g, innerWidth, innerHeight)
    return
  }

  // 转换时间单位
  const timeScale = timeUnit.value === 'minutes' ? 60 : 1

  // 安全的数值计算
  const maxTimeValue = Math.max(...validData.map(d => (d.totalTime || 0) / timeScale), 1)

  // 比例尺（横向柱状图）
  const xScale = d3.scaleLinear()
    .domain([0, maxTimeValue])
    .nice()
    .range([0, innerWidth])

  const yScale = d3.scaleBand()
    .domain(validData.map(d => d.method))
    .range([0, innerHeight])
    .padding(0.22)

  // 竖向网格线（若干条竖线表示标度）
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

  // Y轴（方法名）
  g.append('g')
    .call(d3.axisLeft(yScale).tickSize(0).tickPadding(10))
    .selectAll('text')
    .style('text-anchor', 'end')

  // X轴（时间刻度）
  g.append('g')
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

  // X轴标签
  g.append('text')
    .attr('x', innerWidth / 2)
    .attr('y', innerHeight + margin.bottom - 8)
    .style('text-anchor', 'middle')
    .style('font-size', '16px')
    .style('font-weight', '700')
    .style('fill', '#1f2937')
    .text(`Time (${timeUnit.value === 'minutes' ? 'minutes' : 'seconds'})`)

  // 分组柱数据（不堆叠）：Training + Feature Generation 分开显示
  const groupedData = validData.map(d => ({
    method: d.method,
    isAdda: d.isAdda,
    total: Math.max(0, d.totalTime / timeScale),
    training: Math.max(0, d.trainingTime / timeScale),
    other: Math.max(0, d.otherTime / timeScale)
  }))

  // 颜色：Feature Generation=橙色，Training=灰色
  const colorScale = d3.scaleOrdinal<string, string>()
    .domain(['training', 'other'])
    .range(['#9ca3af', '#f59e0b'])

  const subScale = d3.scaleBand()
    .domain(['training', 'other'])
    .range([0, yScale.bandwidth()])
    .padding(0.18)

  // 每个方法一个分组
  const groups = g.selectAll('.method-group')
    .data(groupedData)
    .enter()
    .append('g')
    .attr('class', 'method-group')
    .attr('transform', (d: any) => `translate(0,${yScale(d.method) || 0})`)

  const barRows = groups.selectAll('rect')
    .data((d: any) => ([
      { method: d.method, isAdda: d.isAdda, key: 'training', value: d.training },
      { method: d.method, isAdda: d.isAdda, key: 'other', value: d.other }
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

  // Adda 高亮边框（围绕总时间标尺宽度）
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

  // 鼠标事件
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
          trainingTime: originalData.trainingTime,
          otherTime: originalData.otherTime,
          trainingRatio: originalData.trainingRatio
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
    .text('Time')

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

const showNoDataMessage = (container: HTMLElement) => {
  // 清除现有内容
  d3.select(container).selectAll('*').remove()

  const noDataDiv = d3.select(container)
    .append('div')
    .style('display', 'flex')
    .style('flex-direction', 'column')
    .style('align-items', 'center')
    .style('justify-content', 'center')
    .style('height', '320px')
    .style('color', '#6c757d')
    .style('font-size', '14px')

  noDataDiv.append('i')
    .attr('class', 'bi bi-clock-history')
    .style('font-size', '48px')
    .style('margin-bottom', '16px')
    .style('opacity', '0.5')

  noDataDiv.append('div')
    .style('text-align', 'center')
    .html('No time data available<br><small>Run the analysis to see time comparisons</small>')
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
    link.download = `time-comparison-${timeUnit.value}-${Date.now()}.png`
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

// keep-alive/tab 返回时确保重绘
onActivated(() => {
  nextTick(() => {
    createChart()
  })
})

onMounted(() => {
  createChart()
  window.addEventListener('resize', handleResize)

  // 监听容器尺寸变化，避免隐藏/显示后尺寸为0导致的刻度问题
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
  font-size: 18px;
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
  font-size: 14px;
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

.chart-container {
  position: relative;
  flex: 1;
  padding: 14px;
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
  font-size: 13px;
  font-weight: 600;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 10px;
}

.legend-segment {
  width: 16px;
  height: 12px;
  border-radius: 3px;
  border: 1px solid #cbd5e1;
  box-shadow: inset 0 0 0 1px rgba(0,0,0,0.05);
}

.training-segment {
  background: #9ca3af;
}

.other-segment {
  background: #f59e0b;
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

  .unit-btn {
    padding: 4px 8px;
    font-size: 11px;
  }

  .legend-item {
    font-size: 11px;
  }
}

/* D3图表样式 */
:deep(.stacked-bar) {
  transition: opacity 0.2s ease;
}

:deep(.stacked-bar:hover) {
  filter: brightness(1.1);
}

:deep(.domain) {
  stroke: #cbd5e1;
  stroke-width: 1;
}

:deep(.tick line) {
  stroke: #cbd5e1;
  stroke-width: 1;
}

:deep(.tick text) {
  fill: #1f2937;
  font-size: 12px;
  font-weight: 500;
}

:deep(.method-group text) {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
}
</style>
