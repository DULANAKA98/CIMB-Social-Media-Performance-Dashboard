import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          const path = id.replaceAll('\\', '/');
          if (/node_modules\/(react|react-dom|scheduler)\//.test(path)) return 'react';
          if (path.includes('node_modules/recharts/') || /node_modules\/d3-/.test(path)) return 'charts';
        },
      },
    },
  },
})
