<template>
  <div class="feature-importance-panel">
    <div class="panel-header">
      <div class="panel-title">
        <i class="bi bi-bar-chart"></i>
        Feature Importance Analysis
      </div>
      <div class="panel-actions">
        <button
          class="btn-icon"
          @click="exportData"
          title="Export importance data"
        >
          <i class="bi bi-download"></i>
        </button>
        <button
          class="btn-icon"
          @click="toggleFullscreen"
          title="Toggle fullscreen"
        >
          <i class="bi" :class="isFullscreen ? 'bi-fullscreen-exit' : 'bi-fullscreen'"></i>
        </button>
      </div>
    </div>

    <div class="panel-content" :class="{ 'fullscreen': isFullscreen }">
      <!-- 重要性指标选择 -->
      <div class="importance-tabs">
        <button
          v-for="tab in importanceTabs"
          :key="tab.key"
          class="tab-button"
          :class="{ active: selectedMethod === tab.key }"
          @click="setSelectedMethod(tab.key)"
        >
          <i :class="tab.icon"></i>
          {{ tab.label }}
        </button>
      </div>

      <!-- 可视化内容 -->
      <div class="visualization-container">
        <!-- Paper Metrics 视图 -->
        <div v-if="selectedMethod === 'paper'" class="paper-metrics-container">
          <!-- Paper Metrics 概览 -->
          <div v-if="!hasPaperMetrics" class="no-data-message">
            <i class="bi bi-journal-x"></i>
            <h4>No Paper Metrics Available</h4>
            <p>Feature importance analysis results are not available. Please run the end-to-end analysis with paper metrics enabled.</p>
          </div>

          <div v-else class="paper-content">
            <!-- 方法表现对比 -->
            <div class="method-performance">
              <div class="performance-header">
                <h6>Generated Features in Top-{{ paperMetrics?.top_k || 7 }} Analysis</h6>
              </div>

              <div class="performance-grid">
                <div
                  v-for="method in ['shap', 'ig', 'rfe', 'fi']"
                  :key="method"
                  class="performance-card"
                  :class="{ 'best-performer': bestPerformingMethod?.method.toLowerCase() === method }"
                >
                  <div class="method-header">
                    <span class="method-name">{{ method.toUpperCase() }}</span>
                    <span class="method-percentage">
                      {{ getMethodTopKPerformance(method)?.percentage.toFixed(1) || 0 }}%
                    </span>
                  </div>

                  <div class="progress-container">
                    <div class="progress-bar">
                      <div
                        class="progress-fill generated"
                        :style="{ width: `${getMethodTopKPerformance(method)?.percentage || 0}%` }"
                      ></div>
                    </div>
                    <div class="progress-labels">
                      <span class="generated-count">
                        {{ getMethodTopKPerformance(method)?.generated_count || 0 }}
                      </span>
                      <span class="total-count">
                        / {{ paperMetrics?.top_k || 7 }}
                      </span>
                    </div>
                  </div>

                  <!-- Top特征列表 -->
                  <div class="top-features-list">
                    <div class="list-header">Top Features:</div>
                    <div
                      v-for="(feature, index) in getMethodTopKPerformance(method)?.top_features_analysis.slice(0, 3)"
                      :key="feature.feature"
                      class="feature-item"
                      :class="{ 'generated-feature': feature.is_generated }"
                    >
                      <span class="feature-rank">{{ feature.rank }}.</span>
                      <span class="feature-name">{{ feature.feature }}</span>
                      <span class="feature-badge">
                        {{ feature.is_generated ? 'New' : 'Original' }}
                      </span>
                    </div>
                  </div>
                </div>
              </div>

              <!-- 简单的特征数量概览 -->
              <div class="simple-overview-internal">
                <div class="overview-item">
                  <span class="overview-label">Original Features:</span>
                  <span class="overview-value original">{{ paperMetrics?.original_feature_count || 0 }}</span>
                </div>
                <div class="overview-item">
                  <span class="overview-label">New Features:</span>
                  <span class="overview-value generated">{{ paperMetrics?.generated_feature_count || 0 }}</span>
                </div>
                <div class="overview-item">
                  <span class="overview-label">Total Features:</span>
                  <span class="overview-value total">{{ paperMetrics?.total_feature_count || 0 }}</span>
                </div>
              </div>
            </div>

            </div>
        </div>

        <!-- 条形图视图 -->
        <div v-else-if="selectedMethod !== 'radar'" class="bar-chart-container">
          <div ref="barChartRef" class="bar-chart"></div>

          <!-- 特征排名表格 -->
          <div class="feature-rankings">
            <div class="rankings-header">
              <h6>Feature Rankings</h6>
              <span class="method-badge">{{ getMethodLabel(selectedMethod) }}</span>
            </div>
            <div class="rankings-list">
              <div
                v-for="(feature, index) in currentFeatures"
                :key="feature.feature"
                class="ranking-item"
                :class="{ 'top-feature': index < 3 }"
              >
                <div class="rank-badge" :class="getRankClass(index)">
                  {{ index + 1 }}
                </div>
                <div class="feature-info">
                  <span class="feature-name">{{ feature.feature }}</span>
                  <div class="importance-bar">
                    <div
                      class="importance-fill"
                      :style="{ width: `${(feature.importance / maxImportance) * 100}%` }"
                    ></div>
                  </div>
                </div>
                <div class="importance-value">
                  <span :title="`Original value: ${feature.rawImportance?.toFixed(6) || feature.importance.toFixed(6)}`">
                    {{ feature.rawImportance?.toFixed(3) || feature.importance.toFixed(3) }}
                  </span>
                  <span v-if="feature.scalingFactor && feature.scalingFactor !== 1"
                        class="scaling-indicator"
                        title="Value scaled for visualization">
                    ×{{ feature.scalingFactor }}
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- 雷达图视图 -->
        <div v-else class="radar-chart-container">
          <div ref="radarChartRef" class="radar-chart"></div>

          <!-- 方法对比表格 -->
          <div class="method-comparison">
            <div class="comparison-header">
              <h6>Method Comparison</h6>
            </div>
            <div class="comparison-table">
              <div class="table-header">
                <div class="header-cell">Feature</div>
                <div class="header-cell" v-for="method in ['SHAP', 'IG', 'RFE', 'FI']" :key="method">
                  {{ method }}
                </div>
              </div>
              <div
                v-for="feature in topFeatures"
                :key="feature.name"
                class="table-row"
              >
                <div class="cell feature-cell">{{ feature.name }}</div>
                <div class="cell">{{ getRawFeatureImportance('shap', feature.name).toFixed(3) }}</div>
                <div class="cell">{{ getRawFeatureImportance('ig', feature.name).toFixed(3) }}</div>
                <div class="cell">{{ getRawFeatureImportance('rfe', feature.name).toFixed(3) }}</div>
                <div class="cell">{{ getRawFeatureImportance('fi', feature.name).toFixed(3) }}</div>
              </div>
            </div>
          </div>
        </div>
      </div>

      </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'
import * as d3 from 'd3'
import type { ImportanceData, FeatureImportance, PaperMetrics } from '@/types'

const props = defineProps<{
  importanceData: ImportanceData | null
}>()

const barChartRef = ref<HTMLElement>()
const radarChartRef = ref<HTMLElement>()
const selectedMethod = ref<'shap' | 'ig' | 'rfe' | 'fi' | 'radar' | 'paper'>('paper')
const isFullscreen = ref(false)

const importanceTabs = [
  { key: 'paper', label: 'Paper Analysis', icon: 'bi bi-journal-text' },
  { key: 'shap', label: 'SHAP', icon: 'bi bi-lightning' },
  { key: 'ig', label: 'Integrated Gradients', icon: 'bi bi-graph-up' },
  { key: 'rfe', label: 'RFE', icon: 'bi bi-arrow-repeat' },
  { key: 'fi', label: 'Feature Importance', icon: 'bi bi-star' },
  { key: 'radar', label: 'Compare All', icon: 'bi bi-diagram-3' }
]

let barSvg: d3.Selection<SVGSVGElement, unknown, null, undefined> | null = null
let radarSvg: d3.Selection<SVGSVGElement, unknown, null, undefined> | null = null

const currentFeatures = computed(() => {
  if (!props.importanceData || selectedMethod.value === 'radar' || selectedMethod.value === 'paper') {
    return []
  }
  return props.importanceData[selectedMethod.value as keyof ImportanceData] || []
})

const maxImportance = computed(() => {
  if (currentFeatures.value.length === 0) return 1
  const values = currentFeatures.value.map(f => f.importance)
  return Math.max(...values, 1)
})

const topFeatures = computed(() => {
  if (!props.importanceData) return []

  // 获取所有方法的前5个特征的并集
  const allFeatures = new Set<string>()

  Object.values(props.importanceData).forEach(features => {
    features.slice(0, 5).forEach(f => allFeatures.add(f.feature))
  })

  return Array.from(allFeatures).slice(0, 8).map(name => ({
    name,
    shap: getRawFeatureImportance('shap', name),
    ig: getRawFeatureImportance('ig', name),
    rfe: getRawFeatureImportance('rfe', name),
    fi: getRawFeatureImportance('fi', name)
  }))
})


// Paper Metrics 相关计算属性
const paperMetrics = computed(() => {
  return props.importanceData?.paperMetrics
})

const hasPaperMetrics = computed(() => {
  return paperMetrics.value && paperMetrics.value.success
})


// 获取方法在Top-K中的表现
const getMethodTopKPerformance = (method: keyof typeof paperMetrics.value.top_k_analysis) => {
  if (!hasPaperMetrics.value) return null
  const analysis = paperMetrics.value!.top_k_analysis[method]
  return analysis || null
}


const getFeatureImportance = (method: keyof ImportanceData, featureName: string): number => {
  if (!props.importanceData) return 0
  const feature = props.importanceData[method].find(f => f.feature === featureName)
  return feature ? feature.importance : 0
}

const getRawFeatureImportance = (method: keyof ImportanceData, featureName: string): number => {
  if (!props.importanceData) return 0
  const feature = props.importanceData[method].find(f => f.feature === featureName)
  return feature ? (feature.rawImportance || feature.importance) : 0
}

const getMethodLabel = (method: string): string => {
  const tab = importanceTabs.find(t => t.key === method)
  return tab ? tab.label : method.toUpperCase()
}

const getRankClass = (index: number): string => {
  if (index === 0) return 'rank-gold'
  if (index === 1) return 'rank-silver'
  if (index === 2) return 'rank-bronze'
  return 'rank-normal'
}


const setSelectedMethod = (method: 'shap' | 'ig' | 'rfe' | 'fi' | 'radar' | 'paper') => {
  selectedMethod.value = method
  nextTick(() => {
    if (method === 'radar') {
      createRadarChart()
    } else if (method === 'paper') {
      // Paper metrics不需要创建图表，只需要刷新
      console.log('Switched to paper metrics view')
      console.log('Paper metrics data:', paperMetrics.value)
      console.log('Has paper metrics:', hasPaperMetrics.value)
    } else if (method !== 'paper' && method !== 'radar') {
      createBarChart()
    }
  })
}

const createBarChart = () => {
  if (!barChartRef.value || selectedMethod.value === 'radar' || selectedMethod.value === 'paper') return

  const container = barChartRef.value
  const width = container.clientWidth
  const height = 280

  // 清除现有图表
  d3.select(container).selectAll('*').remove()

  barSvg = d3.select(container)
    .append('svg')
    .attr('width', width)
    .attr('height', height)

  const margin = { top: 20, right: 30, bottom: 80, left: 60 }
  const innerWidth = width - margin.left - margin.right
  const innerHeight = height - margin.top - margin.bottom

  const g = barSvg.append('g')
    .attr('transform', `translate(${margin.left},${margin.top})`)

  // 如果没有数据，显示空图表
  if (currentFeatures.value.length === 0) {
    showEmptyBarChart(g, innerWidth, innerHeight)
    return
  }

  // 比例尺
  const xScale = d3.scaleBand()
    .domain(currentFeatures.value.map(d => d.feature))
    .range([0, innerWidth])
    .padding(0.3)

  const yScale = d3.scaleLinear()
    .domain([0, maxImportance.value])
    .nice()
    .range([innerHeight, 0])

  // 颜色比例尺
  const colorScale = d3.scaleSequential(d3.interpolateBlues)
    .domain([0, maxImportance.value])

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
      .tickFormat(d3.format('.3f'))
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
    .text('Importance Score')

  // 柱状图
  const bars = g.selectAll('.bar')
    .data(currentFeatures.value)
    .enter().append('rect')
    .attr('class', 'bar')
    .attr('x', d => xScale(d.feature) || 0)
    .attr('width', xScale.bandwidth())
    .attr('y', innerHeight)
    .attr('height', 0)
    .attr('fill', d => colorScale(d.importance))
    .attr('rx', 3)
    .style('cursor', 'pointer')

  // 动画
  bars.transition()
    .duration(800)
    .delay((d, i) => i * 100)
    .attr('y', d => yScale(d.importance))
    .attr('height', d => innerHeight - yScale(d.importance))

  // 数值标签
  g.selectAll('.label')
    .data(currentFeatures.value)
    .enter().append('text')
    .attr('class', 'label')
    .attr('x', d => (xScale(d.feature) || 0) + xScale.bandwidth() / 2)
    .attr('y', d => yScale(d.importance) - 5)
    .attr('text-anchor', 'middle')
    .style('font-size', '11px')
    .style('font-weight', 'bold')
    .style('fill', d => colorScale(d.importance))
    .style('opacity', 0)
    .text(d => (d.rawImportance || d.importance).toFixed(3))
    .transition()
    .duration(800)
    .delay((d, i) => i * 100 + 400)
    .style('opacity', 1)
}

const createRadarChart = () => {
  if (!radarChartRef.value) return

  const container = radarChartRef.value
  const size = Math.min(container.clientWidth, 300)
  const height = size
  const width = size

  // 清除现有图表
  d3.select(container).selectAll('*').remove()

  radarSvg = d3.select(container)
    .append('svg')
    .attr('width', width)
    .attr('height', height)

  const g = radarSvg.append('g')
    .attr('transform', `translate(${width / 2},${height / 2})`)

  // 如果没有数据，显示空图表
  if (topFeatures.value.length === 0) {
    showEmptyRadarChart(g, Math.min(width, height) / 2 - 40)
    return
  }

  const radius = Math.min(width, height) / 2 - 40
  const angleSlice = (Math.PI * 2) / topFeatures.value.length

  // 比例尺
  const rScale = d3.scaleLinear()
    .domain([0, 1])
    .range([0, radius])

  // 颜色
  const colors = {
    shap: '#007bff',
    ig: '#28a745',
    rfe: '#ffc107',
    fi: '#dc3545'
  }

  // 绘制网格
  for (let level = 1; level <= 5; level++) {
    const levelRadius = (radius / 5) * level
    g.append('circle')
      .attr('r', levelRadius)
      .style('fill', 'none')
      .style('stroke', '#e0e0e0')
      .style('stroke-width', '1px')

    // 添加刻度标签
    if (level === 5) {
      g.append('text')
        .attr('x', 5)
        .attr('y', -levelRadius + 3)
        .style('font-size', '10px')
        .style('fill', '#999')
        .text((level / 5).toFixed(1))
    }
  }

  // 绘制轴线
  topFeatures.value.forEach((feature, i) => {
    const angle = angleSlice * i - Math.PI / 2
    const x = Math.cos(angle) * radius
    const y = Math.sin(angle) * radius

    g.append('line')
      .attr('x1', 0)
      .attr('y1', 0)
      .attr('x2', x)
      .attr('y2', y)
      .style('stroke', '#e0e0e0')
      .style('stroke-width', '1px')

    // 特征标签
    const labelX = Math.cos(angle) * (radius + 20)
    const labelY = Math.sin(angle) * (radius + 20)

    g.append('text')
      .attr('x', labelX)
      .attr('y', labelY)
      .style('text-anchor', 'middle')
      .style('dominant-baseline', 'middle')
      .style('font-size', '11px')
      .style('fill', '#495057')
      .text(feature.name.length > 12 ? feature.name.substring(0, 12) + '...' : feature.name)
  })

  // 绘制每个方法的数据
  Object.entries(colors).forEach(([method, color]) => {
    const data = topFeatures.value.map(feature => {
      const importance = getFeatureImportance(method as keyof ImportanceData, feature.name)
      return {
        feature: feature.name,
        importance: importance / maxImportance.value // 标准化
      }
    })

    const lineGenerator = d3.lineRadial()
      .angle((d: any, i) => i * angleSlice)
      .radius((d: any) => rScale(d.importance))
      .curve(d3.curveLinearClosed)

    // 绘制区域
    g.append('path')
      .datum(data)
      .attr('d', lineGenerator)
      .style('fill', color)
      .style('fill-opacity', 0.1)
      .style('stroke', color)
      .style('stroke-width', '2px')

    // 绘制点
    g.selectAll(`.dot-${method}`)
      .data(data)
      .enter().append('circle')
      .attr('class', `dot-${method}`)
      .attr('cx', (d: any, i) => Math.cos(i * angleSlice - Math.PI / 2) * rScale(d.importance))
      .attr('cy', (d: any, i) => Math.sin(i * angleSlice - Math.PI / 2) * rScale(d.importance))
      .attr('r', 4)
      .style('fill', color)
      .style('stroke', 'white')
      .style('stroke-width', '1px')
  })

  // 图例
  const legend = radarSvg.append('g')
    .attr('transform', `translate(10, 10)`)

  Object.entries(colors).forEach(([method, color], i) => {
    const legendItem = legend.append('g')
      .attr('transform', `translate(0, ${i * 20})`)

    legendItem.append('rect')
      .attr('width', 12)
      .attr('height', 12)
      .style('fill', color)
      .style('stroke', color)

    legendItem.append('text')
      .attr('x', 16)
      .attr('y', 9)
      .style('font-size', '11px')
      .style('fill', '#495057')
      .text(method.toUpperCase())
  })
}

const toggleFullscreen = () => {
  isFullscreen.value = !isFullscreen.value
  setTimeout(() => {
    if (selectedMethod.value === 'radar') {
      createRadarChart()
    } else {
      createBarChart()
    }
  }, 100)
}

const exportData = () => {
  const data = {
    selectedMethod: selectedMethod.value,
    features: currentFeatures.value,
    timestamp: new Date().toISOString()
  }

  const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `feature-importance-${selectedMethod.value}-${Date.now()}.json`
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}

// 响应式处理
const handleResize = () => {
  if (selectedMethod.value === 'radar' && radarChartRef.value) {
    createRadarChart()
  } else if (selectedMethod.value !== 'radar' && barChartRef.value) {
    createBarChart()
  }
}

onMounted(() => {
  createBarChart()
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
})

watch(() => props.importanceData, () => {
  nextTick(() => {
    if (selectedMethod.value === 'radar') {
      createRadarChart()
    } else {
      createBarChart()
    }
  })
}, { deep: true })

// 空图表显示函数
const showEmptyBarChart = (g: d3.Selection<SVGGElement, unknown, null, undefined>, width: number, height: number) => {
  // 绘制空的坐标轴
  const xScale = d3.scaleBand()
    .domain([])
    .range([0, width])
    .padding(0.3)

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
    .text('Importance')

  // X轴标签
  g.append('text')
    .attr('transform', `translate(${width / 2}, ${height + 70})`)
    .style('text-anchor', 'middle')
    .style('font-size', '12px')
    .style('fill', '#6c757d')
    .text('Features')

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

const showEmptyRadarChart = (g: d3.Selection<SVGGElement, unknown, null, undefined>, radius: number) => {
  // 绘制空的雷达图背景
  const levels = 5
  const angleSlice = (Math.PI * 2) / 6 // 默认6个维度

  // 绘制同心圆
  for (let level = 1; level <= levels; level++) {
    g.append('circle')
      .attr('r', (radius / levels) * level)
      .style('fill', 'none')
      .style('stroke', '#dee2e6')
      .style('stroke-opacity', 0.5)
  }

  // 绘制轴线
  for (let i = 0; i < 6; i++) {
    const angle = angleSlice * i - Math.PI / 2
    const x = Math.cos(angle) * radius
    const y = Math.sin(angle) * radius

    g.append('line')
      .attr('x1', 0)
      .attr('y1', 0)
      .attr('x2', x)
      .attr('y2', y)
      .style('stroke', '#dee2e6')
      .style('stroke-opacity', 0.5)
  }

  // 空状态提示
  g.append('text')
    .attr('x', 0)
    .attr('y', 0)
    .attr('text-anchor', 'middle')
    .style('font-size', '14px')
    .style('fill', '#6c757d')
    .style('opacity', 0.6)
    .text('No data available')
}
</script>

<style scoped>
.feature-importance-panel {
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
  border-bottom: 2px solid var(--accent-blue, #2a7de1);
  background: transparent;
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
  gap: 4px;
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

.panel-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  min-height: 0;
}

.panel-content.fullscreen {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 1000;
  border-radius: 0;
  background: var(--bg-white);
}

.importance-tabs {
  display: flex;
  border-bottom: 2px solid var(--accent-blue, #2a7de1);
  background: transparent;
  flex-shrink: 0;
  overflow-x: auto;
}

.tab-button {
  background: none;
  border: none;
  padding: 10px 14px;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 6px;
  color: var(--text-secondary);
  font-size: 18px;
  font-weight: 500;
  border-bottom: 2px solid transparent;
  transition: all 0.2s ease;
  white-space: nowrap;
}

.tab-button:hover {
  color: var(--text-primary);
  background: rgba(0, 123, 255, 0.05);
}

.tab-button.active {
  color: var(--accent-blue, #2a7de1);
  border-bottom-color: var(--accent-blue, #2a7de1);
  background: rgba(42, 125, 225, 0.1);
}

.visualization-container {
  flex: 1;
  overflow-y: auto;
  min-height: 0;
  padding: 16px;
}

.bar-chart-container,
.radar-chart-container {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.bar-chart,
.radar-chart {
  flex-shrink: 0;
}

.feature-rankings {
  background: var(--bg-light);
  border-radius: 8px;
  padding: 16px;
  border: 1px solid var(--border-color);
}

.rankings-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.rankings-header h6 {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
}

.method-badge {
  background: var(--primary-color);
  color: white;
  padding: 4px 8px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 500;
}

.rankings-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.ranking-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px;
  background: white;
  border-radius: 6px;
  border: 1px solid var(--border-color);
  transition: all 0.2s ease;
}

.ranking-item:hover {
  box-shadow: none;
  transform: translateY(-1px);
}

.ranking-item.top-feature {
  border-color: var(--primary-color);
  background: rgba(0, 123, 255, 0.02);
}

.rank-badge {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 600;
  color: white;
  flex-shrink: 0;
}

.rank-gold { background: linear-gradient(135deg, #FFD700, #FFA500); }
.rank-silver { background: linear-gradient(135deg, #C0C0C0, #808080); }
.rank-bronze { background: linear-gradient(135deg, #CD7F32, #8B4513); }
.rank-normal { background: #6c757d; }

.feature-info {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}

.feature-name {
  font-size: 14px;
  font-weight: 500;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.importance-bar {
  height: 4px;
  background: var(--border-color);
  border-radius: 2px;
  overflow: hidden;
}

.importance-fill {
  height: 100%;
  background: linear-gradient(90deg, var(--primary-color), #4dabf7);
  border-radius: 2px;
  transition: width 0.8s ease;
}

.importance-value {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
  font-family: 'Monaco', 'Menlo', monospace;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 2px;
}

.scaling-indicator {
  font-size: 10px;
  color: #6c757d;
  font-weight: 400;
  opacity: 0.7;
}

.method-comparison {
  background: var(--bg-light);
  border-radius: 8px;
  padding: 16px;
  border: 1px solid var(--border-color);
}

.comparison-header h6 {
  margin: 0 0 12px 0;
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
}

.comparison-table {
  font-size: 16px;
}

.table-header {
  display: grid;
  grid-template-columns: 1fr repeat(4, 1fr);
  gap: 8px;
  padding: 8px;
  background: var(--bg-primary);
  border-radius: 6px;
  font-weight: 600;
  color: var(--text-primary);
}

.header-cell {
  text-align: center;
}

.table-row {
  display: grid;
  grid-template-columns: 1fr repeat(4, 1fr);
  gap: 8px;
  padding: 8px;
  border-bottom: 1px solid var(--border-color);
}

.table-row:hover {
  background: white;
}

.cell {
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-secondary);
}

.feature-cell {
  justify-content: flex-start;
  font-weight: 500;
  color: var(--text-primary);
}


/* 响应式设计 */
@media (max-width: 768px) {
  .importance-tabs {
    justify-content: flex-start;
  }

  .tab-button {
    padding: 8px 10px;
    font-size: 11px;
  }

  .visualization-container {
    padding: 12px;
  }

  .feature-rankings,
  .method-comparison {
    padding: 12px;
  }

  .ranking-item {
    padding: 6px;
    gap: 8px;
  }

  .rank-badge {
    width: 20px;
    height: 20px;
    font-size: 10px;
  }

  .feature-name {
    font-size: 12px;
  }

  .stats-panel {
    flex-direction: column;
    gap: 8px;
  }

  .stat-item {
    flex-direction: row;
    justify-content: space-between;
  }

  .comparison-table {
    font-size: 11px;
  }

  .table-header,
  .table-row {
    gap: 4px;
  }
}

/* Paper Metrics 样式 */
.paper-metrics-container {
  height: 100%;
  overflow-y: auto;
  padding: 16px;
}

.no-data-message {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 300px;
  color: var(--text-secondary);
  text-align: center;
}

.no-data-message i {
  font-size: 48px;
  margin-bottom: 16px;
  opacity: 0.5;
}

.no-data-message h4 {
  margin: 0 0 8px 0;
  color: var(--text-primary);
}

.no-data-message p {
  margin: 0;
  font-size: 14px;
  max-width: 400px;
}

.paper-content {
  display: flex;
  flex-direction: column;
  gap: 24px;
}


/* 方法表现对比 */
.method-performance {
  background: var(--bg-light);
  border-radius: 8px;
  padding: 20px;
  border: 1px solid var(--border-color);
}

.performance-header {
  display: flex;
  justify-content: center;
  align-items: center;
  margin-bottom: 20px;
}

.performance-header h6 {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
  color: var(--text-primary);
}

.performance-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 16px;
}

.performance-card {
  background: white;
  border: 1px solid var(--border-color);
  border-radius: 8px;
  padding: 16px;
  transition: all 0.2s ease;
}

.performance-card:hover {
  box-shadow: none;
}

.performance-card.best-performer {
  border-color: #ffc107;
  box-shadow: none;
}

.method-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.method-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}

.method-percentage {
  font-size: 14px;
  font-weight: 600;
  color: var(--primary-color);
}

.progress-container {
  margin-bottom: 12px;
}

.progress-bar {
  width: 100%;
  height: 8px;
  background: var(--border-color);
  border-radius: 4px;
  overflow: hidden;
  margin-bottom: 6px;
}

.progress-fill.generated {
  height: 100%;
  background: linear-gradient(90deg, #28a745, #20c997);
  border-radius: 4px;
  transition: width 0.8s ease;
}

.progress-labels {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  color: var(--text-secondary);
}

.generated-count {
  font-weight: 600;
  color: #28a745;
}

.top-features-list {
  border-top: 1px solid var(--border-color);
  padding-top: 8px;
}

.list-header {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-secondary);
  margin-bottom: 6px;
}

.feature-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 2px 0;
  font-size: 11px;
}

.feature-item.generated-feature .feature-name {
  color: #28a745;
  font-weight: 500;
}

.feature-rank {
  color: var(--text-secondary);
  font-weight: 500;
  min-width: 16px;
}

.feature-name {
  flex: 1;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.feature-badge {
  font-size: 10px;
  padding: 2px 4px;
  border-radius: 4px;
  background: var(--bg-light);
  color: var(--text-secondary);
}

.feature-item.generated-feature .feature-badge {
  background: rgba(40, 167, 69, 0.1);
  color: #28a745;
}

/* Paper Analysis 内部的特征数量概览 */
.simple-overview-internal {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 24px;
  margin-top: 20px;
  padding: 12px 16px;
  background: white;
  border: 1px solid var(--border-color);
  border-radius: 6px;
}

.simple-overview-internal .overview-item {
  display: flex;
  align-items: center;
  gap: 6px;
}

.simple-overview-internal .overview-label {
  font-size: 13px;
  color: var(--text-secondary);
  font-weight: 500;
}

.simple-overview-internal .overview-value {
  font-size: 14px;
  font-weight: 600;
  font-family: 'Monaco', 'Menlo', monospace;
}

.simple-overview-internal .overview-value.original {
  color: #007bff;
}

.simple-overview-internal .overview-value.generated {
  color: #28a745;
}

.simple-overview-internal .overview-value.total {
  color: #6f42c1;
}

/* 响应式设计调整 */
@media (max-width: 1200px) {
  .performance-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 768px) {
  .performance-header {
    text-align: center;
  }

  .simple-overview-internal {
    flex-direction: column;
    gap: 10px;
    text-align: center;
  }

  .simple-overview-internal .overview-item {
    justify-content: center;
  }
}

/* D3图表样式 */
:deep(.bar) {
  transition: all 0.2s ease;
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
