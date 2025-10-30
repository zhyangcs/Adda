<template>
  <aside class="right-sidebar" :class="{ collapsed: isCollapsed }">
    <!-- 折叠按钮 -->
    <button
      class="collapse-toggle btn btn-sm btn-outline-secondary"
      @click="toggleCollapse"
      :title="isCollapsed ? 'Expand Sidebar' : 'Collapse Sidebar'"
    >
      <ChevronLeft v-if="!isCollapsed" :size="16" />
      <ChevronRight v-else :size="16" />
    </button>

    <!-- 展开时的内容 -->
    <div v-if="!isCollapsed" class="sidebar-content">
      <!-- 标题 -->
      <div class="sidebar-header">
        <h6 class="mb-0">
          <ScrollText :size="16" class="me-2" />
          Execution Logs & System Status
        </h6>
      </div>

      <!-- 通知列表区域 -->
      <div class="notifications-section">
        <div class="section-title">
          <small class="text-muted">System Notifications</small>
          <span class="badge bg-primary" v-if="notifications.length">
            {{ notifications.length }}
          </span>
        </div>

        <!-- 通知列表 -->
        <div class="notifications-list">
          <div
            v-for="notification in paginatedNotifications"
            :key="notification.id"
            class="notification-item"
            :class="`notification-${notification.type}`"
          >
            <div class="notification-content">
              <p class="notification-text mb-1">{{ notification.message }}</p>
              <div class="notification-meta">
                <small class="text-muted">{{ formatTime(notification.timestamp) }}</small>
                <span
                  class="status-badge"
                  :class="`badge bg-${getStatusColor(notification.type)}`"
                >
                  {{ getStatusText(notification.type) }}
                </span>
              </div>
            </div>
          </div>

          <!-- 空状态 -->
          <div v-if="notifications.length === 0" class="empty-notifications">
            <div class="text-center text-muted py-4">
              <Inbox :size="32" class="mb-2" />
              <p class="small mb-0">No system notifications</p>
            </div>
          </div>
        </div>

        <!-- 分页控制 -->
        <div v-if="totalPages > 1" class="pagination-controls">
          <div class="btn-group" role="group">
            <button
              class="btn btn-outline-secondary btn-sm"
              @click="currentPage = Math.max(1, currentPage - 1)"
              :disabled="currentPage === 1"
            >
              Previous
            </button>

            <button
              v-for="page in totalPages"
              :key="page"
              class="btn btn-outline-secondary btn-sm"
              :class="{ active: currentPage === page }"
              @click="currentPage = page"
            >
              {{ page }}
            </button>

            <button
              class="btn btn-outline-secondary btn-sm"
              @click="currentPage = Math.min(totalPages, currentPage + 1)"
              :disabled="currentPage === totalPages"
            >
              Next
            </button>
          </div>
        </div>
      </div>

      <!-- 系统状态 -->
      <div class="system-status-section">
        <div class="section-title">
          <small class="text-muted">System Status</small>
        </div>

        <div class="status-indicators">
          <div class="status-item">
            <div class="d-flex justify-content-between align-items-center">
              <span class="small">Task Status</span>
              <span class="badge" :class="`bg-${getTaskStatusColor()}`">
                {{ taskStore.statusText }}
              </span>
            </div>
          </div>

          <div class="status-item">
            <div class="d-flex justify-content-between align-items-center">
              <span class="small">Feature Count</span>
              <span class="badge bg-info">
                {{ featureTreeStore.currentFeatures.length }}
              </span>
            </div>
          </div>

          <div class="status-item">
            <div class="d-flex justify-content-between align-items-center">
              <span class="small">Execution Mode</span>
              <span class="badge bg-secondary">
                {{ getExecutionModeText() }}
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </aside>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { ChevronLeft, ChevronRight, ScrollText, Inbox } from 'lucide-vue-next'
import { useTaskStore } from '@/stores/task'
import { useFeatureTreeStore } from '@/stores/featureTree'
import { useWorkspaceStore } from '@/stores/workspace'

const taskStore = useTaskStore()
const featureTreeStore = useFeatureTreeStore()
const workspaceStore = useWorkspaceStore()

const isCollapsed = ref(false)
const currentPage = ref(1)
const itemsPerPage = 10

// 监听store中的通知 - 使用task store的通知
const notifications = computed(() => taskStore.notifications.map(n => ({
  id: n.id,
  message: n.notice_description,
  type: n.notice_type,
  timestamp: n.timestamp
})))

// 分页计算
const totalPages = computed(() => Math.ceil(notifications.value.length / itemsPerPage))
const paginatedNotifications = computed(() => {
  const start = (currentPage.value - 1) * itemsPerPage
  const end = start + itemsPerPage
  return notifications.value.slice(start, end)
})

// 方法
function toggleCollapse() {
  isCollapsed.value = !isCollapsed.value
}

function formatTime(timestamp: Date) {
  return new Intl.DateTimeFormat('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit'
  }).format(timestamp)
}

function getStatusColor(type: string) {
  switch (type) {
    case 'success':
      return 'success'
    case 'error':
    case 'fail':
      return 'danger'
    case 'warning':
      return 'warning'
    case 'info':
    default:
      return 'info'
  }
}

function getStatusText(type: string) {
  switch (type) {
    case 'success':
      return 'Success'
    case 'error':
    case 'fail':
      return 'Fail'
    case 'warning':
      return 'Warning'
    case 'info':
    default:
      return 'Info'
  }
}

function getTaskStatusColor() {
  switch (taskStore.status) {
    case 'idle':
      return 'secondary'
    case 'running':
    case 'initializing':
      return 'primary'
    case 'completed':
      return 'success'
    case 'error':
      return 'danger'
    default:
      return 'secondary'
  }
}

function getExecutionModeText() {
  return workspaceStore.executionMode === 'end-to-end' ? 'End-to-End' : 'Step-by-Step'
}

// 监听通知变化，自动跳转到最新页
onMounted(() => {
  // 当有新通知时，自动跳转到第一页（最新）
  const unwatch = notifications.value
  // 这里可以添加watch逻辑
})
</script>

<style scoped>
.right-sidebar {
  width: var(--right-sidebar-width);
  background-color: var(--bg-primary);
  border-left: 1px solid var(--border-color);
  display: flex;
  flex-direction: column;
  transition: all 0.3s ease;
  position: relative;
}

.right-sidebar.collapsed {
  width: 50px;
}

.collapse-toggle {
  position: absolute;
  left: -12px;
  top: 20px;
  z-index: 10;
  border-radius: 50%;
  width: 24px;
  height: 24px;
  padding: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background-color: #f8f9fa;
  border: 1px solid #dee2e6;
}

.sidebar-content {
  display: flex;
  flex-direction: column;
  height: 100%;
  padding: 1rem;
}

.sidebar-header {
  padding-bottom: var(--spacing-lg);
  border-bottom: 1px solid var(--border-color);
  margin-bottom: var(--spacing-lg);
}

.sidebar-header h6 {
  color: var(--text-primary);
  font-weight: 600;
  display: flex;
  align-items: center;
  font-size: var(--font-size-md);
}

.notifications-section {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.section-title {
  display: flex;
  justify-content: between;
  align-items: center;
  margin-bottom: 0.5rem;
}

.notifications-list {
  flex: 1;
  overflow-y: auto;
  margin-bottom: 1rem;
}

.notification-item {
  padding: 0.75rem;
  margin-bottom: 0.5rem;
  border-radius: 0.375rem;
  border-left: 3px solid;
  background-color: #f8f9fa;
}

.notification-success {
  border-left-color: #28a745;
  background-color: #d4edda;
}

.notification-error,
.notification-fail {
  border-left-color: #dc3545;
  background-color: #f8d7da;
}

.notification-warning {
  border-left-color: #ffc107;
  background-color: #fff3cd;
}

.notification-info {
  border-left-color: #17a2b8;
  background-color: #d1ecf1;
}

.notification-content {
  font-size: var(--font-size-base);
}

.notification-text {
  line-height: 1.4;
  word-break: break-word;
}

.notification-meta {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 0.25rem;
}

.status-badge {
  font-size: 0.75rem;
}

.empty-notifications {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 200px;
}

.pagination-controls {
  display: flex;
  justify-content: center;
  padding-top: 0.5rem;
  border-top: 1px solid #dee2e6;
}

.system-status-section {
  padding-top: 1rem;
  border-top: 1px solid #dee2e6;
}

.status-indicators {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.status-item {
  padding: 0.5rem;
  background-color: #f8f9fa;
  border-radius: 0.375rem;
}

/* 滚动条样式 */
.notifications-list::-webkit-scrollbar {
  width: 4px;
}

.notifications-list::-webkit-scrollbar-track {
  background: #f1f1f1;
}

.notifications-list::-webkit-scrollbar-thumb {
  background: #c1c1c1;
  border-radius: 2px;
}

.notifications-list::-webkit-scrollbar-thumb:hover {
  background: #a8a8a8;
}

/* 响应式设计 */
@media (max-width: 1200px) {
  .right-sidebar {
    width: 250px;
  }

  .right-sidebar.collapsed {
    width: 40px;
  }
}
</style>