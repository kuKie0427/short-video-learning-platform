/// <reference types="vitest" />
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    host: '0.0.0.0', // Allow access from local network (for mobile testing)
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://localhost', // Backend Gateway is on port 80
        changeOrigin: true,
        // rewrite: (path) => path.replace(/^\/api/, ''), // Keep /api if backend expects it
      },
      '/smart_split_output': {
        target: 'http://localhost',
        changeOrigin: true,
      },
      '/uploads': {
        target: 'http://localhost',
        changeOrigin: true,
      },
      '/videos': {
        target: 'http://localhost',
        changeOrigin: true,
      },
    },
  },
  test: {
    environment: 'jsdom',
    globals: false,
    setupFiles: ['./src/test/setup.ts'],
    css: false,
    // 登录页测试使用真实定时器等待 mock 延迟（user-event 与 fake timers 兼容问题），放宽超时
    testTimeout: 15000,
  },
})
