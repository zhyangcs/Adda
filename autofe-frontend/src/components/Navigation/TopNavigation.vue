<template>
  <div class="top-navigation">
    <div class="nav-left">
      <h1 class="welcome-title">Welcome to Adda</h1>
    </div>
    <div class="nav-center">
      <div class="workflow-switch">
        <button
          class="workflow-btn"
          :class="{ active: currentRoute === 'agent-feature-generation' }"
          @click="navigateTo('agent-feature-generation')"
        >
          Agent-driven Feature Generation
        </button>
        <button
          class="workflow-btn"
          :class="{ active: currentRoute === 'in-database-feature-computation' }"
          @click="navigateTo('in-database-feature-computation')"
        >
          In-Database Feature Computation
        </button>
        <button
          class="workflow-btn"
          :class="{ active: currentRoute === 'performance' }"
          @click="navigateTo('performance')"
        >
          Performance
        </button>
      </div>
    </div>
    <div class="nav-right"></div>
  </div>
</template>

<script setup lang="ts">
import { computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useWorkspaceStore } from '@/stores/workspace'

const route = useRoute()
const router = useRouter()
const workspaceStore = useWorkspaceStore()

const currentRoute = computed(() => {
  const path = route.path
  if (path === '/agent-feature-generation') return 'agent-feature-generation'
  if (path === '/in-database-feature-computation') return 'in-database-feature-computation'
  if (path === '/performance') return 'performance'
  return 'agent-feature-generation'
})

function navigateTo(routeName: string) {
  const modeMap: Record<string, 'agent' | 'in-db' | 'performance'> = {
    'agent-feature-generation': 'agent',
    'in-database-feature-computation': 'in-db',
    'performance': 'performance'
  }
  workspaceStore.setExecutionMode(modeMap[routeName] || 'agent')
  router.push(`/${routeName}`)
}

// Keep execution mode in sync when using browser navigation
watch(() => route.path, (path) => {
  if (path === '/agent-feature-generation') workspaceStore.setExecutionMode('agent')
  else if (path === '/in-database-feature-computation') workspaceStore.setExecutionMode('in-db')
  else if (path === '/performance') workspaceStore.setExecutionMode('performance')
}, { immediate: true })
</script>

<style scoped>
.top-navigation {
  display: flex;
  align-items: center;
  padding: 1rem 1.5rem;
  background-color: white;
  border-bottom: 1px solid #e2e8f0;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1), 0 1px 2px rgba(0, 0, 0, 0.06);
  height: 4rem;
  position: sticky;
  top: 0;
  z-index: 100;
  gap: 1rem;
}

.nav-left {
  flex: 1;
  display: flex;
  align-items: center;
  min-width: 0;
}

.nav-center {
  flex: 1;
  display: flex;
  justify-content: center;
}

.welcome-title {
  margin: 0;
  color: #0f172a;
  font-size: 1.1rem;
  font-weight: 600;
  font-family: 'Inter', ui-sans-serif, system-ui, sans-serif;
  white-space: nowrap;
}

.nav-right {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 0.75rem;
  justify-content: flex-end;
  min-width: 0;
}

.workflow-switch {
  display: inline-flex;
  gap: 0.35rem;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  padding: 0.35rem;
  box-shadow: inset 0 1px 2px rgba(15, 23, 42, 0.05);
}

.workflow-btn {
  border: none;
  background: transparent;
  padding: 0.55rem 0.9rem;
  border-radius: 8px;
  font-size: 0.9rem;
  font-weight: 600;
  color: #475569;
  cursor: pointer;
  transition: all 0.15s ease;
  white-space: nowrap;
}

.workflow-btn:hover {
  background: #e5edfb;
  color: #1d4ed8;
}

.workflow-btn.active {
  background: #2563eb;
  color: white;
  box-shadow: 0 4px 10px rgba(37, 99, 235, 0.25);
}

/* 响应式设计 */
@media (max-width: 1024px) {
  .top-navigation {
    padding: 0.75rem 1rem;
  }

  .workflow-switch {
    gap: 0.25rem;
    padding: 0.25rem;
  }

  .workflow-btn {
    padding: 0.45rem 0.7rem;
    font-size: 0.85rem;
  }
}

@media (max-width: 768px) {
  .top-navigation {
    flex-direction: column;
    align-items: flex-start;
    height: auto;
    gap: 0.5rem;
  }

  .nav-right {
    width: 100%;
    justify-content: flex-start;
  }

  .workflow-switch {
    width: 100%;
    flex-wrap: wrap;
  }

  .workflow-btn {
    flex: 1 1 auto;
    text-align: center;
  }
}
</style>
