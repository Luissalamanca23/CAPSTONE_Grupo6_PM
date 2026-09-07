const ESTILOS = {
  operativo: 'bg-emerald-100 text-emerald-700',
  en_mantenimiento: 'bg-amber-100 text-amber-700',
  fuera_de_servicio: 'bg-red-100 text-red-700',

  pendiente: 'bg-amber-100 text-amber-700',
  en_proceso: 'bg-sky-100 text-sky-700',
  resuelta: 'bg-emerald-100 text-emerald-700',
  descartada: 'bg-slate-200 text-slate-600',
}

const ETIQUETAS = {
  operativo: 'Operativo',
  en_mantenimiento: 'En mantenimiento',
  fuera_de_servicio: 'Fuera de servicio',

  pendiente: 'Pendiente',
  en_proceso: 'En proceso',
  resuelta: 'Resuelta',
  descartada: 'Descartada',
}

export default function EstadoBadge({ estado }) {
  const estilo = ESTILOS[estado] || 'bg-slate-100 text-slate-600'
  const etiqueta = ETIQUETAS[estado] || estado
  return (
    <span className={`inline-block px-2.5 py-1 rounded-full text-xs font-semibold ${estilo}`}>
      {etiqueta}
    </span>
  )
}
