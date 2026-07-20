import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    proxy: {
      '/ask': { target: 'http://127.0.0.1:8002', changeOrigin: true },
      '/assets': { target: 'http://127.0.0.1:8002', changeOrigin: true },
      '/auth': { target: 'http://127.0.0.1:8002', changeOrigin: true },
      '/conversations': { target: 'http://127.0.0.1:8002', changeOrigin: true },
      '/health': { target: 'http://127.0.0.1:8002', changeOrigin: true },
    },
  },
})
