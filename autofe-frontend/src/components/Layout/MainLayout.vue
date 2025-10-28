<template>
  <div class="main-layout">
    <!-- 左侧导航栏 -->
    <AppSidebar />

    <!-- 主内容区域 -->
    <div class="content-wrapper">
      <MainContent />
    </div>
  </div>
</template>

<script setup lang="ts">
import AppSidebar from './Sidebar/AppSidebar.vue'
import MainContent from './Content/MainContent.vue'
</script>

<style scoped>
.main-layout {
  display: flex;
  height: 100vh;
  background-color: #f8f9fa;
}

.content-wrapper {
  display: flex;
  flex: 1;
  overflow: hidden;
}
</style>