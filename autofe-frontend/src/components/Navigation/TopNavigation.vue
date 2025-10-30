<template>
  <div class="top-navigation">
    <div class="nav-left">
      <h1 class="welcome-title">Welcome to Adda</h1>
    </div>
    <div class="nav-center">
      <div class="nav-buttons">
        <button
          :class="['nav-btn', { active: currentRoute === 'step-by-step' }]"
          @click="navigateTo('step-by-step')"
        >
          Step-by-Step
        </button>
        <button
          :class="['nav-btn', { active: currentRoute === 'end-to-end' }]"
          @click="navigateTo('end-to-end')"
        >
          End-to-End
        </button>
      </div>
    </div>
    <div class="nav-right">
      <!-- 右侧可以添加其他功能按钮 -->
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'

const router = useRouter()
const route = useRoute()

const currentRoute = computed(() => {
  const path = route.path
  if (path === '/step-by-step') return 'step-by-step'
  if (path === '/end-to-end') return 'end-to-end'
  return 'step-by-step' // 默认
})

const navigateTo = (routeName: string) => {
  router.push(`/${routeName}`)
}

onMounted(() => {
  // 确保当前路由正确
  if (!['/step-by-step', '/end-to-end'].includes(route.path)) {
    router.push('/step-by-step')
  }
})
</script>

<style scoped>
.top-navigation {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1rem 2rem;
  background-color: white;
  border-bottom: 1px solid #e2e8f0;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1), 0 1px 2px rgba(0, 0, 0, 0.06);
  height: 4rem;
  position: sticky;
  top: 0;
  z-index: 100;
}

.nav-left {
  display: flex;
  align-items: center;
}

.welcome-title {
  margin: 0;
  color: #0f172a;
  font-size: 1.25rem;
  font-weight: 600;
  font-family: 'Inter', ui-sans-serif, system-ui, sans-serif;
}

.nav-center {
  display: flex;
  justify-content: center;
  flex: 1;
}

.nav-buttons {
  display: flex;
  gap: 1rem;
  background-color: #f8fafc;
  padding: 0.25rem 0.5rem;
  border-radius: 0.5rem;
  border: 1px solid #e2e8f0;
}

.nav-btn {
  padding: 0.5rem 1.5rem;
  border: none;
  background-color: transparent;
  color: #64748b;
  font-size: 0.875rem;
  font-weight: 500;
  border-radius: 0.5rem;
  cursor: pointer;
  transition: all 0.2s ease;
  position: relative;
  overflow: hidden;
}

.nav-btn:hover {
  color: #0f172a;
  background-color: #f1f5f9;
}

.nav-btn.active {
  background-color: #3b82f6;
  color: white;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1), 0 1px 2px rgba(0, 0, 0, 0.06);
}

.nav-btn.active:hover {
  background-color: #2563eb;
}

.nav-right {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

/* 响应式设计 */
@media (max-width: 768px) {
  .top-navigation {
    padding: 0.75rem 1rem;
  }

  .welcome-title {
    font-size: 1.125rem;
  }

  .nav-buttons {
    gap: 0.5rem;
  }

  .nav-btn {
    padding: 0.5rem 1rem;
    font-size: 0.75rem;
  }
}
</style>