// Avisos al personal de mantencion (RF-15): incidencias nuevas y vencidas. Son funciones puras:
// reciben las incidencias que ya trae la API y devuelven que hay que avisar ahora, sin tocar el DOM.
//
//  - "urgente": incidencia nueva con prioridad urgente (la maquina no se puede ocupar).
//  - "nueva": incidencia nueva con otra prioridad.
//  - "vencida": incidencia abierta (pendiente o en proceso) hace mas de PLAZO_VENCIDA_HORAS.
// Una incidencia nueva se avisa una sola vez; una vencida se vuelve a avisar cada
// REAVISO_VENCIDAS_MS mientras siga abierta.

export const PLAZO_VENCIDA_HORAS = 48 // mismo umbral que "Atencion recomendada" del dashboard
export const RECIENTE_MS = 2 * 60_000 // al abrir el panel solo se avisan las nuevas de los ultimos 2 minutos
export const REAVISO_VENCIDAS_MS = 4 * 3600 * 1000 // una vencida se repite cada 4 horas

const MS_HORA = 3600 * 1000

/** Horas que lleva abierta una incidencia (0 si la fecha no es valida). */
export function horasAbierta(incidencia, ahora) {
  const reporte = new Date(incidencia.fecha_reporte).getTime()
  if (!Number.isFinite(reporte)) return 0
  return Math.max(0, (ahora - reporte) / MS_HORA)
}

/**
 * Decide que avisar en esta consulta.
 *  - pendientes: incidencias con estado "pendiente".
 *  - enProceso: incidencias con estado "en_proceso".
 *  - ahora: milisegundos (Date.now()).
 *  - vistas: Set con los ids de incidencias nuevas ya avisadas.
 *  - vencidasAvisadas: objeto { id: milisegundos del ultimo aviso de vencida }.
 *  - primeraConsulta: true la primera vez tras abrir el panel.
 * Devuelve { nuevas, vencidas, vistas, vencidasAvisadas } (los dos ultimos, actualizados).
 * `nuevas` va de la mas antigua a la mas reciente; `vencidas` de la mas antigua a la mas reciente
 * tambien, cada una como { incidencia, horas }.
 */
export function calcularAvisos({ pendientes = [], enProceso = [], ahora, vistas, vencidasAvisadas = {}, primeraConsulta = false }) {
  const vistasNuevas = new Set(vistas)
  const nuevas = []
  for (const inc of pendientes) {
    if (vistasNuevas.has(inc.id)) continue
    vistasNuevas.add(inc.id)
    // Al abrir el panel lo viejo no se avisa como nuevo: ya esta en la lista (si esta vencido, lo cubre "vencida").
    if (primeraConsulta && ahora - new Date(inc.fecha_reporte).getTime() > RECIENTE_MS) continue
    nuevas.push(inc)
  }
  nuevas.sort((a, b) => new Date(a.fecha_reporte) - new Date(b.fecha_reporte))

  const abiertas = [...pendientes, ...enProceso]
  const idsAbiertas = new Set(abiertas.map((i) => i.id))
  const avisadas = {}
  // Se olvidan las que ya no estan abiertas (resueltas o descartadas): si se reabrieran, avisarian de nuevo.
  for (const [id, cuando] of Object.entries(vencidasAvisadas)) {
    if (idsAbiertas.has(Number(id))) avisadas[id] = cuando
  }
  const vencidas = []
  for (const inc of abiertas) {
    const horas = horasAbierta(inc, ahora)
    if (horas <= PLAZO_VENCIDA_HORAS) continue
    const ultimo = avisadas[inc.id]
    if (ultimo !== undefined && ahora - ultimo < REAVISO_VENCIDAS_MS) continue
    avisadas[inc.id] = ahora
    vencidas.push({ incidencia: inc, horas })
  }
  vencidas.sort((a, b) => b.horas - a.horas)
  return { nuevas, vencidas, vistas: vistasNuevas, vencidasAvisadas: avisadas }
}

/** "2 d 5 h" o "50 h" para el texto del aviso de vencida. */
export function textoAntiguedad(horas) {
  if (!Number.isFinite(horas) || horas < 1) return 'menos de 1 h'
  if (horas < 48) return `${Math.floor(horas)} h`
  const dias = Math.floor(horas / 24)
  const resto = Math.floor(horas - dias * 24)
  return resto > 0 ? `${dias} d ${resto} h` : `${dias} d`
}
