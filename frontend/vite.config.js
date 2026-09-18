import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        ws: true   // 语音通话 WebSocket 代理
      },
      // 新增静态资源代理！
      '/static': {
        target: 'http://localhost:8000',
        changeOrigin: true
      }
    }
  }
})
