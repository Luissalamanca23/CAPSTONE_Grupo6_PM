/**
 * Color de salud de un equipo, segun la cantidad de incidencias ABIERTAS (pendiente o
 * en_proceso -- una falla ya resuelta no debe seguir pintando la maquina en rojo) y si el
 * equipo fue marcado como fuera de servicio (por un reporte QR que indico "ya no funciona",
 * o manualmente desde el panel).
 *
 * Escala: verde (buen estado) -> naranjo (2-3 incidencias) -> rojo (4+ incidencias) ->
 * negro (fuera de servicio, pisa cualquier conteo).
 */
const NIVELES = {
  negro: {
    clave: 'negro',
    etiqueta: 'Fuera de servicio',
    punto: 'bg-slate-900',
    fila: 'bg-slate-100',
    texto: 'text-slate-900',
    borde: 'border-slate-900',
    chip: 'bg-slate-900 text-white',
  },
  rojo: {
    clave: 'rojo',
    etiqueta: 'Estado crítico',
    punto: 'bg-red-600',
    fila: 'bg-red-50',
    texto: 'text-red-700',
    borde: 'border-red-500',
    chip: 'bg-red-100 text-red-700',
  },
  naranjo: {
    clave: 'naranjo',
    etiqueta: 'Requiere atención',
    punto: 'bg-orange-500',
    fila: 'bg-orange-50',
    texto: 'text-orange-700',
    borde: 'border-orange-400',
    chip: 'bg-orange-100 text-orange-700',
  },
  verde: {
    clave: 'verde',
    etiqueta: 'Buen estado',
    punto: 'bg-emerald-500',
    fila: 'bg-white',
    texto: 'text-emerald-700',
    borde: 'border-emerald-400',
    chip: 'bg-emerald-100 text-emerald-700',
  },
}

/**
 * @param {{estado?: string, incidencias_abiertas?: number}} equipo
 */
export function getSaludEquipo(equipo) {
  if (!equipo) return NIVELES.verde

  if (equipo.estado === 'fuera_de_servicio') {
    return NIVELES.negro
  }

  const abiertas = equipo.incidencias_abiertas ?? 0
  if (abiertas >= 4) return NIVELES.rojo
  if (abiertas >= 2) return NIVELES.naranjo
  return NIVELES.verde
}
