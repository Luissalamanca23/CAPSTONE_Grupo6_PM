import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    host: true, // escucha en la red local (0.0.0.0), no solo localhost
    port: 5173,
    allowedHosts: true, // permite abrirlo por un dominio de tunel (ngrok, cloudflared)
    // Reenvia /api a la API local: asi basta con exponer UN solo puerto (5173) al publicar.
    proxy: {
      '/api': 'http://localhost:8000',
    },
  },
})
