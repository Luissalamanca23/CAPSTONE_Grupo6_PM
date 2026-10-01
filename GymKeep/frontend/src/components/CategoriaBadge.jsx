// Colores por categoria general del tipo de falla (ver postgres/schema.sql: columna
// tipos_falla.categoria). Es una de las 3 clasificaciones con las que se puede filtrar el
// historial de incidencias (junto con prioridad y estado).
const ESTILOS = {
  mecanica: 'bg-slate-100 text-slate-600',
  electrica: 'bg-amber-100 text-amber-700',
  otro: 'bg-purple-100 text-purple-700',
}

const ETIQUETAS = {
  mecanica: 'Mecánica',
  electrica: 'Eléctrica',
  otro: 'Otro',
}

export default function CategoriaBadge({ categoria }) {
  if (!categoria) return <span className="text-slate-400 text-xs">—</span>
  const estilo = ESTILOS[categoria] || 'bg-slate-100 text-slate-600'
  const etiqueta = ETIQUETAS[categoria] || categoria
  return (
    <span className={`inline-block px-2.5 py-1 rounded-full text-xs font-semibold ${estilo}`}>
      {etiqueta}
    </span>
  )
}
