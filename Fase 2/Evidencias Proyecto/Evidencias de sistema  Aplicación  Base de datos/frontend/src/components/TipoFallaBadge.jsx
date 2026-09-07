const ESTILOS = {
  desgaste: 'bg-slate-100 text-slate-600',
  sonido_extrano: 'bg-sky-100 text-sky-700',
  rota: 'bg-red-100 text-red-700',
  no_enciende: 'bg-orange-100 text-orange-700',
  otro: 'bg-slate-100 text-slate-600',
}

const ETIQUETAS = {
  desgaste: 'Desgaste',
  sonido_extrano: 'Sonido extraño',
  rota: 'Rota / no funciona',
  no_enciende: 'No enciende',
  otro: 'Otro',
}

export default function TipoFallaBadge({ tipoFalla }) {
  const estilo = ESTILOS[tipoFalla] || 'bg-slate-100 text-slate-600'
  const etiqueta = ETIQUETAS[tipoFalla] || tipoFalla
  return (
    <span className={`inline-block px-2.5 py-1 rounded-full text-xs font-semibold ${estilo}`}>
      {etiqueta}
    </span>
  )
}
