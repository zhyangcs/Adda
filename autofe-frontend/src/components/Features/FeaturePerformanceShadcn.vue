<template>
  <Card class="feature-performance-container h-full flex flex-col overflow-hidden">
    <CardHeader class="flex flex-row items-center justify-between space-y-0 pb-4">
      <CardTitle class="text-lg font-semibold flex items-center gap-2">
        <i class="bi bi-graph-up text-primary"></i>
        Feature Performance
      </CardTitle>
      <div class="flex gap-1">
        <Button
          variant="ghost"
          size="icon"
          @click="refreshData"
          :disabled="props.isLoading || isRefreshing"
        >
          <i class="bi bi-arrow-clockwise" :class="{ 'animate-spin': props.isLoading || isRefreshing }"></i>
        </Button>
        <Button
          variant="ghost"
          size="icon"
          @click="exportData"
          :disabled="!hasData || props.isLoading"
        >
          <i class="bi bi-download"></i>
        </Button>
      </div>
    </CardHeader>

    <CardContent class="flex-1 overflow-y-auto min-h-0">
      <!-- Loading State -->
      <div v-if="props.isLoading" class="flex flex-col items-center justify-center h-full text-center py-10">
        <div class="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
        <p class="mt-3 mb-0 font-medium">Testing performance...</p>
        <small class="text-muted-foreground">Please wait while we analyze your features</small>
      </div>

      <div v-else-if="hasData" class="space-y-3">
        <!-- Performance Metrics Card -->
        <Card class="hover:shadow-md transition-all duration-200">
          <CardContent class="p-6">
            <div class="flex items-center gap-2 mb-3">
              <i class="bi bi-speedometer2 text-green-600"></i>
              <h6 class="text-sm font-semibold">Performance</h6>
            </div>
            <div class="flex items-baseline gap-2 mb-3">
              <span class="text-4xl font-bold text-green-600">{{ formatPerformance(performanceData?.accuracy || 0) }}</span>
              <span class="text-lg text-muted-foreground uppercase">accuracy</span>
            </div>
            <div class="space-y-2">
              <div class="flex justify-between items-center text-sm">
                <span class="text-muted-foreground">Precision:</span>
                <span class="font-medium">{{ formatPerformance(performanceData?.precision || 0) }}</span>
              </div>
              <div class="flex justify-between items-center text-sm">
                <span class="text-muted-foreground">Recall:</span>
                <span class="font-medium">{{ formatPerformance(performanceData?.recall || 0) }}</span>
              </div>
              <div class="flex justify-between items-center text-sm">
                <span class="text-muted-foreground">F1-Score:</span>
                <span class="font-medium">{{ formatPerformance(performanceData?.f1Score || 0) }}</span>
              </div>
            </div>
          </CardContent>
        </Card>

        <!-- Time Usage Card -->
        <Card class="hover:shadow-md transition-all duration-200">
          <CardContent class="p-6">
            <div class="flex items-center gap-2 mb-3">
              <i class="bi bi-clock text-blue-600"></i>
              <h6 class="text-sm font-semibold">Time Usage</h6>
            </div>
            <div class="flex items-baseline gap-2 mb-3">
              <span class="text-4xl font-bold text-blue-600">{{ formatTime(timeData?.total || 0) }}</span>
              <span class="text-lg text-muted-foreground uppercase">total</span>
            </div>
            <div class="space-y-2">
              <div class="flex justify-between items-center text-sm">
                <span class="text-muted-foreground">Generation:</span>
                <span class="font-medium">{{ formatTime(timeData?.generation || 0) }}</span>
              </div>
              <div class="flex justify-between items-center text-sm">
                <span class="text-muted-foreground">Evaluation:</span>
                <span class="font-medium">{{ formatTime(timeData?.evaluation || 0) }}</span>
              </div>
              <div class="flex justify-between items-center text-sm">
                <span class="text-muted-foreground">Selection:</span>
                <span class="font-medium">{{ formatTime(timeData?.selection || 0) }}</span>
              </div>
            </div>
          </CardContent>
        </Card>

        <!-- SHAP Analysis Card -->
        <Card class="hover:shadow-md transition-all duration-200">
          <CardContent class="p-6">
            <div class="flex items-center gap-2 mb-3">
              <i class="bi bi-bar-chart text-amber-600"></i>
              <h6 class="text-sm font-semibold">SHAP Analysis</h6>
            </div>
            <div class="space-y-3">
              <div class="flex justify-between items-center p-2 bg-amber-50 dark:bg-amber-950 rounded-md border border-amber-200 dark:border-amber-800">
                <span class="text-xs font-medium text-muted-foreground">Mean |SHAP|</span>
                <span class="text-xl font-bold text-amber-600">{{ formatShap(shapData?.meanShap || 0) }}</span>
              </div>
              <div class="space-y-2">
                <div
                  v-for="(feature, index) in topFeatures"
                  :key="index"
                  class="flex items-center gap-2 text-sm"
                >
                  <span class="flex-0 w-28 truncate text-muted-foreground">{{ feature.name }}</span>
                  <div class="flex-1 h-1.5 bg-muted rounded-full overflow-hidden">
                    <div
                      class="h-full bg-gradient-to-r from-amber-500 to-orange-600 rounded-full transition-all duration-300"
                      :style="{ width: `${feature.percentage}%` }"
                    ></div>
                  </div>
                  <span class="flex-0 w-10 text-right font-medium">{{ formatShap(feature.value) }}</span>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      <!-- Empty State -->
      <div v-else class="flex flex-col items-center justify-center h-full text-center py-10">
        <i class="bi bi-graph-up-arrow text-4xl text-muted-foreground mb-4"></i>
        <h3 class="text-lg font-semibold mb-1">No Performance Data</h3>
        <p class="text-muted-foreground mb-5">Execute feature generation and evaluation to see performance metrics</p>
        <Button @click="$emit('generateFeatures')" class="flex items-center gap-2">
          <i class="bi bi-play-circle"></i>
          Generate Features
        </Button>
      </div>
    </CardContent>
  </Card>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'

interface PerformanceData {
  accuracy: number
  precision: number
  recall: number
  f1Score: number
  auc?: number
}

interface TimeData {
  total: number
  generation: number
  evaluation: number
  selection: number
}

interface ShapFeature {
  name: string
  value: number
  percentage: number
}

interface ShapData {
  meanShap: number
  features: ShapFeature[]
}

const props = defineProps<{
  performanceData?: PerformanceData
  timeData?: TimeData
  shapData?: ShapData
  isLoading?: boolean
}>()

const emit = defineEmits<{
  generateFeatures: []
  refreshData: []
}>()

const isRefreshing = ref(false)
const showDetails = ref(false)

const hasData = computed(() => {
  return props.performanceData || props.timeData || props.shapData
})

const topFeatures = computed(() => {
  if (!props.shapData?.features) return []
  return props.shapData.features.slice(0, 5)
})

const formatPerformance = (value: number): string => {
  return (value * 100).toFixed(2) + '%'
}

const formatTime = (value: number): string => {
  if (value < 60) {
    return `${value.toFixed(1)}s`
  } else if (value < 3600) {
    return `${(value / 60).toFixed(1)}m`
  } else {
    return `${(value / 3600).toFixed(2)}h`
  }
}

const formatShap = (value: number): string => {
  return value.toFixed(4)
}

const refreshData = async () => {
  isRefreshing.value = true
  try {
    await new Promise(resolve => setTimeout(resolve, 1000))
    emit('refreshData')
  } finally {
    isRefreshing.value = false
  }
}

const exportData = () => {
  const data = {
    performance: props.performanceData,
    time: props.timeData,
    shap: props.shapData,
    timestamp: new Date().toISOString()
  }

  const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `feature-performance-${Date.now()}.json`
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}
</script>

<style scoped>
.feature-performance-container {
  /* Custom styles if needed */
}
</style>