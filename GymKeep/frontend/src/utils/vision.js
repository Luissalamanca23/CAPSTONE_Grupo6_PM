// Utilidades compartidas por las pantallas de vision (Uso de maquinas y Camaras).

/** Horas con un decimal ("12,5 h"); bajo una hora, en minutos ("35 min"). */
export function formatearHoras(horas) {
  const valor = Number(horas)
  if (!Number.isFinite(valor) || valor <= 0) return '0 h'
  if (valor < 1) return `${Math.round(valor * 60)} min`
  return `${valor.toLocaleString('es-CL', { minimumFractionDigits: 1, maximumFractionDigits: 1 })} h`
}

/** Segundos como "mm:ss" (o "h:mm:ss" si pasan de una hora). */
export function formatearCronometro(segundos) {
  const total = Math.max(0, Math.round(Number(segundos) || 0))
  const h = Math.floor(total / 3600)
  const m = Math.floor((total % 3600) / 60)
  const s = total % 60
  const mm = String(m).padStart(2, '0')
  const ss = String(s).padStart(2, '0')
  return h > 0 ? `${h}:${mm}:${ss}` : `${mm}:${ss}`
}

/** Duracion de una sesion en segundos como "1 h 05 min" / "12 min" / "40 s". */
export function formatearDuracion(segundos) {
  if (segundos === null || segundos === undefined) return '—'
  const total = Math.max(0, Math.round(Number(segundos) || 0))
  if (total < 60) return `${total} s`
  const h = Math.floor(total / 3600)
  const m = Math.floor((total % 3600) / 60)
  if (h === 0) return `${m} min`
  return `${h} h ${String(m).padStart(2, '0')} min`
}

/** "hace 12 s" / "hace 3 min" a partir de segundos transcurridos. */
export function formatearHace(segundos) {
  if (segundos === null || segundos === undefined) return 'sin datos'
  if (segundos < 60) return `hace ${Math.round(segundos)} s`
  if (segundos < 3600) return `hace ${Math.round(segundos / 60)} min`
  return `hace ${Math.round(segundos / 3600)} h`
}

// Colores de cada estado de una maquina en vivo (los mismos del video anotado del pipeline):
// verde = libre, ambar = detectando, azul = sesion abierta (en uso o en pausa).
export const ESTADOS_VIVO = {
  libre: { etiqueta: 'Libre', chip: 'bg-emerald-100 text-emerald-700', relleno: 'rgba(16,185,129,0.22)', borde: '#059669' },
  candidata: { etiqueta: 'Detectando', chip: 'bg-amber-100 text-amber-700', relleno: 'rgba(245,158,11,0.28)', borde: '#d97706' },
  en_uso: { etiqueta: 'En uso', chip: 'bg-sky-100 text-sky-700', relleno: 'rgba(14,165,233,0.30)', borde: '#0284c7' },
  pausa: { etiqueta: 'En pausa', chip: 'bg-sky-50 text-sky-600', relleno: 'rgba(14,165,233,0.14)', borde: '#38bdf8' },
}

/** Texto corto del estado en vivo: "En uso 04:39", "Detectando 12/30 s", "En pausa 35/90 s", "Libre". */
export function textoEstadoVivo(vivo) {
  if (!vivo) return null
  const base = ESTADOS_VIVO[vivo.estado]?.etiqueta || vivo.estado
  if (vivo.estado === 'en_uso' && vivo.sesion_s != null) return `${base} ${formatearCronometro(vivo.sesion_s)}`
  if ((vivo.estado === 'candidata' || vivo.estado === 'pausa') && vivo.progreso_s != null && vivo.umbral_s != null) {
    return `${base} ${Math.round(vivo.progreso_s)}/${Math.round(vivo.umbral_s)} s`
  }
  return base
}
