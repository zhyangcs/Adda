<template>
  <div class="main-content">
    <!-- 标签页导航 -->
    <TabContainer />

    <!-- 面板内容 -->
    <div class="content-panels">
      <TaskConfigPanel />
    </div>
  </div>
</template>

<script setup lang="ts">
import TaskConfigPanel from '../../Panels/TaskConfigPanel.vue'
import TabContainer from '../../Tabs/TabContainer.vue'
</script>

<style scoped>
.main-content {
  display: flex;
  flex: 1;
  flex-direction: column;
  overflow: hidden;
}

.content-panels {
  flex: 1;
  overflow: hidden;
  padding: 1rem;
  background-color: #ffffff;
}
</style>