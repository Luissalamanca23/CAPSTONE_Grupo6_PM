// Costo total de propiedad (TCO, RF-32) de una maquina:
//   TCO = costo de compra + costo de todas sus mantenciones
// Cada mantencion guarda su costo total (repuestos + mano de obra), asi que los repuestos ya van
// dentro de las mantenciones. Si todavia no se registro el precio de compra, el TCO solo suma
// mantenciones y `adquisicionRegistrada` es false para avisarlo en pantalla.
// El mismo calculo lo hace la API (GET /equipamiento/{id}/tco); esta version sirve para mostrarlo
// al instante en el detalle de la maquina cuando se registra una mantencion nueva.

/** @param {{costo_adquisicion?: number|string|null}} equipo @param {Array<{tipo?: string, costo_total?: number|string|null}>} mantenimientos */
export function calcularTcoEquipo(equipo, mantenimientos = []) {
  const adquisicion = equipo?.costo_adquisicion
  const adquisicionRegistrada = adquisicion !== null && adquisicion !== undefined && adquisicion !== '' && !Number.isNaN(Number(adquisicion))
  let correctivo = 0
  let preventivo = 0
  let otros = 0
  let conCosto = 0
  for (const m of mantenimientos) {
    const costo = Number(m.costo_total)
    if (m.costo_total === null || m.costo_total === undefined || Number.isNaN(costo)) continue
    conCosto += 1
    if (m.tipo === 'correctivo') correctivo += costo
    else if (m.tipo === 'preventivo') preventivo += costo
    else otros += costo
  }
  const mantenciones = correctivo + preventivo + otros
  const costoAdquisicion = adquisicionRegistrada ? Number(adquisicion) : null
  return {
    costoAdquisicion,
    adquisicionRegistrada,
    costoMantenciones: mantenciones,
    costoCorrectivo: correctivo,
    costoPreventivo: preventivo,
    mantencionesConCosto: conCosto,
    tco: (costoAdquisicion ?? 0) + mantenciones,
  }
}
