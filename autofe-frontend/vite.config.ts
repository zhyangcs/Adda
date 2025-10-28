import { fileURLToPath, URL } from 'node:url'

import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import vueJsx from '@vitejs/plugin-vue-jsx'
import vueDevTools from 'vite-plugin-vue-devtools'

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    vue(),
    vueJsx(),
    vueDevTools(),
  ],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url))
    },
  },
  server: {
    proxy: {
      '/check-format/': {
        target: 'http://localhost:5000',
        changeOrigin: true
      },
      '/get-treejson/': {
        target: 'http://localhost:5000',
        changeOrigin: true
      },
      '/next-step/': {
        target: 'http://localhost:5000',
        changeOrigin: true
      },
      '/test-performance/': {
        target: 'http://localhost:5000',
        changeOrigin: true
      },
      '/gen-model/': {
        target: 'http://localhost:5000',
        changeOrigin: true
      },
      '/stop-task/': {
        target: 'http://localhost:5000',
        changeOrigin: true
      },
      '/clear-task/': {
        target: 'http://localhost:5000',
        changeOrigin: true
      },
      '/auto-step/': {
        target: 'http://localhost:5000',
        changeOrigin: true
      },
      '/check-task-status/': {
        target: 'http://localhost:5000',
        changeOrigin: true
      },
      '/get-notifications/': {
        target: 'http://localhost:5000',
        changeOrigin: true
      }
    }
  }
})
