<template>
  <div class="main-layout">
    <!-- 左侧栏：任务配置与控制 -->
    <AppSidebar />

    <!-- 中间栏：Agent思考过程与特征生成 -->
    <div class="center-content">
      <MainContent />
    </div>

    <!-- 右侧栏：执行日志与系统状态 (可折叠) -->
    <RightSidebar />
  </div>
</template>

<script setup lang="ts">
import AppSidebar from './Sidebar/AppSidebar.vue'
import MainContent from './Content/MainContent.vue'
import RightSidebar from './Sidebar/RightSidebar.vue'
</script>

<style scoped>
.main-layout {
  display: flex;
  height: 100vh;
  background-color: #f8f9fa;
}

.center-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  min-width: 0; /* 允许flexbox收缩 */
}

/* 响应式设计 */
@media (max-width: 1200px) {
  .main-layout {
    flex-direction: column;
  }

  .center-content {
    min-height: 400px;
  }
}
</style>