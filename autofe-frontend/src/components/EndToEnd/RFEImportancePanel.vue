<template>
  <div class="rfe-panel">
    <div class="panel-header">
      <div class="panel-title">
        <i class="bi bi-arrow-repeat"></i>
        RFE Feature Importance
      </div>
      <div class="panel-meta" v-if="hasData">
        <span class="meta-badge">{{ topFeatures.length }}</span>
        <span class="meta-text">features</span>
      </div>
    </div>

    <div class="panel-content">
      <div v-if="!hasData" class="empty-state">
        <i class="bi bi-activity"></i>
        <p>No RFE importance results yet.</p>
        <small>Run the end-to-end analysis to populate this chart.</small>
      </div>

      <div v-else class="bar-list">
        <div
          v-for="(item, index) in topFeatures"
          :key="item.feature"
          class="bar-row"
        >
          <div class="label">
            <span class="rank">#{{ index + 1 }}</span>
            <span class="name" :title="item.feature">{{ item.feature }}</span>
            <span
              v-if="item.isGenerated"
              class="badge-new"
              title="Generated feature"
            >NEW</span>
          </div>
          <div class="bar">
            <div class="bar-fill" :style="{ width: getBarWidth(item.importance) }"></div>
          </div>
          <div class="value" :title="valueTitle(item)">
            {{ formatValue(item) }}
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { FeatureImportance } from '@/types'

const props = defineProps<{ rfeData: FeatureImportance[] | null | undefined }>()

const cleanedData = computed(() => {
  if (!props.rfeData) return []
  return props.rfeData
    .filter(item => item && typeof item.importance === 'number' && isFinite(item.importance))
})

const sortedData = computed(() => [...cleanedData.value].sort((a, b) => b.importance - a.importance))
const topFeatures = computed(() => sortedData.value.slice(0, 15))
const maxImportance = computed(() => topFeatures.value.reduce((max, item) => Math.max(max, item.importance), 0))
const hasData = computed(() => topFeatures.value.length > 0)

const getBarWidth = (importance: number) => {
  const safeMax = maxImportance.value > 0 ? maxImportance.value : 1
  const width = (importance / safeMax) * 100
  const minWidth = importance > 0 ? 4 : 0
  return `${Math.max(width, minWidth)}%`
}

const formatValue = (item: FeatureImportance) => (item.rawImportance ?? item.importance).toFixed(3)
const valueTitle = (item: FeatureImportance) => `Scaled: ${item.importance.toFixed(4)} | Raw: ${(item.rawImportance ?? item.importance).toFixed(4)}`
</script>

<style scoped>
.rfe-panel {
  background: #fff;
  border-radius: 12px;
  border: none;
  box-shadow: none;
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 10px 14px;
  border-bottom: 2px solid var(--accent-blue, #2a7de1);
}

.panel-title {
  display: flex;
  align-items: center;
  gap: 10px;
  font-weight: 700;
  font-size: 20px;
  color: var(--text-primary);
}

.panel-meta {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  background: #f7f9fc;
  border: 1px solid var(--border-color);
  border-radius: 20px;
  padding: 6px 10px;
  font-size: 12px;
  color: var(--text-secondary);
}

.meta-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  border-radius: 50%;
  background: var(--primary-color);
  color: #fff;
  font-weight: 700;
}

.meta-text {
  font-weight: 600;
}

.panel-content {
  flex: 1;
  overflow-y: auto;
  padding: 14px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.empty-state {
  margin: auto;
  text-align: center;
  color: var(--text-secondary);
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.empty-state i {
  font-size: 32px;
  opacity: 0.5;
}

.bar-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.bar-row {
  display: grid;
  grid-template-columns: 1fr 2fr auto;
  gap: 10px;
  align-items: center;
  padding: 8px 10px;
  background: #f7f9fc;
  border: 1px solid var(--border-color);
  border-radius: 10px;
}

.label {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.badge-new {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 4px 6px;
  border-radius: 10px;
  background: rgba(40, 167, 69, 0.18);
  color: #1e9b43;
  font-size: 11px;
  font-weight: 800;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.rank {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 26px;
  height: 26px;
  border-radius: 50%;
  background: rgba(0, 123, 255, 0.12);
  color: var(--primary-color);
  font-weight: 700;
  font-size: 12px;
}

.name {
  font-weight: 600;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.bar {
  width: 100%;
  height: 10px;
  background: var(--bg-light, #eef1f5);
  border-radius: 999px;
  overflow: hidden;
}

.bar-fill {
  height: 100%;
  background: linear-gradient(90deg, var(--primary-color), #4dabf7);
  border-radius: 999px;
  transition: width 0.3s ease;
}

.value {
  font-family: 'Monaco', 'Menlo', monospace;
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}

@media (max-width: 768px) {
  .bar-row {
    grid-template-columns: 1fr;
    align-items: flex-start;
  }

  .value {
    text-align: right;
  }
}
</style>
