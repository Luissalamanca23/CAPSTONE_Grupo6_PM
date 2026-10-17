import { ESTADOS_VIVO, textoEstadoVivo } from '../utils/vision.js'

// Chip con el estado en vivo de una maquina segun la camara que la mira.
export default function EstadoVivoChip({ vivo, className = '' }) {
  if (!vivo) return null
  const estilo = ESTADOS_VIVO[vivo.estado]?.chip || 'bg-slate-100 text-slate-600'
  return (
    <span className={`inline-block px-2.5 py-1 rounded-full text-xs font-semibold ${estilo} ${className}`}>
      {textoEstadoVivo(vivo)}
    </span>
  )
}
