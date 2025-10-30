<template>
  <div class="sql-code-container">
    <div class="component-header">
      <div class="title">
        <i class="bi bi-code-slash"></i>
        SQL Code
      </div>
      <div class="actions">
        <button class="btn-icon" @click="copyToClipboard" :disabled="!sqlCode">
          <i class="bi" :class="copied ? 'bi-check' : 'bi-clipboard'"></i>
        </button>
        <button class="btn-icon" @click="toggleFullscreen">
          <i class="bi bi-arrows-fullscreen"></i>
        </button>
      </div>
    </div>
    <div class="sql-code-content" :class="{ 'fullscreen': isFullscreen }">
      <div class="code-header">
        <div class="badge postgres">
          <i class="bi bi-database"></i>
          PostgreSQL
        </div>
        <div class="line-info">
          {{ sqlCode ? `${lineCount} lines` : 'No code' }}
        </div>
      </div>
      <div class="code-editor" v-if="sqlCode">
        <pre><code class="language-sql">{{ sqlCode }}</code></pre>
      </div>
      <div class="empty-state" v-else>
        <i class="bi bi-code"></i>
        <p>No SQL code generated yet</p>
        <small>Execute feature generation to see PostgreSQL code</small>
      </div>
    </div>
    <!-- Fullscreen overlay -->
    <div class="fullscreen-overlay" v-if="isFullscreen" @click="toggleFullscreen">
      <div class="fullscreen-content" @click.stop>
        <div class="fullscreen-header">
          <h5><i class="bi bi-code-slash"></i> SQL Code</h5>
          <button class="btn-close" @click="toggleFullscreen">
            <i class="bi bi-x"></i>
          </button>
        </div>
        <div class="fullscreen-body">
          <pre><code class="language-sql">{{ sqlCode }}</code></pre>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'

const props = defineProps<{
  sqlCode?: string
}>()

const isFullscreen = ref(false)
const copied = ref(false)

const lineCount = computed(() => {
  if (!props.sqlCode) return 0
  return props.sqlCode.split('\n').length
})

const copyToClipboard = async () => {
  if (!props.sqlCode) return

  try {
    await navigator.clipboard.writeText(props.sqlCode)
    copied.value = true
    setTimeout(() => {
      copied.value = false
    }, 2000)
  } catch (err) {
    console.error('Failed to copy SQL code:', err)
  }
}

const toggleFullscreen = () => {
  isFullscreen.value = !isFullscreen.value
}
</script>

<style scoped>
.sql-code-container {
  background: var(--bg-primary);
  border-radius: 12px;
  box-shadow: var(--shadow-sm);
  border: 1px solid var(--border-color);
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
}

.component-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--spacing-md) var(--spacing-lg);
  border-bottom: 1px solid var(--border-color);
  background: var(--bg-secondary);
}

.title {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  font-weight: 600;
  color: var(--text-primary);
  font-size: var(--font-size-md);
}

.actions {
  display: flex;
  gap: 4px;
}

.btn-icon {
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

.btn-icon:hover:not(:disabled) {
  background: var(--bg-primary);
  color: var(--primary-color);
}

.btn-icon:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.sql-code-content {
  flex: 1;
  padding: var(--spacing-lg);
  overflow-y: auto;
  min-height: 0;
}

.code-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.badge.postgres {
  background: linear-gradient(135deg, #336791, #4179A8);
  color: white;
  padding: 4px 8px;
  border-radius: 12px;
  font-size: 11px;
  font-weight: 500;
  display: flex;
  align-items: center;
  gap: 4px;
}

.line-info {
  font-size: var(--font-size-xs);
  color: var(--text-secondary);
  font-family: var(--font-mono);
}

.code-editor {
  background: #1e1e1e;
  border-radius: 8px;
  overflow: hidden;
  border: 1px solid var(--border-color);
}

.code-editor pre {
  margin: 0;
  padding: var(--spacing-lg);
  overflow-x: auto;
}

.code-editor code {
  color: #d4d4d4;
  font-family: var(--font-mono);
  font-size: 20px;
  line-height: 1.6;
  white-space: pre-wrap;
  word-wrap: break-word;
}

.empty-state {
  text-align: center;
  padding: 40px 20px;
  color: var(--text-secondary);
}

.empty-state i {
  font-size: 48px;
  color: var(--text-placeholder);
  margin-bottom: 16px;
  display: block;
}

.empty-state p {
  margin: 8px 0 4px 0;
  font-weight: 500;
}

.empty-state small {
  font-size: 12px;
  opacity: 0.7;
}

/* Fullscreen styles */
.sql-code-content.fullscreen {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 1000;
  background: var(--bg-white);
  padding: 0;
}

.fullscreen-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.8);
  z-index: 1000;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
}

.fullscreen-content {
  background: var(--bg-white);
  border-radius: 12px;
  width: 100%;
  max-width: 1200px;
  max-height: 90vh;
  display: flex;
  flex-direction: column;
  box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.25);
}

.fullscreen-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px;
  border-bottom: 1px solid var(--border-color);
}

.fullscreen-header h5 {
  margin: 0;
  color: var(--text-primary);
  font-size: 18px;
  font-weight: 600;
}

.btn-close {
  background: none;
  border: none;
  padding: 8px;
  border-radius: 6px;
  cursor: pointer;
  color: var(--text-secondary);
  font-size: 18px;
}

.btn-close:hover {
  background: var(--bg-light);
  color: var(--text-primary);
}

.fullscreen-body {
  flex: 1;
  padding: 20px;
  overflow-y: auto;
  background: #1e1e1e;
}

.fullscreen-body pre {
  margin: 0;
  color: #d4d4d4;
  font-family: var(--font-mono);
  font-size: 22px;
  line-height: 1.5;
  white-space: pre-wrap;
  word-wrap: break-word;
}

/* SQL Syntax highlighting (basic) */
.code-editor code .keyword {
  color: #569cd6;
  font-weight: 500;
}

.code-editor code .string {
  color: #ce9178;
}

.code-editor code .function {
  color: #dcdcaa;
}

.code-editor code .comment {
  color: #6a9955;
  font-style: italic;
}

.code-editor code .number {
  color: #b5cea8;
}

/* Responsive */
@media (max-width: 768px) {
  .component-header {
    padding: 10px 12px;
  }

  .title {
    font-size: 13px;
  }

  .sql-code-content {
    padding: 12px;
  }

  .fullscreen-content {
    margin: 10px;
    max-height: calc(100vh - 20px);
  }
}
</style>