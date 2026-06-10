<script setup lang="ts">
import { onMounted } from 'vue'
import MainLayout from '@/components/Layout/MainLayout.vue'
import { useTaskStore } from '@/stores/task'
import { useAgentStore } from '@/stores/agent'

const taskStore = useTaskStore()
const agentStore = useAgentStore()

onMounted(() => {
  // 初始化时检查任务状态
  taskStore.checkTaskStatus()

  // 初始化WebSocket连接
  agentStore.initializeWebSocket()
})
</script>

<template>
  <div id="app">
    <MainLayout />
  </div>
</template>

<style>
/* CSS 变量定义 - 统一管理整个应用的字体和间距 */
:root {
  /* 字体大小 - Gradio 风格的字体大小 */
  --font-size-xs: 0.75rem;    /* 12px */
  --font-size-sm: 0.875rem;   /* 14px */
  --font-size-base: 1rem;     /* 16px */
  --font-size-md: 1.125rem;   /* 18px */
  --font-size-lg: 1.25rem;    /* 20px */
  --font-size-xl: 1.5rem;     /* 24px */
  --font-size-2xl: 1.875rem;  /* 30px */
  --font-size-3xl: 2.25rem;   /* 36px */

  /* 间距 - 简洁的间距系统 */
  --spacing-xs: 0.25rem;   /* 4px */
  --spacing-sm: 0.5rem;    /* 8px */
  --spacing-md: 1rem;      /* 16px */
  --spacing-lg: 1.5rem;    /* 24px */
  --spacing-xl: 2rem;      /* 32px */
  --spacing-2xl: 3rem;     /* 48px */
  --spacing-3xl: 4rem;     /* 64px */

  /* 组件尺寸 - 适当调大 */
  --sidebar-width: 340px;
  --right-sidebar-width: 340px;
  --header-height: 64px;
  --control-bar-height: 68px;

  /* 颜色变量 - Gradio 风格的颜色 */
  --text-primary: #0f0f0f;
  --text-secondary: #666666;
  --text-muted: #999999;
  --text-placeholder: #cccccc;
  --bg-primary: #ffffff;
  --bg-secondary: #fafafa;
  --bg-light: #f5f5f5;
  --border-color: #e0e0e0;
  --primary-color: #007bff;
  --primary-hover: #0056b3;

  /* 阴影 - Gradio 风格的轻量阴影 */
  --shadow-sm: 0 1px 3px rgba(0, 0, 0, 0.1), 0 1px 2px rgba(0, 0, 0, 0.06);
  --shadow-md: 0 4px 6px rgba(0, 0, 0, 0.1), 0 2px 4px rgba(0, 0, 0, 0.06);
  --shadow-lg: 0 10px 15px rgba(0, 0, 0, 0.1), 0 4px 6px rgba(0, 0, 0, 0.05);

  /* 字体 */
  --font-mono: 'JetBrains Mono', 'Fira Code', 'Consolas', 'Monaco', 'Courier New', monospace;
}

/* 全局样式 */
#app {
  font-family: 'Inter', ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, 'Noto Sans', sans-serif;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  color: var(--text-primary);
  background-color: var(--bg-secondary);
  min-height: 100vh;
  margin: 0;
  padding: 0;
  font-size: var(--font-size-base);
  line-height: 1.5;
}

/* 三栏布局全局样式 */
.three-column-layout {
  display: flex;
  height: 100vh;
  overflow: hidden;
}

.column-transition {
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

/* 防止flexbox收缩 */
.flex-shrink-0 {
  flex-shrink: 0;
}

.flex-min-0 {
  min-width: 0;
}

/* Bootstrap 自定义 - using traditional CSS for Tailwind v4 compatibility */
.btn {
  transition: all 0.2s ease;
}

.btn:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
}

.card {
  transition: box-shadow 0.2s ease;
}

.card:hover {
  box-shadow: 0 4px 15px rgba(0, 0, 0, 0.1);
}

.form-control:focus,
.form-select:focus {
  border-color: #3b82f6;
  box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.2);
}

/* Gradio 风格的表单元素覆盖 */
.form-control {
  border-radius: 0.5rem;
  border: 1px solid #cbd5e1;
  padding: 0.5rem 0.75rem;
  font-size: 0.875rem;
  transition: all 0.2s ease;
  background-color: white;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1), 0 1px 2px rgba(0, 0, 0, 0.06);
}

.form-control:focus {
  outline: none;
  border-color: #3b82f6;
  box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.2);
}

.form-select {
  border-radius: 0.5rem;
  border: 1px solid #cbd5e1;
  padding: 0.5rem 0.75rem;
  font-size: 0.875rem;
  transition: all 0.2s ease;
  background-color: white;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1), 0 1px 2px rgba(0, 0, 0, 0.06);
}

.form-select:focus {
  outline: none;
  border-color: #3b82f6;
  box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.2);
}

.form-label {
  font-size: 0.875rem;
  font-weight: 500;
  color: #334155;
  margin-bottom: 0.25rem;
  display: block;
  font-family: 'Inter', ui-sans-serif, system-ui, sans-serif;
}

/* Gradio 风格的按钮覆盖 */
.btn-primary {
  background-color: #3b82f6;
  color: white;
  font-weight: 500;
  padding: 0.5rem 1rem;
  border-radius: 0.5rem;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1), 0 1px 2px rgba(0, 0, 0, 0.06);
  transition: all 0.2s ease;
  border: none;
}

.btn-primary:hover {
  background-color: #2563eb;
  box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1), 0 2px 4px rgba(0, 0, 0, 0.06);
  transform: translateY(-1px);
}

.btn-primary:focus {
  outline: none;
  box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.2);
}

.btn-secondary {
  background-color: #f1f5f9;
  color: #0f172a;
  font-weight: 500;
  padding: 0.5rem 1rem;
  border-radius: 0.5rem;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1), 0 1px 2px rgba(0, 0, 0, 0.06);
  transition: all 0.2s ease;
  border: none;
}

.btn-secondary:hover {
  background-color: #e2e8f0;
  box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1), 0 2px 4px rgba(0, 0, 0, 0.06);
  transform: translateY(-1px);
}

.btn-secondary:focus {
  outline: none;
  box-shadow: 0 0 0 2px rgba(71, 85, 105, 0.2);
}

.btn-outline-primary {
  border: 1px solid #3b82f6;
  background-color: white;
  color: #3b82f6;
  font-weight: 500;
  padding: 0.5rem 1rem;
  border-radius: 0.5rem;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1), 0 1px 2px rgba(0, 0, 0, 0.06);
  transition: all 0.2s ease;
}

.btn-outline-primary:hover {
  background-color: #eff6ff;
  box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1), 0 2px 4px rgba(0, 0, 0, 0.06);
  transform: translateY(-1px);
}

.btn-outline-primary:focus {
  outline: none;
  box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.2);
}

/* 动画效果 */
@keyframes fadeIn {
  from {
    opacity: 0;
    transform: translateY(20px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.fade-in {
  animation: fadeIn 0.3s ease-out;
}

@keyframes slideInLeft {
  from {
    opacity: 0;
    transform: translateX(-30px);
  }
  to {
    opacity: 1;
    transform: translateX(0);
  }
}

@keyframes slideInRight {
  from {
    opacity: 0;
    transform: translateX(30px);
  }
  to {
    opacity: 1;
    transform: translateX(0);
  }
}

.slide-in-left {
  animation: slideInLeft 0.3s ease-out;
}

.slide-in-right {
  animation: slideInRight 0.3s ease-out;
}

/* 呼吸灯效果 */
@keyframes breathe {
  0%, 100% {
    box-shadow: 0 0 0 0 rgba(0, 123, 255, 0.7);
  }
  50% {
    box-shadow: 0 0 0 10px rgba(0, 123, 255, 0);
  }
}

.breathe-effect {
  animation: breathe 2s ease-in-out infinite;
}

/* 滚动条样式 */
::-webkit-scrollbar {
  width: 8px;
  height: 8px;
}

::-webkit-scrollbar-track {
  background: #f1f3f4;
  border-radius: 4px;
}

::-webkit-scrollbar-thumb {
  background: #c1c1c1;
  border-radius: 4px;
}

::-webkit-scrollbar-thumb:hover {
  background: #a8a8a8;
}

/* 自定义滚动条 - 细版 */
.thin-scrollbar::-webkit-scrollbar {
  width: 4px;
}

.thin-scrollbar::-webkit-scrollbar-track {
  background: transparent;
}

.thin-scrollbar::-webkit-scrollbar-thumb {
  background: rgba(0, 0, 0, 0.2);
  border-radius: 2px;
}

.thin-scrollbar::-webkit-scrollbar-thumb:hover {
  background: rgba(0, 0, 0, 0.3);
}

/* 响应式断点优化 */
@media (max-width: 1200px) {
  #app {
    font-size: var(--font-size-base);
  }

  .three-column-layout {
    flex-direction: column;
  }

  :root {
    --sidebar-width: 300px;
    --right-sidebar-width: 300px;
    --font-size-xs: 0.75rem;   /* 12px */
    --font-size-sm: 0.875rem;  /* 14px */
    --font-size-base: 1rem;    /* 16px */
    --font-size-md: 1.125rem;  /* 18px */
    --font-size-lg: 1.25rem;   /* 20px */
    --font-size-xl: 1.5rem;    /* 24px */
    --font-size-2xl: 1.75rem;  /* 28px */
    --font-size-3xl: 2rem;     /* 32px */
  }

  .hide-on-mobile {
    display: none !important;
  }
}

@media (max-width: 768px) {
  #app {
    font-size: var(--font-size-sm);
  }

  .mobile-stacking .column {
    width: 100% !important;
    min-height: 300px;
  }

  :root {
    --sidebar-width: 260px;
    --right-sidebar-width: 260px;
    --font-size-xs: 0.75rem;   /* 12px */
    --font-size-sm: 0.875rem;  /* 14px */
    --font-size-base: 0.9375rem;/* 15px */
    --font-size-md: 1.0625rem; /* 17px */
    --font-size-lg: 1.1875rem;  /* 19px */
    --font-size-xl: 1.3125rem;  /* 21px */
    --font-size-2xl: 1.5rem;   /* 24px */
    --font-size-3xl: 1.75rem;  /* 28px */
    --spacing-lg: 0.75rem;
    --spacing-xl: 1rem;
  }
}

/* 整体布局优化 */
.content-layout {
  display: flex;
  flex-direction: column;
  height: 100vh;
  overflow: hidden;
}

.main-content-wrapper {
  flex: 1;
  display: flex;
  overflow: hidden;
}

/* 提升视觉层次 */
.visual-hierarchy-1 { font-size: var(--font-size-3xl); font-weight: 700; }
.visual-hierarchy-2 { font-size: var(--font-size-2xl); font-weight: 600; }
.visual-hierarchy-3 { font-size: var(--font-size-xl); font-weight: 600; }
.visual-hierarchy-4 { font-size: var(--font-size-lg); font-weight: 500; }
.visual-hierarchy-5 { font-size: var(--font-size-base); font-weight: 400; }
.visual-hierarchy-6 { font-size: var(--font-size-sm); font-weight: 400; }

/* 统一卡片样式 */
.unified-card {
  background: var(--bg-primary);
  border-radius: 12px;
  box-shadow: var(--shadow-sm);
  border: 1px solid var(--border-color);
  overflow: hidden;
  transition: all 0.2s ease;
}

.unified-card:hover {
  box-shadow: var(--shadow-md);
  transform: translateY(-1px);
}

/* 统一按钮样式增强 */
.btn-enhanced {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: var(--spacing-xs);
  padding: var(--spacing-sm) var(--spacing-lg);
  border-radius: 6px;
  font-weight: 500;
  font-size: var(--font-size-sm);
  transition: all 0.2s ease;
  cursor: pointer;
  border: none;
  white-space: nowrap;
}

.btn-enhanced:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: var(--shadow-md);
}

.btn-enhanced:active:not(:disabled) {
  transform: translateY(0);
}

/* 数据展示优化 */
.data-display {
  font-family: var(--font-mono);
  font-size: var(--font-size-sm);
  line-height: 1.6;
  background: #1e1e1e;
  color: #d4d4d4;
  padding: var(--spacing-lg);
  border-radius: 8px;
  overflow-x: auto;
}

/* 性能指标卡片优化 */
.metric-card-enhanced {
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: 12px;
  padding: var(--spacing-lg);
  transition: all 0.3s ease;
}

.metric-card-enhanced:hover {
  box-shadow: var(--shadow-lg);
  transform: translateY(-2px);
}

/* 滚动条统一优化 */
.enhanced-scrollbar::-webkit-scrollbar {
  width: 6px;
  height: 6px;
}

.enhanced-scrollbar::-webkit-scrollbar-track {
  background: var(--bg-secondary);
  border-radius: 3px;
}

.enhanced-scrollbar::-webkit-scrollbar-thumb {
  background: var(--text-muted);
  border-radius: 3px;
  transition: background 0.2s ease;
}

.enhanced-scrollbar::-webkit-scrollbar-thumb:hover {
  background: var(--text-secondary);
}

/* 折叠动画 */
.collapsible {
  overflow: hidden;
  transition: all 0.3s ease-in-out;
}

.collapsible.collapsed {
  width: 50px !important;
  min-width: 50px !important;
}

.collapsible.collapsed .collapsible-content {
  opacity: 0;
  pointer-events: none;
}

.collapsible:not(.collapsed) .collapsible-content {
  opacity: 1;
  pointer-events: auto;
}

/* 状态指示器 */
.status-indicator {
  position: relative;
}

.status-indicator::before {
  content: '';
  position: absolute;
  top: 50%;
  left: -12px;
  transform: translateY(-50%);
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background-color: #6c757d;
}

.status-indicator.status-success::before {
  background-color: #28a745;
}

.status-indicator.status-warning::before {
  background-color: #ffc107;
}

.status-indicator.status-error::before {
  background-color: #dc3545;
}

.status-indicator.status-info::before {
  background-color: #17a2b8;
}

/* 加载状态 */
.loading {
  opacity: 0.6;
  pointer-events: none;
  position: relative;
}

.loading::after {
  content: '';
  position: absolute;
  top: 50%;
  left: 50%;
  width: 20px;
  height: 20px;
  margin: -10px 0 0 -10px;
  border: 2px solid #f3f3f3;
  border-top: 2px solid #007bff;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}

/* 工具提示样式 */
.tooltip-container {
  position: relative;
}

.tooltip-container .tooltip-content {
  position: absolute;
  bottom: 100%;
  left: 50%;
  transform: translateX(-50%);
  background-color: rgba(0, 0, 0, 0.8);
  color: white;
  padding: 0.5rem 0.75rem;
  border-radius: 0.375rem;
  font-size: 0.875rem;
  white-space: nowrap;
  opacity: 0;
  pointer-events: none;
  transition: opacity 0.2s ease;
  z-index: 1000;
  margin-bottom: 0.5rem;
}

.tooltip-container:hover .tooltip-content {
  opacity: 1;
}

/* 网格背景 */
.grid-background {
  background-image:
    linear-gradient(rgba(0, 0, 0, 0.03) 1px, transparent 1px),
    linear-gradient(90deg, rgba(0, 0, 0, 0.03) 1px, transparent 1px);
  background-size: 20px 20px;
}

/* 毛玻璃效果 */
.glass-effect {
  background-color: rgba(255, 255, 255, 0.8);
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
  border: 1px solid rgba(255, 255, 255, 0.2);
}

/* 边框动画 */
@keyframes borderFlow {
  0% {
    border-color: #007bff;
  }
  25% {
    border-color: #28a745;
  }
  50% {
    border-color: #ffc107;
  }
  75% {
    border-color: #dc3545;
  }
  100% {
    border-color: #007bff;
  }
}

.border-flow {
  animation: borderFlow 3s ease-in-out infinite;
}

/* 阴影效果 */
.shadow-soft {
  box-shadow: 0 2px 15px rgba(0, 0, 0, 0.08), 0 1px 2px rgba(0, 0, 0, 0.04);
}

.shadow-medium {
  box-shadow: 0 4px 25px rgba(0, 0, 0, 0.12), 0 2px 4px rgba(0, 0, 0, 0.06);
}

.shadow-strong {
  box-shadow: 0 10px 40px rgba(0, 0, 0, 0.15), 0 4px 8px rgba(0, 0, 0, 0.08);
}
</style>
