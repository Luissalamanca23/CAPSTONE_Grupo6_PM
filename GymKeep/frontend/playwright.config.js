import { defineConfig } from '@playwright/test'

// Prueba de extremo a extremo (ver e2e/reportar.spec.js). Solo Chromium: la red y la CPU
// lentas se simulan con el protocolo de Chrome.
export default defineConfig({
  testDir: './e2e',
  timeout: 120_000,
  retries: 0,
  reporter: [['list']],
  use: {
    baseURL: process.env.E2E_BASE_URL || 'http://localhost:5173',
    browserName: 'chromium',
    screenshot: 'only-on-failure',
  },
})
