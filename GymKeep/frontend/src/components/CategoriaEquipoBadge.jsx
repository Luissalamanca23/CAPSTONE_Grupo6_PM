// Categoria del EQUIPO (maquina): campo `equipos.categoria`, con el esquema de 6 categorias del
// gimnasio. Los valores (`valor`) son lo que guarda la API; la API solo acepta estos 6.
// No confundir con la categoria de tipos_falla (mecanica/electrica/otro), que clasifica
// el tipo de FALLA de una incidencia, no el equipo en si mismo — ver CategoriaBadge.jsx.
export const CATEGORIAS_EQUIPO = [
  {
    valor: 'cardio',
    etiqueta: 'Cardio',
    descripcion: 'Resistencia aeróbica: cintas, bicicletas, elíptica, remo, escaladora, skierg.',
  },
  {
    valor: 'placas',
    etiqueta: 'Placas / guiadas',
    descripcion: 'Selector de peso (pin) y poleas: prensa sentada, extensión, curl, polea alta, pec deck, cruces.',
  },
  {
    valor: 'discos',
    etiqueta: 'Carga de discos',
    descripcion: 'Palancas con discos: prensa 45°, hack squat, tipo Hammer Strength, hip thrust.',
  },
  {
    valor: 'peso_libre',
    etiqueta: 'Peso libre',
    descripcion: 'Sin trayectoria fija: mancuernas, barras, discos, pesas rusas, balones medicinales.',
  },
  {
    valor: 'bancos_racks',
    etiqueta: 'Bancos y racks',
    descripcion: 'Bancos, jaula de potencia, máquina Smith, power tower, banco Scott.',
  },
  {
    valor: 'funcional',
    etiqueta: 'Funcional y accesorios',
    descripcion: 'Bandas, battle ropes, plyo box, TRX, bosu, foam roller.',
  },
]

// Valores de versiones anteriores del panel: se siguen mostrando mientras se reclasifican.
const ANTIGUAS = {
  fuerza: 'Fuerza (por reclasificar)',
  otro: 'Otro (por reclasificar)',
}

export const ETIQUETA_CATEGORIA_EQUIPO = {
  ...ANTIGUAS,
  ...Object.fromEntries(CATEGORIAS_EQUIPO.map((c) => [c.valor, c.etiqueta])),
}

export const esCategoriaVigente = (categoria) => CATEGORIAS_EQUIPO.some((c) => c.valor === categoria)

const ESTILOS = {
  cardio: 'bg-sky-100 text-sky-700',
  placas: 'bg-rose-100 text-rose-700',
  discos: 'bg-orange-100 text-orange-700',
  peso_libre: 'bg-amber-100 text-amber-700',
  bancos_racks: 'bg-teal-100 text-teal-700',
  funcional: 'bg-violet-100 text-violet-700',
}

const ESTILO_PENDIENTE = 'bg-white text-slate-500 border border-dashed border-slate-300'

export default function CategoriaEquipoBadge({ categoria }) {
  if (!categoria) return <span className="text-slate-400 text-xs">—</span>
  const vigente = esCategoriaVigente(categoria)
  const estilo = vigente ? ESTILOS[categoria] : ESTILO_PENDIENTE
  const etiqueta = ETIQUETA_CATEGORIA_EQUIPO[categoria] || categoria
  return (
    <span
      className={`inline-block px-2.5 py-1 rounded-full text-xs font-semibold ${estilo}`}
      title={vigente ? undefined : 'Categoría antigua: edítala para elegir una del esquema nuevo.'}
    >
      {etiqueta}
    </span>
  )
}
