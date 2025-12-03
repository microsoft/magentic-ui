import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import path from 'path'
import fs from 'fs'

// Read version from the Python package's single source of truth
let APP_VERSION = 'dev'
try {
  const versionFile = fs.readFileSync(
    path.resolve(__dirname, '../src/magentic_ui/version.py'),
    'utf-8'
  )
  APP_VERSION = versionFile.match(/VERSION\s*=\s*["']([^"']+)["']/)?.[1] ?? 'dev'
} catch {
  // version.py not found — standalone frontend build or different directory layout
}

// https://vite.dev/config/
export default defineConfig({
  define: {
    __APP_VERSION__: JSON.stringify(APP_VERSION),
  },
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8081',
        changeOrigin: true,
        ws: true, // Enable WebSocket proxying
      },
      '/files': {
        target: 'http://localhost:8081',
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: '../src/magentic_ui/backend/web/ui',
    emptyOutDir: true,
  },
})
