<template>
  <div class="tab-container">
    <ul class="nav nav-tabs" role="tablist">
      <li class="nav-item" role="presentation">
        <button
          class="nav-link active"
          type="button"
          role="tab"
        >
          <Settings :size="16" class="me-2" />
          任务配置
        </button>
      </li>
      <li class="nav-item" role="presentation">
        <button
          class="nav-link"
          type="button"
          role="tab"
        >
          <GitBranch :size="16" class="me-2" />
          特征生成
        </button>
      </li>
      <li class="nav-item" role="presentation">
        <button
          class="nav-link"
          type="button"
          role="tab"
        >
          <Workflow :size="16" class="me-2" />
          Agent工作流
        </button>
      </li>
      <li class="nav-item" role="presentation">
        <button
          class="nav-link"
          type="button"
          role="tab"
        >
          <ScrollText :size="16" class="me-2" />
          执行日志
        </button>
      </li>
    </ul>
  </div>
</template>

<script setup lang="ts">
import {
  Settings,
  GitBranch,
  Workflow,
  ScrollText
} from 'lucide-vue-next'
</script>

<style scoped>
.tab-container {
  background-color: #ffffff;
  border-bottom: 1px solid #dee2e6;
  padding: 0 1rem;
}

.nav-tabs {
  border-bottom: none;
  flex-wrap: nowrap;
  overflow-x: auto;
}

.nav-link {
  display: flex;
  align-items: center;
  padding: 1rem 1.5rem;
  color: #6c757d;
  border: none;
  border-bottom: 3px solid transparent;
  background-color: transparent;
  white-space: nowrap;
  transition: all 0.2s ease-in-out;
  cursor: pointer;
}

.nav-link:hover {
  color: #495057;
  background-color: #f8f9fa;
  border-bottom-color: #e9ecef;
}

.nav-link.active {
  color: #007bff;
  background-color: transparent;
  border-bottom-color: #007bff;
  font-weight: 600;
}

.nav-link:focus {
  outline: none;
  box-shadow: none;
}

.badge {
  font-size: 0.7rem;
  padding: 0.2rem 0.5rem;
  border-radius: 1rem;
  min-width: 1.5rem;
  text-align: center;
}

/* 自定义滚动条 */
.nav-tabs::-webkit-scrollbar {
  height: 4px;
}

.nav-tabs::-webkit-scrollbar-track {
  background: #f1f1f1;
}

.nav-tabs::-webkit-scrollbar-thumb {
  background: #c1c1c1;
  border-radius: 2px;
}

.nav-tabs::-webkit-scrollbar-thumb:hover {
  background: #a8a8a8;
}
</style>