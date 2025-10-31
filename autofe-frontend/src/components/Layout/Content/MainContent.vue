<template>
  <div class="main-content" :class="{ 'splitter-collapsed': rightPanelCollapsed }">
    <!-- 使用Splitpanes实现左右分区布局 -->
    <splitpanes class="default-theme" @resize="handleResize" :push-other-panes="false">
      <!-- 左侧面板：Agent流程图（上方） + Node Information（下方） -->
      <pane :size="leftPaneSize" min="15" max="70">
        <div class="left-panel">
          <!-- 上方：Agent协作流程图 -->
          <div class="agent-flow-section">
            <div class="info-card">
              <div class="info-header">
                <h6 class="info-title">
                  <Users :size="18" class="me-2" />
                  Agent Thinking Process
                  <button
                    class="btn btn-sm btn-info ms-2"
                    @click="testAgentStatus"
                    style="font-size: 0.75rem; padding: 0.25rem 0.5rem;"
                  >
                    Test
                  </button>
                </h6>
              </div>
              <div class="info-content">
                <div class="agent-flow-diagram">
              <!-- 环形布局的Agent协作图 -->
              <div class="flow-container">
                <!-- Agent图标正方形布局 -->
                <div class="agents-container">
                  <!-- System Agent (左上角) -->
                  <div
                    class="agent-node system-agent"
                    :class="{ active: activeAgent === 'system', working: workingAgents.includes('system') }"
                    @click="setActiveAgent('system')"
                  >
                    <div class="agent-icon">
                      <Monitor :size="32" />
                    </div>
                    <div class="agent-label">System</div>
                    <div v-if="workingAgents.includes('system')" class="working-indicator"></div>

                    <!-- System Agent思考气泡 -->
                    <div v-if="getAgentThinking('system')" class="thinking-bubble left-bubble">
                      <pre>{{ getAgentThinking('system') }}</pre>
                    </div>
                  </div>

                  <!-- Main Agent (右上角) -->
                  <div
                    class="agent-node main-agent"
                    :class="{ active: activeAgent === 'main', working: workingAgents.includes('main') }"
                    @click="setActiveAgent('main')"
                  >
                    <div class="agent-icon">
                      <img src="/demo_main.png" alt="Main Agent" class="agent-image" />
                    </div>
                    <div class="agent-label">Main Agent</div>
                    <div v-if="workingAgents.includes('main')" class="working-indicator"></div>

                    <!-- Main Agent思考气泡 -->
                    <div v-if="getAgentThinking('main')" class="thinking-bubble right-bubble">
                      <pre>{{ getAgentThinking('main') }}</pre>
                    </div>
                  </div>

                  <!-- Optimization Agent (右下角) -->
                  <div
                    class="agent-node opt-agent"
                    :class="{ active: activeAgent === 'optimization', working: workingAgents.includes('optimization') }"
                    @click="setActiveAgent('optimization')"
                  >
                    <div class="agent-icon">
                      <img src="/demo_opt.png" alt="Optimization Agent" class="agent-image" />
                    </div>
                    <div class="agent-label">Opt Agent</div>
                    <div v-if="workingAgents.includes('optimization')" class="working-indicator"></div>

                    <!-- Optimization Agent思考气泡 -->
                    <div v-if="getAgentThinking('optimization')" class="thinking-bubble right-bubble">
                      <pre>{{ getAgentThinking('optimization') }}</pre>
                    </div>
                  </div>

                  <!-- Node Validation Process (左下角) -->
                  <div
                    class="agent-node validation-agent"
                    :class="{ active: activeAgent === 'validation', working: workingAgents.includes('validation') }"
                    @click="setActiveAgent('validation')"
                  >
                    <div class="agent-icon">
                      <Cog :size="32" />
                    </div>
                    <div class="agent-label">Node Validation</div>
                    <div v-if="workingAgents.includes('validation')" class="working-indicator"></div>

                    <!-- Node Validation Agent思考气泡 -->
                    <div v-if="getAgentThinking('validation')" class="thinking-bubble left-bubble">
                      <pre>{{ getAgentThinking('validation') }}</pre>
                    </div>
                  </div>

                  <!-- CSS箭头 - 相对中心定位，在同一容器内 -->
                  <div class="arrow-horizontal top-arrow" :class="{ active: connectionActive }"></div>
                  <div class="arrow-vertical right-arrow" :class="{ active: connectionActiveReverse }"></div>
                  <div class="arrow-horizontal bottom-arrow" :class="{ active: connectionActiveValidation }"></div>
                  <div class="arrow-vertical left-arrow" :class="{ active: connectionActiveSystem }"></div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

          <!-- 下方：左右分列的Node Information和Feature Generation -->
          <div class="lower-section">
            <!-- 左边：Node Information -->
            <div class="node-info-section">
              <div class="info-card">
                <div class="info-header">
                  <h6 class="info-title">Node Information</h6>
                </div>
                <div class="info-content">
                  <div v-if="featureTreeStore.selectedNode" class="node-details">
                    <div class="node-detail">
                      <span class="detail-label">Node ID:</span>
                      <span class="detail-value">{{ featureTreeStore.selectedNode.node_id }}</span>
                    </div>
                    <div class="node-detail">
                      <span class="detail-label">Feature Name:</span>
                      <span class="detail-value">{{ featureTreeStore.selectedNode.feature_name }}</span>
                    </div>
                    <div class="node-detail">
                      <span class="detail-label">Task Code:</span>
                      <span class="detail-value">{{ featureTreeStore.selectedNode.task_code }}</span>
                    </div>
                    <div class="node-detail">
                      <span class="detail-label">Operation:</span>
                      <span class="detail-value">{{ featureTreeStore.selectedNode.op_type }}</span>
                    </div>
                    <div class="node-detail">
                      <span class="detail-label">Description:</span>
                      <span class="detail-value">{{ featureTreeStore.selectedNode.operation_desc }}</span>
                    </div>
                    <div class="node-detail">
                      <span class="detail-label">Score:</span>
                      <span class="detail-value">{{ featureTreeStore.selectedNode.score?.toFixed(4) }}</span>
                    </div>
                  </div>
                  <div v-else class="no-node-info">
                    Hover over a node to see details.
                  </div>
                </div>
              </div>
            </div>

            <!-- 右边：Feature Generation -->
            <div class="feature-tree-section">
              <FeatureTreePanel />
            </div>
          </div>
        </div>
      </pane>


      <!-- 右侧面板：SQL Code组件（上方） + Feature Performance组件（下方） -->
      <pane :size="rightPaneSize" min="20" max="60" v-if="!rightPanelCollapsed">
        <div class="right-panel-content">
          <!-- 上方：SQL Code组件 -->
          <div class="sql-code-section">
            <SQLCode :sql-code="sqlCode" />
          </div>

  
          <!-- 下方：Feature Performance组件 -->
          <div class="feature-performance-section">
            <FeaturePerformance
              :performance-data="performanceData"
              :time-data="timeData"
              :shap-data="shapData"
              :is-loading="isLoadingPerformance"
              @generate-features="handleGenerateFeatures"
              @refresh-data="handleRefreshData"
            />
          </div>
        </div>
      </pane>

      <!-- 折叠按钮（当右侧面板隐藏时显示） -->
      <div v-if="rightPanelCollapsed" class="expand-button-container" @click="toggleRightPanel">
        <div class="expand-button">
          <span class="expand-arrow">‹</span>
          <span class="expand-tooltip">Expand Panel (Ctrl+→)</span>
        </div>
      </div>
    </splitpanes>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, nextTick, watch } from 'vue'
import { Users, Cog, Monitor, Bot } from 'lucide-vue-next'
import { useTaskStore } from '@/stores/task'
import { useFeatureTreeStore } from '@/stores/featureTree'
import { useAgentStore } from '@/stores/agent'
import type { AgentType, AgentState } from '@/types/websocket'
import SQLCode from '@/components/Features/SQLCode.vue'
import FeaturePerformance from '@/components/Features/FeaturePerformance.vue'
import FeatureTreePanel from '@/components/Features/FeatureTreePanel.vue'

const taskStore = useTaskStore()
const featureTreeStore = useFeatureTreeStore()
const agentStore = useAgentStore()

const activeAgent = ref<'system' | 'main' | 'optimization' | 'validation'>('main')
const workingAgents = ref<string[]>([])
const connectionActive = ref(false)
const connectionActiveReverse = ref(false)
const connectionActiveValidation = ref(false)
const connectionActiveSystem = ref(false)

// 右侧面板数据
const sqlCode = ref('')
const performanceData = ref<any>(null)
const timeData = ref<any>(null)
const shapData = ref<any>(null)
const isLoadingPerformance = ref(false)

// Splitpanes 相关状态
const leftPaneSize = ref(75) // 左侧面板默认占75%
const rightPaneSize = ref(25) // 右侧面板默认占25%（留空）
const rightPanelCollapsed = ref(false) // 右侧面板折叠状态

// 处理分隔条拖动
function handleResize(event: any) {
  console.log('Resize event:', event)
  // splitpanes 的事件参数可能是单个对象或数组
  if (Array.isArray(event)) {
    const [leftPane] = event
    leftPaneSize.value = leftPane.size
    rightPaneSize.value = 100 - leftPane.size
    localStorage.setItem('main-content-split-ratio', leftPane.size.toString())
  } else if (event && event[0]) {
    // 如果event是类数组对象
    const leftPane = event[0]
    leftPaneSize.value = leftPane.size
    rightPaneSize.value = 100 - leftPane.size
    localStorage.setItem('main-content-split-ratio', leftPane.size.toString())
  } else if (event && event.size !== undefined) {
    // 如果event直接包含size信息
    leftPaneSize.value = event.size
    rightPaneSize.value = 100 - event.size
    localStorage.setItem('main-content-split-ratio', event.size.toString())
  }
}


// 切换右侧面板折叠状态
function toggleRightPanel() {
  console.log('toggleRightPanel called, current collapsed state:', rightPanelCollapsed.value)
  rightPanelCollapsed.value = !rightPanelCollapsed.value

  if (rightPanelCollapsed.value) {
    // 折叠右侧面板，左侧占满
    console.log('Collapsing right panel')
    leftPaneSize.value = 100
    rightPaneSize.value = 0
  } else {
    // 展开右侧面板，恢复之前比例
    console.log('Expanding right panel')
    const savedRatio = localStorage.getItem('main-content-split-ratio')
    if (savedRatio) {
      leftPaneSize.value = parseFloat(savedRatio)
      rightPaneSize.value = 100 - leftPaneSize.value
    } else {
      leftPaneSize.value = 75
      rightPaneSize.value = 25
    }
  }

  // 保存折叠状态
  localStorage.setItem('right-panel-collapsed', rightPanelCollapsed.value.toString())
  console.log('New sizes - left:', leftPaneSize.value, 'right:', rightPaneSize.value)
}


// Agent interaction
function setActiveAgent(agent: 'system' | 'main' | 'optimization' | 'validation') {
  activeAgent.value = agent
  taskStore.addNotification(`Selected ${agent} agent`, 'info')
}

// WebSocket相关
const currentThinkingText = computed(() => {
  // 映射activeAgent到agent store中的agent类型
  const agentTypeMap: Record<string, AgentType> = {
    'system': 'system',
    'main': 'mainagent',
    'optimization': 'optimizationagent',
    'validation': 'nodevalidator'
  }

  const agentType = agentTypeMap[activeAgent.value]
  if (agentType) {
    const thinking = agentStore.getLatestThinking(agentType)
    return thinking
  }
  return ''
})

// 获取特定Agent的思考内容
function getAgentThinking(agent: 'system' | 'main' | 'optimization' | 'validation'): string {
  const agentTypeMap: Record<string, AgentType> = {
    'system': 'system',
    'main': 'mainagent',
    'optimization': 'optimizationagent',
    'validation': 'nodevalidator'
  }

  const agentType = agentTypeMap[agent]
  if (agentType) {
    const thinking = agentStore.getLatestThinking(agentType)
    console.log(`getAgentThinking called for ${agent} (${agentType}):`, thinking)
    return thinking
  }
  console.log(`No agent type found for ${agent}`)
  return ''
}

// 测试Agent状态
function testAgentStatus() {
  console.log('Test Agent Status clicked!')

  // 映射到正确的agent类型
  const agentTypeMap: Record<string, AgentType> = {
    'system': 'system',
    'main': 'mainagent',
    'optimization': 'optimizationagent',
    'validation': 'nodevalidator'
  }

  const agentType = agentTypeMap[activeAgent.value]
  if (agentType) {
    console.log('Testing agent:', agentType)

    // 测试 thinking 消息
    agentStore.updateAgentThinking({
      type: 'agent_thinking',
      agent: agentType,
      thinking: `这是一个测试思考消息：${activeAgent.value} Agent正在分析数据集特征，准备生成新的特征组合...`,
      category: 'analysis',
      timestamp: Date.now()
    })

    // 也更新状态
    agentStore.updateAgentState({
      type: 'agent_status',
      agent: agentType,
      status: 'working',
      work_type: '特征工程测试',
      details: { phase: 'testing', progress: 75 },
      timestamp: Date.now()
    })

    taskStore.addNotification(`Test ${activeAgent.value} Agent状态已发送`, 'info')
    console.log('Test status sent successfully')
  }
}

// 模拟agent工作状态（保持原有逻辑）
function simulateAgentWork() {
  if (taskStore.status === 'running') {
    workingAgents.value = ['system']
    connectionActive.value = true

    setTimeout(() => {
      workingAgents.value = ['main']
      connectionActive.value = false
      connectionActiveReverse.value = true

      setTimeout(() => {
        workingAgents.value = ['optimization']
        connectionActiveReverse.value = false
        connectionActiveValidation.value = true

        setTimeout(() => {
          workingAgents.value = ['validation']
          connectionActiveValidation.value = false
          connectionActiveSystem.value = true

          setTimeout(() => {
            workingAgents.value = []
            connectionActiveSystem.value = false
          }, 2000)
        }, 2000)
      }, 2000)
    }, 2000)
  }
}

// 监听任务状态变化
watch(() => taskStore.status, (newStatus) => {
  if (newStatus === 'running') {
    simulateAgentWork()
  } else {
    workingAgents.value = []
    connectionActive.value = false
    connectionActiveReverse.value = false
    connectionActiveValidation.value = false
    connectionActiveSystem.value = false
  }
})

// 监听任务初始化状态变化
watch(() => taskStore.isInitialized, (isInitialized) => {
  if (isInitialized) {
    // 当任务初始化后，加载特征树数据
    featureTreeStore.loadTreeData()
  }
})

// 监听Agent状态变化，更新工作状态
watch(() => agentStore.allAgentStates, (states) => {
  const agentTypeMap: Record<string, string> = {
    'system': 'system',
    'mainagent': 'main',
    'optimizationagent': 'optimization',
    'nodevalidator': 'validation'
  }

  const newWorkingAgents: string[] = []

  states.forEach((state: AgentState) => {
    const shortName = agentTypeMap[state.agent]
    if (shortName && state.status === 'working') {
      newWorkingAgents.push(shortName)
    }
  })

  workingAgents.value = newWorkingAgents

  // 更新连接状态
  const hasMainAgent = states.some((s: AgentState) => s.agent === 'mainagent' && s.status === 'working')
  const hasOptAgent = states.some((s: AgentState) => s.agent === 'optimizationagent' && s.status === 'working')
  const hasValidationAgent = states.some((s: AgentState) => s.agent === 'nodevalidator' && s.status === 'working')
  const hasSystemAgent = states.some((s: AgentState) => s.agent === 'system' && s.status === 'working')

  connectionActive.value = hasMainAgent || hasSystemAgent
  connectionActiveReverse.value = hasOptAgent
  connectionActiveValidation.value = hasValidationAgent
  connectionActiveSystem.value = hasSystemAgent
}, { deep: true })

// 键盘快捷键处理
const handleKeyDown = (event: KeyboardEvent) => {
  // Ctrl + → 或 Ctrl + ← 切换右侧面板
  if (event.ctrlKey && (event.key === 'ArrowRight' || event.key === 'ArrowLeft')) {
    event.preventDefault()
    toggleRightPanel()
  }
  // Esc 键也可以折叠右侧面板
  if (event.key === 'Escape' && !rightPanelCollapsed.value) {
    toggleRightPanel()
  }
}

onMounted(() => {
  // 从localStorage加载用户偏好
  const savedRatio = localStorage.getItem('main-content-split-ratio')
  const savedCollapsed = localStorage.getItem('right-panel-collapsed')

  if (savedRatio) {
    leftPaneSize.value = parseFloat(savedRatio)
    rightPaneSize.value = 100 - leftPaneSize.value
  }

  if (savedCollapsed) {
    rightPanelCollapsed.value = savedCollapsed === 'true'
    if (rightPanelCollapsed.value) {
      leftPaneSize.value = 100
      rightPaneSize.value = 0
    }
  }

  // 初始化WebSocket连接
  agentStore.initializeWebSocket()

  // 添加键盘事件监听器
  window.addEventListener('keydown', handleKeyDown)

  // 添加性能测试事件监听器
  window.addEventListener('test-performance', handleTestPerformanceEvent as EventListener)

  // 添加splitter点击事件监听器
  nextTick(() => {
    const splitters = document.querySelectorAll('.splitpanes__splitter')
    splitters.forEach((splitter) => {
      splitter.addEventListener('click', (event: Event) => {
        event.preventDefault()
        event.stopPropagation()
        toggleRightPanel()
      })

      splitter.addEventListener('mousedown', (event: Event) => {
        const mouseEvent = event as MouseEvent
        const splitterElement = mouseEvent.target as HTMLElement
        const rect = splitterElement.getBoundingClientRect()
        const centerY = rect.top + rect.height / 2
        const clickY = mouseEvent.clientY

        // 如果点击在中央区域（上下各20px范围内），阻止拖拽
        if (Math.abs(clickY - centerY) < 20) {
          mouseEvent.preventDefault()
          mouseEvent.stopPropagation()
        }
      })
    })
  })
})

onUnmounted(() => {
  // 移除事件监听器
  window.removeEventListener('keydown', handleKeyDown)
  window.removeEventListener('test-performance', handleTestPerformanceEvent as EventListener)
})

// 处理性能测试事件
function handleTestPerformanceEvent(event: CustomEvent) {
  const { features } = event.detail

  // 确保右侧面板展开
  if (rightPanelCollapsed.value) {
    toggleRightPanel()
  }

  // 调用性能测试函数，传递选中的节点ID
  testPerformance(features)
}

// 右侧面板组件事件处理
async function handleGenerateFeatures() {
  // 处理测试性能请求，使用当前选中的节点ID
  await testPerformance(featureTreeStore.selectedNodeIds)
}

async function testPerformance(selectedNodeIds?: string[]) {
  if (isLoadingPerformance.value) {
    taskStore.addNotification('Performance test already in progress...', 'info')
    return
  }

  // 确定要使用的节点ID
  const nodeIds = selectedNodeIds || featureTreeStore.selectedNodeIds

  if (!nodeIds || nodeIds.length === 0) {
    taskStore.addNotification('Please select at least one feature to test performance', 'info')
    return
  }

  isLoadingPerformance.value = true
  taskStore.addNotification('Testing performance...', 'info')

  try {
    const response = await fetch('/test-performance/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        selectedNodeIds: nodeIds
      })
    })

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`)
    }

    const data = await response.json()

    if (data.status === 'success') {
      // 更新SQL代码（显示all_sql）
      if (data.sql_code && data.sql_code.all_sql) {
        sqlCode.value = data.sql_code.all_sql
      }

      // 更新性能数据
      if (data.performance_info) {
        const perf = data.performance_info

        // 转换性能数据格式
        performanceData.value = {
          accuracy: perf.accuracy || 0,
          precision: perf.precision || 0,
          recall: perf.recall || 0,
          f1Score: perf.f1_score || perf.f1Score || 0,
          auc: perf.auc || 0
        }

        // 转换时间数据（如果存在）
        timeData.value = {
          total: perf.total_time || perf.time_usage || 0,
          generation: perf.generation_time || 0,
          evaluation: perf.evaluation_time || 0,
          selection: perf.selection_time || 0
        }

        // 转换SHAP数据（如果存在）
        if (perf.shap_values && perf.shap_values.length > 0) {
          shapData.value = {
            meanShap: perf.mean_shap || 0,
            features: perf.shap_values.map((shap: any, index: number) => ({
              name: shap.feature_name || `feature_${index}`,
              value: shap.shap_value || shap.value || 0,
              percentage: Math.max(1, (shap.importance || shap.percentage || 1))
            })).sort((a: any, b: any) => b.value - a.value).slice(0, 5)
          }
        }
      }

      taskStore.addNotification('Performance test completed successfully!', 'success')
    } else {
      throw new Error(data.message || 'Performance test failed')
    }
  } catch (error) {
    console.error('Error testing performance:', error)
    taskStore.addNotification(`Error: ${error instanceof Error ? error.message : 'Unknown error'}`, 'fail')
  } finally {
    isLoadingPerformance.value = false
  }
}

function handleRefreshData() {
  // 处理刷新数据请求，重新调用测试性能API
  testPerformance()
}
</script>

<style scoped>
.main-content {
  display: flex;
  flex: 1;
  flex-direction: column;
  padding: var(--spacing-lg);
  overflow: hidden;
  background-color: var(--bg-primary);
  height: 100%;
}

/* 左侧面板布局 */
.left-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  gap: 0;
  padding-right: 1rem;
}

.agent-flow-section {
  flex: 1;
  min-height: 200px;
  display: flex;
  flex-direction: column;
  padding-bottom: 0.375rem;
}

.agent-flow-section .info-card {
  flex: 1;
}

/* 下方左右分列布局 */
.lower-section {
  display: flex;
  gap: 1.5rem;
  flex: 1;
  min-height: 200px;
  padding-top: 0.375rem;
}

.node-info-section {
  flex: 1;
  min-width: 200px;
  display: flex;
  flex-direction: column;
}

.feature-tree-section {
  flex: 1;
  min-width: 250px;
  display: flex;
  flex-direction: column;
}

/* 右侧面板布局 */
.right-panel-content {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  gap: 0;
  background-color: #ffffff;
  padding-left: 1rem;
}

.sql-code-section {
  flex: 1;
  min-height: 200px;
  display: flex;
  flex-direction: column;
  padding-bottom: 0.375rem;
}

.feature-performance-section {
  flex: 1;
  min-height: 200px;
  display: flex;
  flex-direction: column;
  padding-top: 0.375rem;
}


/* 展开按钮样式 */
.expand-button {
  position: absolute;
  right: 0;
  top: 50%;
  transform: translateY(-50%);
  background-color: #007bff;
  color: white;
  border: none;
  border-radius: 4px 0 0 4px;
  padding: 0.5rem;
  cursor: pointer;
  z-index: 1000;
  transition: all 0.3s ease;
}

.expand-button:hover {
  background-color: #0056b3;
  padding-left: 1rem;
}

/* Splitpanes 自定义样式 */
:deep(.splitpanes.default-theme .splitpanes__splitter) {
  background-color: transparent !important;
  border: none !important;
  position: relative;
  width: 12px !important;
  cursor: col-resize !important;
  transition: all 0.3s ease !important;
}

:deep(.splitpanes.default-theme .splitpanes__splitter:hover) {
  background-color: transparent !important;
}

/* 在splitter中添加可点击的折叠区域 */
:deep(.splitpanes.default-theme .splitpanes__splitter)::after {
  content: '';
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  width: 40px;
  height: 60px;
  background-color: transparent;
  cursor: default;
  transition: all 0.3s ease;
  z-index: 1;
  border-radius: 4px;
  pointer-events: none;
}

:deep(.splitpanes.default-theme .splitpanes__splitter:hover)::after {
  background-color: transparent;
}

/* 添加箭头 */
:deep(.splitpanes.default-theme .splitpanes__splitter)::before {
  content: '';
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  color: transparent;
  font-size: 0;
  font-weight: bold;
  transition: all 0.3s ease;
  z-index: 11;
  pointer-events: none;
  width: 0;
  height: 0;
  overflow: hidden;
}

:deep(.splitpanes.default-theme .splitpanes__splitter:hover)::before {
  color: transparent;
}

/* 当面板折叠时的箭头方向 - 使用数据属性 */
.splitter-collapsed :deep(.splitpanes.default-theme .splitpanes__splitter)::before {
  content: '';
  color: transparent;
  width: 0;
  height: 0;
  overflow: hidden;
}

:deep(.splitpanes.default-theme .splitpanes__pane) {
  background-color: transparent;
  overflow: hidden;
}

/* 响应式布局 */
@media (max-width: 1200px) {
  .left-panel,
  .right-panel {
    min-height: auto;
  }

  .agent-flow-section {
    min-height: 150px;
  }

  .enhanced-feature-tree-section {
    min-height: 250px;
  }

  .node-info-section {
    min-height: 120px;
  }
}

/* 通用样式 */
.section-header {
  margin-bottom: 0.75rem;
  padding-bottom: 0.5rem;
  border-bottom: 2px solid #e9ecef;
}

.section-title {
  color: var(--text-primary);
  font-weight: 600;
  margin: 0;
  display: flex;
  align-items: center;
  font-size: var(--font-size-xl);
}

.info-card {
  height: 100%;
  background-color: var(--bg-secondary);
  border-radius: 8px;
  border: 1px solid var(--border-color);
  display: flex;
  flex-direction: column;
  box-shadow: var(--shadow-sm);
}

.info-header {
  padding: var(--spacing-md) var(--spacing-lg);
  border-bottom: 1px solid var(--border-color);
  background-color: var(--bg-primary);
  border-radius: 8px 8px 0 0;
}

.info-title {
  color: var(--text-primary);
  font-weight: 600;
  margin: 0;
  font-size: var(--font-size-md);
}

.info-content {
  flex: 1;
  padding: 1rem;
  overflow-y: auto;
}

/* Agent Flow Diagram - 移除背景和边框，让组件自身样式生效 */
.agent-flow-diagram {
  flex: 1;
  position: relative;
  min-height: 350px; /* 增加最小高度以容纳所有节点 */
}

.flow-container {
  position: relative;
  width: 100%;
  height: 100%;
  /* 移除flex布局，使用绝对定位布局 */
}


.agents-container {
  position: relative;
  width: 100%;
  height: 100%;
  min-height: 400px; /* 确保有足够的高度 */
}

.agent-node {
  position: absolute;
  width: 90px;
  text-align: center;
  cursor: pointer;
  transition: all 0.3s ease;
  z-index: 2; /* 确保节点在连接线上方 */
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
}


/* 正方形布局 - 四个节点相对于容器中心的位置，考虑元素宽度 */
.system-agent {
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%) translate(-135px, -135px);
}

.main-agent {
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%) translate(135px, -135px);
}

.opt-agent {
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%) translate(135px, 135px);
}

.validation-agent {
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%) translate(-135px, 135px);
}

.agent-icon {
  width: 70px;
  height: 70px;
  background-color: transparent;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto;
  border: 3px solid transparent;
  transition: all 0.3s ease;
  color: #6c757d;
}

.agent-image {
  width: 100%;
  height: 100%;
  object-fit: contain;
  border-radius: 4px;
}

.agent-node.active .agent-icon {
  background-color: #007bff;
  color: white;
  border-color: #0056b3;
}

.agent-node.working .agent-icon {
  background-color: #28a745;
  color: white;
  animation: breathe 2s ease-in-out infinite;
}

.agent-label {
  font-weight: 600;
  font-size: var(--font-size-md);
  color: var(--text-primary);
  position: absolute;
  bottom: -25px;
  left: 50%;
  transform: translateX(-50%);
  text-align: center;
  white-space: nowrap;
}

.working-indicator {
  position: absolute;
  top: -5px;
  right: -5px;
  width: 12px;
  height: 12px;
  background-color: #ffc107;
  border-radius: 50%;
  animation: pulse 1.5s ease-in-out infinite;
}

.connection-lines {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
  width: 500px;
  height: 500px;
  left: 50%;
  top: 50%;
  transform: translate(-50%, -50%);
  z-index: 0; /* 确保连接线在节点下方 */
}

.connection-line {
  fill: none;
  stroke: #dee2e6;
  stroke-width: 4;
  stroke-dasharray: 5, 5;
  transition: all 0.3s ease;
}

.connection-line.curved {
  stroke-width: 4;
  fill: none;
}

.connection-line.active {
  stroke: #007bff;
  stroke-dasharray: none;
  animation: flow 2s ease-in-out;
}

.connection-line.curved.active {
  stroke: #007bff;
}

/* 节点信息 */
.node-details {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.node-detail {
  display: flex;
  align-items: flex-start;
  gap: 0.5rem;
}

.detail-label {
  font-weight: 600;
  color: var(--text-primary);
  min-width: 80px;
  flex-shrink: 0;
  font-size: var(--font-size-sm);
}

.detail-value {
  color: var(--text-secondary);
  word-break: break-word;
  flex: 1;
  font-size: var(--font-size-sm);
}

.no-node-info {
  color: #6c757d;
  font-style: italic;
  text-align: center;
  padding: 2rem 0;
  font-size: 14px;
}

/* 动画 */
@keyframes breathe {
  0%, 100% {
    box-shadow: 0 0 0 0 rgba(40, 167, 69, 0.7);
  }
  50% {
    box-shadow: 0 0 0 10px rgba(40, 167, 69, 0);
  }
}

@keyframes pulse {
  0%, 100% {
    opacity: 1;
  }
  50% {
    opacity: 0.5;
  }
}

@keyframes flow {
  0% {
    stroke-dashoffset: 10;
  }
  100% {
    stroke-dashoffset: 0;
  }
}

/* 展开按钮容器样式 */
.expand-button-container {
  position: absolute;
  right: 0;
  top: 50%;
  transform: translateY(-50%);
  z-index: 1000;
  cursor: pointer;
}

.expand-button {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  background-color: #6c757d;
  color: white;
  border: none;
  border-radius: 4px 0 0 4px;
  padding: 0.75rem 1rem;
  box-shadow: -2px 0 8px rgba(0, 0, 0, 0.1);
  transition: all 0.3s ease;
  white-space: nowrap;
}

.expand-button:hover {
  background-color: #495057;
  transform: translateY(-50%) translateX(-4px);
  box-shadow: -4px 0 12px rgba(0, 0, 0, 0.15);
}

.expand-arrow {
  font-size: 20px;
  font-weight: bold;
  margin-right: 0.5rem;
}

.expand-tooltip {
  font-size: 1rem;
  font-weight: 500;
}

/* CSS箭头直接在agents-container内，无需额外容器 */

/* 水平箭头基础样式 */
.arrow-horizontal {
  position: absolute;
  top: 50%;
  left: 50%;
  width: 130px;
  height: 4px;
  background-color: #dee2e6;
  transition: all 0.3s ease;
}

.arrow-horizontal::after {
  content: '';
  position: absolute;
  right: -8px;
  top: 50%;
  transform: translateY(-50%);
  width: 0;
  height: 0;
  border-left: 12px solid #dee2e6;
  border-top: 8px solid transparent;
  border-bottom: 8px solid transparent;
}

/* 垂直箭头基础样式 */
.arrow-vertical {
  position: absolute;
  top: 50%;
  left: 50%;
  width: 4px;
  height: 130px;
  background-color: #dee2e6;
  transition: all 0.3s ease;
}

.arrow-vertical::after {
  content: '';
  position: absolute;
  bottom: -8px;
  left: 50%;
  transform: translateX(-50%);
  width: 0;
  height: 0;
  border-top: 12px solid #dee2e6;
  border-left: 8px solid transparent;
  border-right: 8px solid transparent;
}

/* 上横箭头位置 - 匹配新的节点位置 */
.top-arrow {
  transform: translate(-50%, -50%) translateY(-135px);
}

/* 右纵箭头位置 - 匹配新的节点位置 */
.right-arrow {
  transform: translate(-50%, -50%) translateX(135px);
}

/* 下横箭头位置和方向 - 匹配新的节点位置 */
.bottom-arrow {
  transform: translate(-50%, -50%) translateY(135px) rotate(180deg);
}

/* 左纵箭头位置和方向 - 匹配新的节点位置 */
.left-arrow {
  transform: translate(-50%, -50%) translateX(-135px) rotate(180deg);
}

/* 激活状态样式 */
.arrow-horizontal.active,
.arrow-vertical.active {
  background-color: #007bff;
}

.arrow-horizontal.active::after,
.arrow-vertical.active::after {
  border-left-color: #007bff;
  border-top-color: #007bff;
}

.bottom-arrow.active::after {
  border-left-color: #007bff;
}

.left-arrow.active::after {
  border-top-color: #007bff;
}

/* 响应式设计 */
@media (max-width: 1200px) {
  .upper-section {
    flex-direction: column;
  }

  .lower-section {
    flex-direction: column;
    height: auto;
  }

  .agent-flow-section,
  .feature-tree-section {
    min-width: auto;
  }
}

/* Agent思考气泡样式 */
.thinking-bubble {
  position: absolute;
  background: white;
  border: 2px solid #e3f2fd;
  border-radius: 12px;
  padding: 12px 16px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  color: #37474f;
  font-size: 0.8rem;
  line-height: 1.5;
  font-weight: 500;
  max-width: 400px;
  min-width: 200px;
  z-index: 100;
  animation: thinking-bubble-appear 0.3s ease-out;
}

.thinking-bubble pre {
  margin: 0;
  font-family: inherit;
  font-size: inherit;
  white-space: pre-wrap;
  word-wrap: break-word;
  color: inherit;
}

/* 左侧气泡 */
.left-bubble {
  right: calc(100% + 10px);
  top: 50%;
  transform: translateY(-50%);
}

.left-bubble::before {
  content: '';
  position: absolute;
  top: 50%;
  right: -8px;
  transform: translateY(-50%);
  width: 0;
  height: 0;
  border-top: 8px solid transparent;
  border-bottom: 8px solid transparent;
  border-left: 8px solid white;
  z-index: 101;
}

.left-bubble::after {
  content: '';
  position: absolute;
  top: 50%;
  right: -10px;
  transform: translateY(-50%);
  width: 0;
  height: 0;
  border-top: 9px solid transparent;
  border-bottom: 9px solid transparent;
  border-left: 9px solid #e3f2fd;
  z-index: 100;
}

/* 右侧气泡 */
.right-bubble {
  left: calc(100% + 10px);
  top: 50%;
  transform: translateY(-50%);
}

.right-bubble::before {
  content: '';
  position: absolute;
  top: 50%;
  left: -8px;
  transform: translateY(-50%);
  width: 0;
  height: 0;
  border-top: 8px solid transparent;
  border-bottom: 8px solid transparent;
  border-right: 8px solid white;
  z-index: 101;
}

.right-bubble::after {
  content: '';
  position: absolute;
  top: 50%;
  left: -10px;
  transform: translateY(-50%);
  width: 0;
  height: 0;
  border-top: 9px solid transparent;
  border-bottom: 9px solid transparent;
  border-right: 9px solid #e3f2fd;
  z-index: 100;
}

@keyframes thinking-bubble-appear {
  0% {
    opacity: 0;
    transform: translateY(-50%) scale(0.8);
  }
  100% {
    opacity: 1;
    transform: translateY(-50%) scale(1);
  }
}

/* Test按钮样式 */
.btn-info {
  background-color: #17a2b8 !important;
  color: white !important;
  font-weight: 500;
  border: none;
  border-radius: 0.25rem;
  transition: all 0.2s ease;
}

.btn-info:hover:not(:disabled) {
  background-color: #138496 !important;
  transform: translateY(-1px);
}

.btn-info:focus {
  outline: none;
  box-shadow: 0 0 0 2px rgba(23, 162, 184, 0.2);
}
</style>