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
    const h = container.clientHeight && container.clientHeight > 0 ? container.clientHeight : 0
    return Math.max(h, 360) // 保留较高最小值，但为下方图例腾出空间
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
  const margin = { top: 48, right: 30, bottom: 80, left: 100 }
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
  const maxTimeValue = Math.max(...chartData.value.map(d => d.totalTime / timeScale), 1)

  // 比例尺
  const xScale = d3.scaleBand()
    .domain(chartData.value.map(d => d.method))
    .range([0, innerWidth])
    .padding(0.2)

  const yScale = d3.scaleLinear()
    .domain([0, maxTimeValue])
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
    .call(
      d3.axisLeft(yScale)
        .ticks(6)
        .tickPadding(6)
        .tickFormat(d => {
          const value = Number(d)
          if (timeUnit.value === 'minutes') {
            const minutes = value
            return minutes >= 1 ? `${minutes.toFixed(1)} min` : `${(minutes * 60).toFixed(0)} s`
          }
          // Seconds 模式下始终显示秒，不再转为分钟
          return `${value.toFixed(0)} s`
        })
    )

  // Y轴标签
  g.append('text')
    .attr('transform', 'rotate(-90)')
    .attr('y', -margin.left + 18)
    .attr('x', -innerHeight / 2)
    .attr('dy', '0')
    .style('text-anchor', 'middle')
    .style('dominant-baseline', 'middle')
    .style('font-size', '15px')
    .style('font-weight', '600')
    .style('fill', '#374151')
    .text(`Time (${timeUnit.value === 'minutes' ? 'minutes' : 'seconds'})`)

  // 堆叠柱状图数据
  const stackedData = validData.map(d => ({
    method: d.method,
    isAdda: d.isAdda,
    training: d.trainingTime / timeScale,
    other: d.otherTime / timeScale
  }))

  // 堆叠生成器
  const stack = d3.stack<any>()
    .keys(['training', 'other'])

  const series = stack(stackedData as unknown as Array<{ training: number; other: number }>)

  // 颜色比例尺
  const colorScale = d3.scaleOrdinal<string, string>()
    .domain(['training', 'other'])
    .range(['#1d4ed8', '#f59e0b']) // training: blue, feature generation: yellow

  // 绘制堆叠柱状图
  const groups = g.selectAll('.method-group')
    .data(stackedData)
    .enter().append('g')
    .attr('class', 'method-group')

  // 绘制每个柱子的分段
  const bars = groups.selectAll('rect')
    .data((d: any, groupIndex: number) => series.map(s => {
      const seriesData = s[groupIndex]
      return {
        method: d.method,
        isAdda: d.isAdda,
        key: s.key,
        value: d[s.key] || 0,
        start: seriesData?.[0] || 0,
        end: seriesData?.[1] || 0
      }
    }))
    .enter().append('rect')
    .attr('class', 'stacked-bar')
    .attr('x', (d: any) => xScale(d.method) || 0)
    .attr('width', xScale.bandwidth())
    .attr('y', (d: any) => {
      const endValue = isNaN(d.end) || d.end < 0 ? 0 : d.end
      return yScale(endValue)
    })
    .attr('height', (d: any) => {
      const startValue = isNaN(d.start) || d.start < 0 ? 0 : d.start
      const endValue = isNaN(d.end) || d.end < 0 ? 0 : d.end
      return yScale(startValue) - yScale(endValue)
    })
    .attr('fill', (d: any) => colorScale(d.key as string) || '#1d4ed8')
    .attr('rx', 2)
    .style('cursor', 'pointer')
    .attr('opacity', 0)

  // 动画
  bars.transition()
    .duration(800)
    .delay((d, i) => i * 50)
    .attr('opacity', 1)

  // 添加边框（为Adda方法）
  groups
    .filter((d: any) => d.isAdda)
    .append('rect')
    .attr('x', (d: any) => (xScale(d.method) || 0) - 2)
    .attr('width', xScale.bandwidth() + 4)
    .attr('y', (d: any) => {
      const value = d.totalTime / timeScale
      return isNaN(value) || value < 0 ? innerHeight : yScale(value)
    })
    .attr('height', (d: any) => {
      const value = d.totalTime / timeScale
      const yPos = isNaN(value) || value < 0 ? innerHeight : yScale(value)
      return innerHeight - yPos
    })
    .attr('fill', 'none')
    .attr('stroke', '#007bff')
    .attr('stroke-width', 2)
    .attr('stroke-dasharray', '5,3')
    .attr('rx', 4)
    .style('opacity', 0)
    .transition()
    .duration(800)
    .delay(1000)
    .style('opacity', 1)

  // 鼠标事件
  groups
    .on('mouseover', function(event, d) {
      d3.select(this).selectAll('.stacked-bar')
        .transition()
        .duration(200)
        .attr('opacity', 0.8)

      // 从原始数据中获取完整信息
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

  currentChart = { svg, g, xScale, yScale, bars }
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
  padding: 16px;
  display: flex;
  flex-direction: column;
  overflow: visible;
  min-height: 360px;
}

.time-chart {
  flex: 1;
  min-height: 300px;
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

.legend-segment {
  width: 16px;
  height: 12px;
  border-radius: 2px;
  border: 1px solid var(--border-color);
}

.training-segment {
  background: #1d4ed8;
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
  stroke: #dee2e6;
}

:deep(.tick line) {
  stroke: #dee2e6;
}

:deep(.tick text) {
  fill: #6c757d;
  font-size: 16px;
}

:deep(.method-group text) {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
}
</style>
