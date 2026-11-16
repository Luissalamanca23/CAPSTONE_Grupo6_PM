// Prueba de extremo a extremo del reporte por QR, como en un celular (RF-07, RNF-01, RNF-03, RNF-04).
//
// Antes de correrla:
//   1. Instalar una vez:   npm install -D @playwright/test   y   npx playwright install chromium
//   2. Levantar el sistema y copiar el token de una maquina DE PRUEBA (lo que va despues de
//      /reportar/ en la direccion de su QR).
//   3. Correr (PowerShell):
//        $env:E2E_TOKEN = "el-token-de-la-maquina"
//        npm run e2e
//      Para probar la demo publica:   $env:E2E_BASE_URL = "https://pcbenjalol.tail2fa0e0.ts.net"
//
// OJO: la prueba de 1 minuto ENVIA un reporte de verdad (queda como incidencia de la maquina).
// El formulario acepta 5 reportes cada 10 minutos por maquina e IP; si se pasa, responde 429.
import { test, expect } from '@playwright/test'

import { abrirFormulario, completarReporte, limitarA4G } from './flujo-reporte.js'

const TOKEN = process.env.E2E_TOKEN

test.describe('Reporte por QR en celular (360 x 800)', () => {
  test.skip(!TOKEN, 'Define E2E_TOKEN con el token de una maquina de prueba (ver el inicio de este archivo).')
  test.use({ viewport: { width: 360, height: 800 }, isMobile: true, hasTouch: true, deviceScaleFactor: 2 })

  test.beforeEach(async ({ page }) => {
    await limitarA4G(page)
  })

  test('RNF-04: a 360 px no hay desplazamiento horizontal', async ({ page }) => {
    await abrirFormulario(page, TOKEN)
    const medidas = await page.evaluate(() => ({
      contenido: document.documentElement.scrollWidth,
      pantalla: document.documentElement.clientWidth,
    }))
    expect(medidas.contenido).toBeLessThanOrEqual(medidas.pantalla)
  })

  test('RNF-01: el formulario carga en menos de 3 s en 4G', async ({ page }, info) => {
    const ms = await abrirFormulario(page, TOKEN)
    info.annotations.push({ type: 'carga', description: `${ms} ms` })
    expect(ms, `el formulario tardo ${ms} ms en verse`).toBeLessThan(3000)
  })

  test('RF-07 y RNF-03: se completa el reporte en menos de 1 minuto y se muestra la confirmacion', async ({ page }, info) => {
    const ms = await completarReporte(page, TOKEN)
    info.annotations.push({ type: 'flujo completo', description: `${(ms / 1000).toFixed(1)} s` })
    await expect(page.getByText('Registramos la falla en')).toBeVisible()
    expect(ms, `el flujo tardo ${ms} ms`).toBeLessThan(60_000)
  })
})
