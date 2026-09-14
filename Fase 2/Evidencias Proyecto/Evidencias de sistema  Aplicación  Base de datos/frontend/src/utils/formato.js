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
