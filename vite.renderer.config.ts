import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

/**
 * 管理者再起動用の UI ビルド設定。
 * Electron プラグインなし・相対パス（loadFile で開くため）。
 */
export default defineConfig({
  plugins: [react()],
  base: './',
  server: {
    host: '127.0.0.1',
    port: 5173,
    strictPort: true,
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
  },
})
