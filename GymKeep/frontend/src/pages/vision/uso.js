// Formatos y estados compartidos por las pantallas del modulo de vision.

/** Horas decimales -> "45 min", "3 h 20 min", "128 h". */
export function formatearHoras(horas) {
  if (horas === null || horas === undefined) return '—'
  const minutos = Math.round(horas * 60)
  if (minutos < 60) return `${minutos} min`
  const h = Math.floor(minutos / 60)
  const m = minutos % 60
  if (h >= 100 || m === 0) return `${h} h`
  return `${h} h ${m} min`
}

/** Segundos -> "04:39" o "1:02:03" (cronometro). */
export function formatearCronometro(segundos) {
  if (segundos === null || segundos === undefined) return '—'
  const total = Math.max(0, Math.round(segundos))
  const h = Math.floor(total / 3600)
  const m = Math.floor((total % 3600) / 60)
  const s = total % 60
  const dos = (n) => String(n).padStart(2, '0')
  return h ? `${h}:${dos(m)}:${dos(s)}` : `${dos(m)}:${dos(s)}`
}

/** Fecha ISO -> "hace 5 min", "hace 3 h", "hace 2 días". */
export function haceCuanto(fechaIso) {
  if (!fechaIso) return '—'
  const segundos = Math.max(0, (Date.now() - new Date(fechaIso).getTime()) / 1000)
  if (segundos < 60) return 'hace un momento'
  if (segundos < 3600) return `hace ${Math.floor(segundos / 60)} min`
  if (segundos < 86400) return `hace ${Math.floor(segundos / 3600)} h`
  const dias = Math.floor(segundos / 86400)
  if (dias < 60) return `hace ${dias} ${dias === 1 ? 'día' : 'días'}`
  return new Date(fechaIso).toLocaleDateString('es-CL')
}

// Estado en vivo de una maquina segun la camara (mismo criterio que el video anotado:
// verde libre, ambar detectando, azul sesion abierta).
export const ESTADOS_VIVO = {
  libre: { etiqueta: 'Libre', punto: 'bg-emerald-500', chip: 'bg-emerald-50 text-emerald-700', relleno: '#10b981' },
  candidata: { etiqueta: 'Detectando', punto: 'bg-amber-500', chip: 'bg-amber-50 text-amber-700', relleno: '#f59e0b' },
  en_uso: { etiqueta: 'En uso', punto: 'bg-blue-600', chip: 'bg-blue-50 text-blue-700', relleno: '#2563eb' },
  pausa: { etiqueta: 'En pausa', punto: 'bg-sky-400', chip: 'bg-sky-50 text-sky-700', relleno: '#38bdf8' },
}

/** Texto del estado en vivo con su cronometro ("En uso 04:39", "Detectando 12/30 s"). */
export function textoEstadoVivo(estado) {
  if (!estado) return 'Sin cámara en línea'
  const base = ESTADOS_VIVO[estado.estado]?.etiqueta || estado.estado
  if (estado.estado === 'en_uso' && estado.sesion_s != null) return `${base} ${formatearCronometro(estado.sesion_s)}`
  if (estado.progreso_s != null && estado.umbral_s != null) {
    return `${base} ${Math.round(estado.progreso_s)}/${Math.round(estado.umbral_s)} s`
  }
  return base
}
