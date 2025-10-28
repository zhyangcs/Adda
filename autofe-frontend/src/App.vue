<script setup lang="ts">
import { onMounted } from 'vue'
import MainLayout from '@/components/Layout/MainLayout.vue'
import { useTaskStore } from '@/stores/task'

const taskStore = useTaskStore()

onMounted(() => {
  // 初始化时检查任务状态
  taskStore.checkTaskStatus()
})
</script>

<template>
  <div id="app">
    <MainLayout />
  </div>
</template>

<style>
/* 全局样式 */
#app {
  font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  color: #495057;
  background-color: #f8f9fa;
  min-height: 100vh;
  margin: 0;
  padding: 0;
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

/* Bootstrap 自定义 */
.btn {
  transition: all 0.2s ease-in-out;
}

.btn:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
}

.card {
  transition: box-shadow 0.2s ease-in-out;
}

.card:hover {
  box-shadow: 0 4px 15px rgba(0, 0, 0, 0.1);
}

.form-control:focus,
.form-select:focus {
  border-color: #007bff;
  box-shadow: 0 0 0 0.2rem rgba(0, 123, 255, 0.25);
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

/* 响应式断点 */
@media (max-width: 1200px) {
  #app {
    font-size: 15px;
  }

  .three-column-layout {
    flex-direction: column;
  }

  .hide-on-mobile {
    display: none !important;
  }
}

@media (max-width: 768px) {
  #app {
    font-size: 14px;
  }

  .mobile-stacking .column {
    width: 100% !important;
    min-height: 300px;
  }
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
