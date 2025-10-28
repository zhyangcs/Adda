<template>
  <div class="execution-logs-panel">
    <div class="card h-100">
      <div class="card-header">
        <div class="d-flex justify-content-between align-items-center">
          <h5 class="card-title mb-0">
            <ScrollText :size="20" class="me-2" />
            执行日志
          </h5>
          <div class="header-controls">
            <span class="badge bg-primary me-2">
              {{ taskStore.notifications.length }} 条日志
            </span>
            <button
              class="btn btn-sm btn-outline-secondary"
              @click="refreshLogs"
              :disabled="isRefreshing"
            >
              <RefreshCw :size="14" class="me-1" :class="{ 'animate-spin': isRefreshing }" />
              刷新
            </button>
            <button
              class="btn btn-sm btn-outline-danger"
              @click="clearLogs"
            >
              <Trash2 :size="14" class="me-1" />
              清空
            </button>
          </div>
        </div>
      </div>
      <div class="card-body d-flex flex-column">
        <!-- 过滤器 -->
        <div class="log-filters mb-3">
          <div class="filter-group">
            <label class="form-label me-2 mb-0">类型筛选:</label>
            <div class="btn-group" role="group">
              <button
                type="button"
                class="btn btn-sm"
                :class="filterType === 'all' ? 'btn-primary' : 'btn-outline-secondary'"
                @click="filterType = 'all'"
              >
                全部
              </button>
              <button
                type="button"
                class="btn btn-sm"
                :class="filterType === 'success' ? 'btn-success' : 'btn-outline-secondary'"
                @click="filterType = 'success'"
              >
                成功
              </button>
              <button
                type="button"
                class="btn btn-sm"
                :class="filterType === 'fail' ? 'btn-danger' : 'btn-outline-secondary'"
                @click="filterType = 'fail'"
              >
                失败
              </button>
              <button
                type="button"
                class="btn btn-sm"
                :class="filterType === 'info' ? 'btn-info' : 'btn-outline-secondary'"
                @click="filterType = 'info'"
              >
                信息
              </button>
            </div>
          </div>

          <div class="search-group">
            <div class="input-group">
              <span class="input-group-text">
                <Search :size="14" />
              </span>
              <input
                type="text"
                class="form-control"
                placeholder="搜索日志内容..."
                v-model="searchQuery"
              />
            </div>
          </div>
        </div>

        <!-- 日志列表 -->
        <div class="log-list flex-grow-1">
          <div
            v-if="filteredNotifications.length === 0"
            class="empty-logs"
          >
            <ScrollText :size="48" class="text-muted mb-3" />
            <h6 class="text-muted">暂无日志记录</h6>
            <p class="text-muted small">
              {{ searchQuery ? '没有找到匹配的日志记录' : '开始执行任务后，日志将显示在这里' }}
            </p>
          </div>

          <div
            v-else
            class="notification-list"
            ref="logContainer"
          >
            <div
              v-for="notification in paginatedNotifications"
              :key="notification.id"
              class="notification-item"
              :class="`notification-${notification.notice_type}`"
            >
              <div class="notification-header">
                <div class="notification-type">
                  <component :is="getNotificationIcon(notification.notice_type)" :size="16" />
                </div>
                <div class="notification-time">
                  {{ formatTime(notification.timestamp) }}
                </div>
              </div>
              <div class="notification-content">
                {{ notification.notice_description }}
              </div>
            </div>
          </div>
        </div>

        <!-- 分页控制 -->
        <div
          v-if="totalPages > 1"
          class="pagination-controls mt-3"
        >
          <nav aria-label="日志分页">
            <ul class="pagination justify-content-center mb-0">
              <li class="page-item" :class="{ disabled: currentPage === 1 }">
                <button
                  class="page-link"
                  @click="currentPage = 1"
                  :disabled="currentPage === 1"
                >
                  «
                </button>
              </li>
              <li class="page-item" :class="{ disabled: currentPage === 1 }">
                <button
                  class="page-link"
                  @click="currentPage--"
                  :disabled="currentPage === 1"
                >
                  ‹
                </button>
              </li>

              <li
                v-for="page in visiblePages"
                :key="page"
                class="page-item"
                :class="{ active: page === currentPage }"
              >
                <button
                  class="page-link"
                  @click="currentPage = page"
                >
                  {{ page }}
                </button>
              </li>

              <li class="page-item" :class="{ disabled: currentPage === totalPages }">
                <button
                  class="page-link"
                  @click="currentPage++"
                  :disabled="currentPage === totalPages"
                >
                  ›
                </button>
              </li>
              <li class="page-item" :class="{ disabled: currentPage === totalPages }">
                <button
                  class="page-link"
                  @click="currentPage = totalPages"
                  :disabled="currentPage === totalPages"
                >
                  »
                </button>
              </li>
            </ul>
          </nav>

          <div class="pagination-info text-center small text-muted mt-2">
            显示 {{ startIndex + 1 }}-{{ endIndex }} 条，共 {{ filteredNotifications.length }} 条日志
          </div>
        </div>

        <!-- 自动滚动控制 -->
        <div class="auto-scroll-control mt-2">
          <div class="form-check">
            <input
              type="checkbox"
              class="form-check-input"
              id="autoScroll"
              v-model="autoScroll"
            />
            <label class="form-check-label" for="autoScroll">
              自动滚动到最新日志
            </label>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, nextTick, onMounted, onUnmounted } from 'vue'
import {
  ScrollText,
  RefreshCw,
  Trash2,
  Search,
  CheckCircle,
  XCircle,
  Info
} from 'lucide-vue-next'
import { useTaskStore } from '@/stores/task'

const taskStore = useTaskStore()

// 状态管理
const filterType = ref<'all' | 'success' | 'fail' | 'info'>('all')
const searchQuery = ref('')
const currentPage = ref(1)
const itemsPerPage = ref(10)
const autoScroll = ref(true)
const isRefreshing = ref(false)
const logContainer = ref<HTMLElement>()

// 过滤后的通知
const filteredNotifications = computed(() => {
  let filtered = taskStore.notifications

  // 按类型过滤
  if (filterType.value !== 'all') {
    filtered = filtered.filter(n => n.notice_type === filterType.value)
  }

  // 按搜索关键词过滤
  if (searchQuery.value.trim()) {
    const query = searchQuery.value.toLowerCase()
    filtered = filtered.filter(n =>
      n.notice_description.toLowerCase().includes(query)
    )
  }

  return filtered
})

// 分页相关计算
const totalPages = computed(() => Math.ceil(filteredNotifications.value.length / itemsPerPage.value))

const startIndex = computed(() => (currentPage.value - 1) * itemsPerPage.value)

const endIndex = computed(() => Math.min(startIndex.value + itemsPerPage.value, filteredNotifications.value.length))

const paginatedNotifications = computed(() => {
  return filteredNotifications.value.slice(startIndex.value, endIndex.value)
})

// 可见页码计算
const visiblePages = computed(() => {
  const total = totalPages.value
  const current = currentPage.value
  const delta = 2 // 当前页前后显示的页码数

  const range = []
  const rangeWithDots = []

  for (let i = Math.max(2, current - delta); i <= Math.min(total - 1, current + delta); i++) {
    range.push(i)
  }

  if (current - delta > 2) {
    rangeWithDots.push(1, '...')
  } else {
    rangeWithDots.push(1)
  }

  rangeWithDots.push(...range)

  if (current + delta < total - 1) {
    rangeWithDots.push('...', total)
  } else {
    rangeWithDots.push(total)
  }

  return rangeWithDots.filter(page => page !== '...' || rangeWithDots.indexOf(page) === rangeWithDots.lastIndexOf(page))
})

// 方法
function getNotificationIcon(type: string) {
  const icons = {
    success: CheckCircle,
    fail: XCircle,
    info: Info
  }
  return icons[type as keyof typeof icons] || Info
}

function formatTime(date: Date): string {
  return date.toLocaleTimeString('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit'
  })
}

function refreshLogs() {
  isRefreshing.value = true
  setTimeout(() => {
    isRefreshing.value = false
    taskStore.addNotification('日志已刷新', 'info')
  }, 1000)
}

function clearLogs() {
  taskStore.clearNotifications()
  currentPage.value = 1
  taskStore.addNotification('日志已清空', 'info')
}

// 自动滚动到底部
async function scrollToBottom() {
  if (autoScroll.value && logContainer.value) {
    await nextTick()
    logContainer.value.scrollTop = logContainer.value.scrollHeight
  }
}

// 监听新通知，自动滚动
watch(() => taskStore.notifications.length, () => {
  if (filterType.value === 'all' && !searchQuery.value) {
    currentPage.value = 1
    scrollToBottom()
  }
})

// 监听过滤条件变化，重置分页
watch([filterType, searchQuery], () => {
  currentPage.value = 1
})

// 监听自动滚动
watch(autoScroll, () => {
  if (autoScroll.value) {
    scrollToBottom()
  }
})

// 组件挂载后的初始化
onMounted(() => {
  scrollToBottom()
})

// 组件卸载前清理
onUnmounted(() => {
  // 清理定时器等资源
})
</script>

<style scoped>
.execution-logs-panel {
  height: 100%;
  overflow: hidden;
}

.card {
  border: none;
  box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
  border-radius: 8px;
}

.card-header {
  background-color: #f8f9fa;
  border-bottom: 1px solid #dee2e6;
  padding: 1rem 1.5rem;
}

.card-title {
  color: #495057;
  font-weight: 600;
  display: flex;
  align-items: center;
}

.header-controls {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.log-filters {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 1rem;
  padding: 1rem;
  background-color: #f8f9fa;
  border-radius: 6px;
  border: 1px solid #dee2e6;
}

.filter-group {
  display: flex;
  align-items: center;
}

.search-group {
  min-width: 300px;
}

.log-list {
  overflow-y: auto;
  max-height: 400px;
  border: 1px solid #dee2e6;
  border-radius: 6px;
  background-color: white;
}

.empty-logs {
  height: 300px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: #6c757d;
}

.notification-list {
  padding: 0.5rem;
}

.notification-item {
  display: flex;
  flex-direction: column;
  padding: 0.75rem;
  margin-bottom: 0.5rem;
  border-radius: 6px;
  border-left: 4px solid;
  background-color: #f8f9fa;
  transition: all 0.2s ease;
}

.notification-item:hover {
  background-color: #e9ecef;
  transform: translateX(2px);
}

.notification-item.notification-success {
  border-left-color: #28a745;
  background-color: #d4edda;
}

.notification-item.notification-success:hover {
  background-color: #c3e6cb;
}

.notification-item.notification-fail {
  border-left-color: #dc3545;
  background-color: #f8d7da;
}

.notification-item.notification-fail:hover {
  background-color: #f5c6cb;
}

.notification-item.notification-info {
  border-left-color: #17a2b8;
  background-color: #d1ecf1;
}

.notification-item.notification-info:hover {
  background-color: #bee5eb;
}

.notification-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.5rem;
}

.notification-type {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-weight: 600;
  font-size: 0.8rem;
  text-transform: uppercase;
}

.notification-time {
  font-size: 0.8rem;
  color: #6c757d;
}

.notification-content {
  color: #495057;
  line-height: 1.4;
}

.notification-success .notification-type {
  color: #155724;
}

.notification-fail .notification-type {
  color: #721c24;
}

.notification-info .notification-type {
  color: #0c5460;
}

.pagination-controls {
  border-top: 1px solid #dee2e6;
  padding-top: 1rem;
}

.page-link {
  cursor: pointer;
  transition: all 0.2s ease;
}

.page-link:hover:not(.disabled) {
  background-color: #e9ecef;
  transform: translateY(-1px);
}

.auto-scroll-control {
  border-top: 1px solid #f1f3f4;
  padding-top: 0.75rem;
}

.form-check-input:checked {
  background-color: #007bff;
  border-color: #007bff;
}

/* 动画效果 */
.animate-spin {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}

/* 自定义滚动条 */
.log-list::-webkit-scrollbar {
  width: 6px;
}

.log-list::-webkit-scrollbar-track {
  background: #f1f1f1;
  border-radius: 3px;
}

.log-list::-webkit-scrollbar-thumb {
  background: #c1c1c1;
  border-radius: 3px;
}

.log-list::-webkit-scrollbar-thumb:hover {
  background: #a8a8a8;
}

/* 响应式设计 */
@media (max-width: 768px) {
  .log-filters {
    flex-direction: column;
    align-items: stretch;
    gap: 0.75rem;
  }

  .filter-group {
    justify-content: center;
  }

  .search-group {
    min-width: auto;
  }

  .header-controls {
    flex-direction: column;
    gap: 0.5rem;
  }

  .card-header {
    flex-direction: column;
    align-items: stretch;
  }

  .card-title {
    justify-content: center;
    margin-bottom: 0.5rem;
  }

  .btn-group {
    flex-wrap: wrap;
    justify-content: center;
  }
}
</style>