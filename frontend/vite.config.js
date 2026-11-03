import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  // In development, serve the API from the same origin as the app (as CloudFront does
  // in production) so the login cookie is sent. Override the target with VITE_PROXY_TARGET.
  server: {
    proxy: { '/api': process.env.VITE_PROXY_TARGET || 'http://127.0.0.1:8000' },
  },
  // Let Vite keep React and chart initialization in dependency order.
  // Splitting these manually can create a production-only circular import.
})
