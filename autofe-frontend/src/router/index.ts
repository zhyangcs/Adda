import { createRouter, createWebHistory } from 'vue-router'
import MainContent from '@/components/Layout/Content/MainContent.vue'
import EndToEndContent from '@/components/Layout/Content/EndToEndContent.vue'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      redirect: '/step-by-step'
    },
    {
      path: '/step-by-step',
      name: 'step-by-step',
      component: MainContent
    },
    {
      path: '/end-to-end',
      name: 'end-to-end',
      component: EndToEndContent
    }
  ],
})

export default router
