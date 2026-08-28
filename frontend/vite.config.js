import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  // Let Vite keep React and chart initialization in dependency order.
  // Splitting these manually can create a production-only circular import.
})
