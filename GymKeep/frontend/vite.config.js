import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    host: true, // escucha en la red local (0.0.0.0), no solo localhost
    port: 5173,
  },
})
