import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url))
    }
  },
  server: {
    port: 5173,
    // No proxy needed - frontend makes direct requests to backend
    // CORS is configured on backend to allow localhost:5173
  },
  build: {
    outDir: 'dist',
    sourcemap: true
  }
})
