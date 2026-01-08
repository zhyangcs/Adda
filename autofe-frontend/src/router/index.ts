import { createRouter, createWebHistory } from 'vue-router'
import MainContent from '@/components/Layout/Content/MainContent.vue'
import EndToEndContent from '@/components/Layout/Content/EndToEndContent.vue'
import InDatabaseContent from '@/components/Layout/Content/InDatabaseContent.vue'
import FeatureImportanceSnapshot from '@/components/FeatureImportanceSnapshot.vue'
import PerformanceSnapshotPage from '@/components/PerformanceSnapshot/PerformanceSnapshotPage.vue'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      redirect: '/agent-feature-generation'
    },
    {
      path: '/agent-feature-generation',
      name: 'agent-feature-generation',
      component: MainContent
    },
    {
      path: '/in-database-feature-computation',
      name: 'in-database-feature-computation',
      component: InDatabaseContent
    },
    {
      path: '/performance',
      name: 'performance',
      component: EndToEndContent
    },
    {
      path: '/feature-importance-snapshot',
      name: 'feature-importance-snapshot',
      component: FeatureImportanceSnapshot,
      meta: { hideChrome: true }
    },
    {
      path: '/performance-snapshot',
      name: 'performance-snapshot',
      component: PerformanceSnapshotPage,
      meta: { hideChrome: true }
    }
  ],
})

export default router
