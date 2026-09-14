// Colores por codigo del catalogo `tipos_falla` (ver GymKeep_BDD_Completa/postgres/schema.sql).
const ESTILOS = {
  DESGASTE: 'bg-slate-100 text-slate-600',
  SONIDO_EXTRANO: 'bg-sky-100 text-sky-700',
  ROTA: 'bg-red-100 text-red-700',
  NO_ENCIENDE: 'bg-orange-100 text-orange-700',
  MOVIMIENTO_ANOMALO: 'bg-purple-100 text-purple-700',
  OTRO: 'bg-slate-100 text-slate-600',
}

/** tipoFalla: objeto del catalogo ({ codigo, nombre, ... }), como lo devuelve la API. */
export default function TipoFallaBadge({ tipoFalla }) {
  if (!tipoFalla) return <span className="text-slate-400 text-xs">—</span>
  const estilo = ESTILOS[tipoFalla.codigo] || 'bg-slate-100 text-slate-600'
  return (
    <span className={`inline-block px-2.5 py-1 rounded-full text-xs font-semibold ${estilo}`}>
      {tipoFalla.nombre}
    </span>
  )
}
