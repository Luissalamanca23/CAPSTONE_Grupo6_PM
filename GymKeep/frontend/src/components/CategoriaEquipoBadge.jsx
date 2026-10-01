// Categoria del EQUIPO (maquina): campo libre `equipos.categoria`, pensado para agrupar
// el gimnasio por tipo de maquina (cardio / fuerza / funcional / peso libre / otro).
// No confundir con la categoria de tipos_falla (mecanica/electrica/otro), que clasifica
// el tipo de FALLA de una incidencia, no el equipo en si mismo — ver CategoriaBadge.jsx.
export const CATEGORIAS_EQUIPO = [
  { valor: 'cardio', etiqueta: 'Cardio' },
  { valor: 'fuerza', etiqueta: 'Fuerza' },
  { valor: 'funcional', etiqueta: 'Funcional' },
  { valor: 'peso_libre', etiqueta: 'Peso libre' },
  { valor: 'otro', etiqueta: 'Otro' },
]

const ESTILOS = {
  cardio: 'bg-sky-100 text-sky-700',
  fuerza: 'bg-rose-100 text-rose-700',
  funcional: 'bg-violet-100 text-violet-700',
  peso_libre: 'bg-amber-100 text-amber-700',
  otro: 'bg-slate-100 text-slate-600',
}

const ETIQUETAS = Object.fromEntries(CATEGORIAS_EQUIPO.map((c) => [c.valor, c.etiqueta]))

export default function CategoriaEquipoBadge({ categoria }) {
  if (!categoria) return <span className="text-slate-400 text-xs">—</span>
  const estilo = ESTILOS[categoria] || 'bg-slate-100 text-slate-600'
  const etiqueta = ETIQUETAS[categoria] || categoria
  return (
    <span className={`inline-block px-2.5 py-1 rounded-full text-xs font-semibold ${estilo}`}>
      {etiqueta}
    </span>
  )
}
