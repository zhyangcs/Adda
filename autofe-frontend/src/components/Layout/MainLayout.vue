<template>
  <div class="main-layout">
    <!-- 顶部导航栏 -->
    <TopNavigation />

    <div class="content-area">
      <!-- 左侧栏：任务配置与控制 -->
      <AppSidebar />

      <!-- 中间栏：Agent思考过程与特征生成 -->
      <div class="center-content">
        <!-- 执行控制栏 -->
        <ExecutionControlBar />

        <!-- 路由视图内容 -->
        <div class="content-wrapper">
          <router-view />
        </div>
      </div>

      <!-- 右侧栏：执行日志与系统状态 (可折叠) -->
      <RightSidebar />
    </div>
  </div>
</template>

<script setup lang="ts">
import AppSidebar from './Sidebar/AppSidebar.vue'
import TopNavigation from '../Navigation/TopNavigation.vue'
import ExecutionControlBar from './ExecutionControlBar.vue'
import RightSidebar from './Sidebar/RightSidebar.vue'
</script>

<style scoped>
.main-layout {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background-color: #f8fafc;
  font-family: 'Inter', ui-sans-serif, system-ui, sans-serif;
}

.content-area {
  display: flex;
  flex: 1;
  height: calc(100vh - 4rem);
  position: relative;
  overflow: visible;
}

.center-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  min-width: 0;
  background-color: #f8fafc;
}

.content-wrapper {
  flex: 1;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

/* 响应式设计 */
@media (max-width: 1200px) {
  .content-area {
    flex-direction: column;
  }

  .center-content {
    min-height: 400px;
  }
}
</style>