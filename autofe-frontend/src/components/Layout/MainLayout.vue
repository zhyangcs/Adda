<template>
  <div class="main-layout" :class="{ 'plain-layout': hideChrome }">
    <TopNavigation v-if="!hideChrome" />

    <div class="content-area" :class="{ plain: hideChrome }">
      <AppSidebar v-if="!hideChrome" />

      <div class="center-content" :class="{ plain: hideChrome }">
        <div class="content-wrapper" :class="{ plain: hideChrome }">
          <router-view />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import AppSidebar from './Sidebar/AppSidebar.vue'
import TopNavigation from '../Navigation/TopNavigation.vue'

const route = useRoute()
const hideChrome = computed(() => route.meta.hideChrome === true)
</script>

<style scoped>
.main-layout {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background-color: #f8fafc;
  font-family: 'Inter', ui-sans-serif, system-ui, sans-serif;
}

.main-layout.plain-layout {
  background-color: transparent;
}

.content-area {
  display: flex;
  flex: 1;
  height: calc(100vh - 4rem);
  position: relative;
  overflow: visible;
}

.content-area.plain {
  height: auto;
  min-height: 100vh;
}

.center-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  min-width: 0;
  min-height: 0;
  background-color: #f8fafc;
}

.center-content.plain {
  background-color: transparent;
}

.content-wrapper {
  flex: 1;
  /* allow routed content (e.g. InDatabaseContent) to scroll vertically */
  overflow-y: auto;
  overflow-x: hidden;
  display: flex;
  flex-direction: column;
}

.content-wrapper.plain {
  padding: 0;
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
