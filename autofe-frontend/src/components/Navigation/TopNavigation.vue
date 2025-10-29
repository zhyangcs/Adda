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
  padding: 12px 24px;
  background: linear-gradient(135deg, #6b46c1 0%, #4c1d95 100%);
  border-bottom: 1px solid #e5e7eb;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
  height: 60px;
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
  color: #ffffff;
  font-size: 1.5rem;
  font-weight: 600;
  text-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
}

.nav-center {
  display: flex;
  justify-content: center;
  flex: 1;
}

.nav-buttons {
  display: flex;
  gap: 16px;
  background: rgba(255, 255, 255, 0.1);
  padding: 4px;
  border-radius: 12px;
  backdrop-filter: blur(10px);
}

.nav-btn {
  padding: 8px 24px;
  border: none;
  background: transparent;
  color: rgba(255, 255, 255, 0.8);
  font-size: 14px;
  font-weight: 500;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.3s ease;
  position: relative;
  overflow: hidden;
}

.nav-btn:hover {
  color: #ffffff;
  background: rgba(255, 255, 255, 0.1);
}

.nav-btn.active {
  background: rgba(255, 255, 255, 0.2);
  color: #ffffff;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.2);
}

.nav-btn.active::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: linear-gradient(135deg, rgba(255, 255, 255, 0.1) 0%, rgba(255, 255, 255, 0.05) 100%);
  border-radius: 8px;
}

.nav-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

/* 响应式设计 */
@media (max-width: 768px) {
  .top-navigation {
    padding: 12px 16px;
  }

  .welcome-title {
    font-size: 1.2rem;
  }

  .nav-buttons {
    gap: 8px;
  }

  .nav-btn {
    padding: 6px 16px;
    font-size: 12px;
  }
}
</style>