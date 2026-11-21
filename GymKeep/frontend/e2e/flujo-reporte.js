// Pasos compartidos de la prueba del formulario de reporte por QR (/reportar/:token).

export const TEXTO_FORMULARIO = 'Estás reportando una falla en:'
export const TEXTO_CONFIRMACION = '¡Gracias por tu reporte!'

/**
 * Simula una conexion 4G lenta (la del perfil "movil" de Lighthouse: 1,6 Mbps, 150 ms) y un
 * celular modesto (CPU 4 veces mas lenta). Solo funciona en Chromium. Con E2E_RED=normal no
 * limita nada (util para ver si un fallo es de la red o de la pagina).
 */
export async function limitarA4G(page) {
  if (process.env.E2E_RED === 'normal') return
  const cdp = await page.context().newCDPSession(page)
  await cdp.send('Network.enable')
  await cdp.send('Network.emulateNetworkConditions', {
    offline: false,
    latency: 150,
    downloadThroughput: (1.6 * 1024 * 1024) / 8,
    uploadThroughput: (750 * 1024) / 8,
  })
  await cdp.send('Emulation.setCPUThrottlingRate', { rate: 4 })
}

/** Abre el formulario y espera a que se vea. Devuelve los milisegundos que tardo. */
export async function abrirFormulario(page, token) {
  const inicio = Date.now()
  await page.goto(`/reportar/${token}`, { waitUntil: 'domcontentloaded' })
  await page.getByText(TEXTO_FORMULARIO).waitFor({ timeout: 30_000 })
  return Date.now() - inicio
}

/** Llena la encuesta como lo haria una persona y la envia. No espera la confirmacion. */
export async function responderEncuesta(page, nombre = 'Prueba E2E') {
  await page.getByRole('button', { name: /Mecánica/ }).click() // 1. tipo de problema
  await page.getByRole('button', { name: 'Desgaste visible' }).click() // 2. que le pasa
  await page.getByRole('button', { name: /Sí, funciona/ }).click() // 3. se puede seguir usando
  await page.getByPlaceholder('Escribe tu nombre').fill(nombre) // 5. nombre (4. la foto es opcional)
  await page.getByRole('button', { name: 'Enviar reporte' }).click()
}

/** Encuesta completa y espera la confirmacion. Devuelve los milisegundos desde que se abre la pagina. */
export async function completarReporte(page, token, nombre) {
  const inicio = Date.now()
  await abrirFormulario(page, token)
  await responderEncuesta(page, nombre)
  await page.getByText(TEXTO_CONFIRMACION).waitFor({ timeout: 30_000 })
  return Date.now() - inicio
}
