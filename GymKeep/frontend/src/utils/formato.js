const formateadorFechaHora = new Intl.DateTimeFormat('es-CL', {
  day: '2-digit',
  month: '2-digit',
  year: 'numeric',
  hour: '2-digit',
  minute: '2-digit',
})

/** Convierte un timestamp ISO (fecha_reporte, fecha_resolucion) a "dd/mm/aaaa hh:mm". */
export function formatearFechaHora(fechaIso) {
  if (!fechaIso) return '—'
  return formateadorFechaHora.format(new Date(fechaIso))
}

const formateadorMonto = new Intl.NumberFormat('es-CL', {
  style: 'currency',
  currency: 'CLP',
  maximumFractionDigits: 0,
})

/** Convierte un monto (costo_total) a formato de pesos chilenos, ej. "$45.000". */
export function formatearMonto(monto) {
  if (monto === null || monto === undefined || monto === '') return '—'
  const numero = Number(monto)
  if (Number.isNaN(numero)) return '—'
  return formateadorMonto.format(numero)
}
