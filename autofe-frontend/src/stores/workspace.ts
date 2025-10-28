import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useWorkspaceStore = defineStore('workspace', () => {
  // 状态
  const activePanel = ref<string>('TaskConfigPanel')
  const panelHistory = ref<string[]>(['TaskConfigPanel'])

  const availablePanels = [
    { id: 'TaskConfigPanel', name: '任务配置', icon: 'Settings' },
    { id: 'FeatureGenerationPanel', name: '特征生成', icon: 'GitBranch' },
    { id: 'AgentWorkflowPanel', name: 'Agent工作流', icon: 'Workflow' },
    { id: 'ExecutionLogsPanel', name: '执行日志', icon: 'ScrollText' }
  ]

  // 方法
  function switchPanel(panelId: string) {
    if (activePanel.value !== panelId) {
      panelHistory.value.push(activePanel.value)
      activePanel.value = panelId
    }
  }

  function goBack() {
    if (panelHistory.value.length > 1) {
      panelHistory.value.pop()
      activePanel.value = panelHistory.value[panelHistory.value.length - 1]
    }
  }

  return {
    // 状态
    activePanel,
    panelHistory,
    availablePanels,

    // 方法
    switchPanel,
    goBack
  }
})