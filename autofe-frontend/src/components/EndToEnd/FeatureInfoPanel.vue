<template>
  <div class="feature-info-panel">
    <div class="panel-header">
      <div class="panel-title">
        <i class="bi bi-file-code"></i>
        Feature Information
      </div>
      <div class="panel-actions">
        <button
          class="btn-icon"
          @click="copyToClipboard"
          :disabled="!activeContent"
          :title="'Copy ' + activeTab + ' to clipboard'"
        >
          <i class="bi bi-clipboard"></i>
        </button>
        <button
          class="btn-icon"
          @click="toggleFullscreen"
          :title="'Toggle fullscreen'"
        >
          <i class="bi" :class="isFullscreen ? 'bi-fullscreen-exit' : 'bi-fullscreen'"></i>
        </button>
      </div>
    </div>

    <div class="panel-content" :class="{ 'fullscreen': isFullscreen }">
      <!-- 标签页导航 -->
      <div class="tab-navigation">
        <button
          v-for="tab in tabs"
          :key="tab.key"
          class="tab-button"
          :class="{ active: activeTab === tab.key }"
          @click="setActiveTab(tab.key)"
        >
          <i :class="tab.icon"></i>
          {{ tab.label }}
        </button>
      </div>

      <!-- 标签页内容 -->
      <div class="tab-content">
        <!-- 特征描述 -->
        <div v-if="activeTab === 'description'" class="content-section description-content">
          <div class="markdown-content" v-html="formattedDescription"></div>
        </div>

        <!-- Python代码 -->
        <div v-else-if="activeTab === 'python'" class="content-section code-content">
          <div class="code-header">
            <span class="code-language">Python</span>
            <div class="code-actions">
              <button class="btn-small" @click="formatPythonCode" title="Format code">
                <i class="bi bi-braces"></i>
              </button>
              <button class="btn-small" @click="copyToClipboard" title="Copy code">
                <i class="bi bi-clipboard"></i>
              </button>
            </div>
          </div>
          <pre class="code-block"><code class="language-python">{{ featureData.pythonCode }}</code></pre>
        </div>

        <!-- SQL代码 -->
        <div v-else-if="activeTab === 'sql'" class="content-section code-content">
          <div class="code-header">
            <span class="code-language">SQL</span>
            <div class="code-actions">
              <button class="btn-small" @click="formatSqlCode" title="Format SQL">
                <i class="bi bi-braces"></i>
              </button>
              <button class="btn-small" @click="copyToClipboard" title="Copy SQL">
                <i class="bi bi-clipboard"></i>
              </button>
            </div>
          </div>
          <pre class="code-block"><code class="language-sql">{{ featureData.sqlCode }}</code></pre>
        </div>
      </div>
    </div>

    <!-- 复制成功提示 -->
    <div v-if="showCopyNotification" class="copy-notification">
      <i class="bi bi-check-circle"></i>
      Copied to clipboard!
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import type { FeatureInfo } from './mockData'

interface Tab {
  key: 'description' | 'python' | 'sql'
  label: string
  icon: string
}

const props = defineProps<{
  featureData: FeatureInfo
}>()

const tabs: Tab[] = [
  { key: 'description', label: 'Description', icon: 'bi bi-info-circle' },
  { key: 'python', label: 'Python Code', icon: 'bi bi-filetype-py' },
  { key: 'sql', label: 'SQL Code', icon: 'bi bi-filetype-sql' }
]

const activeTab = ref<'description' | 'python' | 'sql'>('description')
const isFullscreen = ref(false)
const showCopyNotification = ref(false)

const activeContent = computed(() => {
  switch (activeTab.value) {
    case 'description':
      return props.featureData.description
    case 'python':
      return props.featureData.pythonCode
    case 'sql':
      return props.featureData.sqlCode
    default:
      return ''
  }
})

const formattedDescription = computed(() => {
  // 简单的Markdown格式化
  return props.featureData.description
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/\n/g, '<br>')
    .replace(/(\d+\.\s)/g, '<br><br>$1')
    .replace(/^<br>/, '')
})

const setActiveTab = (tab: 'description' | 'python' | 'sql') => {
  activeTab.value = tab
}

const toggleFullscreen = () => {
  isFullscreen.value = !isFullscreen.value
}

const copyToClipboard = async () => {
  try {
    await navigator.clipboard.writeText(activeContent.value || '')
    showCopyNotification.value = true
    setTimeout(() => {
      showCopyNotification.value = false
    }, 2000)
  } catch (err) {
    console.error('Failed to copy to clipboard:', err)
  }
}

const formatPythonCode = () => {
  // 这里可以添加代码格式化逻辑
  console.log('Formatting Python code...')
}

const formatSqlCode = () => {
  // 这里可以添加SQL格式化逻辑
  console.log('Formatting SQL code...')
}
</script>

<style scoped>
.feature-info-panel {
  background: var(--bg-white);
  border-radius: 12px;
  box-shadow: var(--shadow-sm);
  border: 1px solid var(--border-color);
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
  position: relative;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  border-bottom: 1px solid var(--border-color);
  background: var(--bg-light);
  flex-shrink: 0;
}

.panel-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 600;
  color: var(--text-primary);
  font-size: 18px;
}

.panel-actions {
  display: flex;
  gap: 4px;
}

.btn-icon, .btn-small {
  background: none;
  border: none;
  padding: 6px;
  border-radius: 6px;
  cursor: pointer;
  color: var(--text-secondary);
  transition: all 0.2s ease;
  display: flex;
  align-items: center;
  justify-content: center;
}

.btn-icon:hover:not(:disabled), .btn-small:hover {
  background: var(--bg-primary);
  color: var(--primary-color);
}

.btn-icon:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-small {
  padding: 4px 6px;
  font-size: 18px;
}

.panel-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  min-height: 0;
}

.panel-content.fullscreen {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 1000;
  border-radius: 0;
  background: var(--bg-white);
}

.tab-navigation {
  display: flex;
  border-bottom: 1px solid var(--border-color);
  background: var(--bg-light);
  flex-shrink: 0;
}

.tab-button {
  background: none;
  border: none;
  padding: 12px 16px;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 6px;
  color: var(--text-secondary);
  font-size: 14px;
  font-weight: 500;
  border-bottom: 2px solid transparent;
  transition: all 0.2s ease;
}

.tab-button:hover {
  color: var(--text-primary);
  background: rgba(0, 123, 255, 0.05);
}

.tab-button.active {
  color: var(--primary-color);
  border-bottom-color: var(--primary-color);
  background: rgba(0, 123, 255, 0.1);
}

.tab-content {
  flex: 1;
  overflow-y: auto;
  min-height: 0;
}

.content-section {
  padding: 16px;
}

.description-content {
  line-height: 1.6;
}

.markdown-content {
  color: var(--text-primary);
  font-size: 20px;
}

.markdown-content :deep(strong) {
  color: var(--text-primary);
  font-weight: 600;
}

.code-content {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.code-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 12px;
  background: var(--bg-light);
  border: 1px solid var(--border-color);
  border-bottom: none;
  border-radius: 8px 8px 0 0;
  flex-shrink: 0;
}

.code-language {
  font-size: 18px;
  font-weight: 600;
  color: var(--text-secondary);
  text-transform: uppercase;
}

.code-actions {
  display: flex;
  gap: 4px;
}

.code-block {
  margin: 0;
  background: #f8f9fa;
  border: 1px solid var(--border-color);
  border-radius: 0 0 8px 8px;
  overflow: auto;
  flex: 1;
  font-size: 18px;
  line-height: 1.5;
}

.code-block code {
  font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
  display: block;
  padding: 16px;
  color: #24292e;
  white-space: pre;
  overflow-x: auto;
  font-size: 22px;
}

/* 语法高亮（简单版本） */
.language-python :deep(.keyword) { color: #d73a49; }
.language-python :deep(.string) { color: #032f62; }
.language-python :deep(.comment) { color: #6a737d; }
.language-python :deep(.function) { color: #6f42c1; }

.language-sql :deep(.keyword) { color: #d73a49; font-weight: bold; }
.language-sql :deep(.function) { color: #6f42c1; }
.language-sql :deep(.string) { color: #032f62; }
.language-sql :deep(.comment) { color: #6a737d; }

.copy-notification {
  position: absolute;
  top: 60px;
  right: 16px;
  background: var(--success-color, #28a745);
  color: white;
  padding: 8px 12px;
  border-radius: 6px;
  font-size: 18px;
  font-weight: 500;
  display: flex;
  align-items: center;
  gap: 6px;
  box-shadow: var(--shadow-md);
  z-index: 10;
  animation: slideIn 0.3s ease;
}

@keyframes slideIn {
  from {
    transform: translateX(100%);
    opacity: 0;
  }
  to {
    transform: translateX(0);
    opacity: 1;
  }
}

/* 响应式设计 */
@media (max-width: 768px) {
  .panel-header {
    padding: 10px 12px;
  }

  .tab-button {
    padding: 10px 12px;
    font-size: 12px;
  }

  .content-section {
    padding: 12px;
  }

  .code-block {
    font-size: 12px;
  }

  .code-block code {
    padding: 12px;
  }
}

/* 深色主题适配 */
@media (prefers-color-scheme: dark) {
  .code-block {
    background: #2d3748;
    color: #e2e8f0;
  }

  .code-block code {
    color: #e2e8f0;
  }
}
</style>