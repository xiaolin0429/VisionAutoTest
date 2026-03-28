import path from 'node:path'
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src')
    }
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (!id.includes('node_modules')) {
            return
          }

          if (id.includes('element-plus')) {
            return 'element-plus'
          }

          if (id.includes('vue-router')) {
            return 'router'
          }

          if (id.includes('pinia') || id.includes('@vueuse')) {
            return 'state'
          }

          if (id.includes('axios')) {
            return 'http'
          }

          if (id.includes('/vue/')) {
            return 'vue'
          }
        }
      }
    }
  },
  server: {
    host: '0.0.0.0',
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true
      },
      '/healthz': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true
      }
    }
  }
})
