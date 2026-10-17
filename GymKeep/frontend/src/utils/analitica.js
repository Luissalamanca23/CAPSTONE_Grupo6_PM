// Calculos del dashboard (graficos, KPIs y alertas). Son funciones puras: reciben las listas
// que ya trae la API y devuelven numeros listos para dibujar, sin tocar el DOM.

export const PERIODOS = [
  { valor: 'sem8', etiqueta: 'Últimas 8 semanas', tipo: 'semana', cantidad: 8 },
  { valor: 'mes6', etiqueta: 'Últimos 6 meses', tipo: 'mes', cantidad: 6 },
  { valor: 'mes12', etiqueta: 'Últimos 12 meses', tipo: 'mes', cantidad: 12 },
]

// Umbrales de las alertas de "Atencion recomendada" (ajustables segun la politica del gimnasio).
export const UMBRAL_HORAS_SIN_ATENCION = 48 // incidencia urgente/alta abierta hace mas de 48 h
export const UMBRAL_REINCIDENCIA = 3 // 3 o mas incidencias de una maquina en 30 dias
export const UMBRAL_HORAS_PREVENTIVO = 200 // 200 h de uso desde la ultima mantencion

export const DIAS_SEMANA = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']
// Bloques de 4 horas para el mapa de calor (hora local de quien mira el panel).
export const BLOQUES_HORA = ['0–4 h', '4–8 h', '8–12 h', '12–16 h', '16–20 h', '20–24 h']

const MS_HORA = 3600 * 1000
const MS_DIA = 24 * MS_HORA
const ESTADOS_ABIERTOS = ['pendiente', 'en_proceso']

const formatoDiaMes = new Intl.DateTimeFormat('es-CL', { day: '2-digit', month: '2-digit' })
const formatoMesCorto = new Intl.DateTimeFormat('es-CL', { month: 'short' })
const formatoMesLargo = new Intl.DateTimeFormat('es-CL', { month: 'long', year: 'numeric' })

function lunesDe(fecha) {
  const inicio = new Date(fecha.getFullYear(), fecha.getMonth(), fecha.getDate())
  const diasDesdeLunes = (inicio.getDay() + 6) % 7
  inicio.setDate(inicio.getDate() - diasDesdeLunes)
  return inicio
}

function crearBucket(tipo, inicio) {
  if (tipo === 'semana') {
    const fin = new Date(inicio)
    fin.setDate(fin.getDate() + 7)
    return {
      inicio,
      fin,
      etiqueta: formatoDiaMes.format(inicio),
      etiquetaLarga: `Semana del ${formatoDiaMes.format(inicio)}`,
    }
  }
  const fin = new Date(inicio.getFullYear(), inicio.getMonth() + 1, 1)
  return {
    inicio,
    fin,
    etiqueta: `${formatoMesCorto.format(inicio).replace('.', '')} ${String(inicio.getFullYear()).slice(2)}`,
    etiquetaLarga: formatoMesLargo.format(inicio),
  }
}

/** Intervalos (semanas o meses) del periodo, del mas antiguo al actual. */
export function calcularBuckets(periodo, ahora = new Date()) {
  const buckets = []
  for (let i = periodo.cantidad - 1; i >= 0; i -= 1) {
    if (periodo.tipo === 'semana') {
      const inicio = lunesDe(ahora)
      inicio.setDate(inicio.getDate() - 7 * i)
      buckets.push(crearBucket('semana', inicio))
    } else {
      buckets.push(crearBucket('mes', new Date(ahora.getFullYear(), ahora.getMonth() - i, 1)))
    }
  }
  return buckets
}

/** Mismo largo que el periodo, inmediatamente antes (para comparar "vs periodo anterior"). */
function rangoAnterior(periodo, buckets) {
  const inicio = buckets[0].inicio
  const anterior = new Date(inicio)
  if (periodo.tipo === 'semana') anterior.setDate(anterior.getDate() - 7 * periodo.cantidad)
  else anterior.setMonth(anterior.getMonth() - periodo.cantidad)
  return { desde: anterior, hasta: inicio }
}

function indiceBucket(fecha, buckets) {
  const tiempo = fecha.getTime()
  for (let i = 0; i < buckets.length; i += 1) {
    if (tiempo >= buckets[i].inicio.getTime() && tiempo < buckets[i].fin.getTime()) return i
  }
  return -1
}

const aNumero = (valor) => (Number.isFinite(Number(valor)) ? Number(valor) : 0)

function agrupar(items, clave, valor = () => 1) {
  const mapa = new Map()
  for (const item of items) {
    const k = clave(item)
    if (k === null || k === undefined) continue
    const actual = mapa.get(k.id ?? k) || { id: k.id ?? k, etiqueta: k.etiqueta ?? String(k), valor: 0 }
    actual.valor += valor(item)
    mapa.set(k.id ?? k, actual)
  }
  return Array.from(mapa.values()).sort((a, b) => b.valor - a.valor)
}

/** Deja los `maximo` mayores y suma el resto en "Otros" (nunca se inventan mas categorias). */
function plegarCola(lista, maximo) {
  if (lista.length <= maximo) return lista
  const cabeza = lista.slice(0, maximo)
  const resto = lista.slice(maximo).reduce((total, item) => total + item.valor, 0)
  return [...cabeza, { id: '__otros__', etiqueta: 'Otros', valor: resto }]
}

export function porcentajeCambio(actual, anterior) {
  if (!anterior) return null
  return Math.round(((actual - anterior) / anterior) * 100)
}

function promedio(lista) {
  return lista.length === 0 ? null : lista.reduce((a, b) => a + b, 0) / lista.length
}

/**
 * Todo lo que necesita el dashboard para el periodo elegido.
 * @param {object} datos { incidencias, mantenimientos, equipos, uso, etiquetasCategoria }
 */
export function calcularAnalitica({ incidencias, mantenimientos, equipos, uso, etiquetasCategoria = {} }, periodo, ahora = new Date()) {
  const buckets = calcularBuckets(periodo, ahora)
  const desde = buckets[0].inicio
  const hasta = buckets[buckets.length - 1].fin
  const anterior = rangoAnterior(periodo, buckets)

  const dentro = (fecha, d, h) => fecha >= d && fecha < h
  const reportadas = incidencias.filter((i) => dentro(new Date(i.fecha_reporte), desde, hasta))
  const reportadasAnt = incidencias.filter((i) => dentro(new Date(i.fecha_reporte), anterior.desde, anterior.hasta))
  const resueltasEnPeriodo = incidencias.filter(
    (i) => i.fecha_resolucion && dentro(new Date(i.fecha_resolucion), desde, hasta)
  )

  // --- series por intervalo
  const reportadasPorBucket = buckets.map(() => 0)
  for (const i of reportadas) reportadasPorBucket[indiceBucket(new Date(i.fecha_reporte), buckets)] += 1
  const resueltasPorBucket = buckets.map(() => 0)
  for (const i of resueltasEnPeriodo) resueltasPorBucket[indiceBucket(new Date(i.fecha_resolucion), buckets)] += 1

  const fechaMant = (m) => new Date(m.fecha_fin || m.fecha_inicio)
  const mantEnPeriodo = mantenimientos.filter((m) => dentro(fechaMant(m), desde, hasta))
  const mantAnterior = mantenimientos.filter((m) => dentro(fechaMant(m), anterior.desde, anterior.hasta))
  const gastoCorrectivo = buckets.map(() => 0)
  const gastoPreventivo = buckets.map(() => 0)
  for (const m of mantEnPeriodo) {
    const destino = m.tipo === 'preventivo' ? gastoPreventivo : gastoCorrectivo
    destino[indiceBucket(fechaMant(m), buckets)] += aNumero(m.costo_total)
  }
  const sumaGasto = (lista) => lista.reduce((total, m) => total + aNumero(m.costo_total), 0)

  // --- tiempo medio de resolucion (horas) de las incidencias reportadas en el periodo y ya resueltas
  const horasResolucion = (lista) =>
    lista
      .filter((i) => i.fecha_resolucion)
      .map((i) => (new Date(i.fecha_resolucion) - new Date(i.fecha_reporte)) / MS_HORA)
      .filter((h) => h >= 0)
  const mttrHoras = promedio(horasResolucion(reportadas))
  const mttrAnteriorHoras = promedio(horasResolucion(reportadasAnt))
  const resueltasDeReportadas = reportadas.filter((i) => i.estado === 'resuelta').length

  // --- rankings y distribuciones
  const categoriaPorEquipo = new Map(equipos.map((e) => [e.id, e.categoria]))
  const tiposFalla = plegarCola(
    agrupar(reportadas, (i) => (i.tipo_falla ? { id: i.tipo_falla.codigo, etiqueta: i.tipo_falla.nombre } : null)),
    6
  )
  const categoriasEquipo = agrupar(reportadas, (i) => {
    const categoria = categoriaPorEquipo.get(i.equipo_id)
    return { id: categoria || '__sin__', etiqueta: etiquetasCategoria[categoria] || categoria || 'Sin categoría' }
  })
  const rankingFallas = agrupar(reportadas, (i) => ({ id: i.equipo_id, etiqueta: i.equipo?.nombre || `Equipo #${i.equipo_id}` })).slice(0, 5)
  const rankingGasto = agrupar(
    mantEnPeriodo.filter((m) => aNumero(m.costo_total) > 0),
    (m) => (m.equipo ? { id: m.equipo.id, etiqueta: m.equipo.nombre } : null),
    (m) => aNumero(m.costo_total)
  ).slice(0, 5)

  // --- mapa de calor: dia de la semana x bloque de 4 horas
  const matriz = DIAS_SEMANA.map(() => BLOQUES_HORA.map(() => 0))
  for (const i of reportadas) {
    const fecha = new Date(i.fecha_reporte)
    matriz[(fecha.getDay() + 6) % 7][Math.floor(fecha.getHours() / 4)] += 1
  }
  const maximoCalor = Math.max(0, ...matriz.flat())

  // --- estado de la flota (foto de hoy, no depende del periodo)
  const flota = ['operativo', 'en_mantenimiento', 'fuera_de_servicio', 'retirado'].map((estado) => ({
    clave: estado,
    valor: equipos.filter((e) => e.estado === estado).length,
  }))

  // --- uso (modulo de vision): top por horas de los ultimos 7 dias
  const usoSemana = (uso || [])
    .filter((m) => m.horas_ultimos_7_dias > 0)
    .sort((a, b) => b.horas_ultimos_7_dias - a.horas_ultimos_7_dias)
    .slice(0, 6)
    .map((m) => ({ id: m.equipo_id, etiqueta: m.nombre, valor: m.horas_ultimos_7_dias }))

  // --- atencion recomendada
  const tAhora = ahora.getTime()
  const abiertas = incidencias.filter((i) => ESTADOS_ABIERTOS.includes(i.estado))
  const urgentesViejas = abiertas
    .filter((i) => ['urgente', 'alta'].includes(i.prioridad))
    .map((i) => ({ incidencia: i, horas: (tAhora - new Date(i.fecha_reporte).getTime()) / MS_HORA }))
    .filter((x) => x.horas > UMBRAL_HORAS_SIN_ATENCION)
    .sort((a, b) => b.horas - a.horas)
    .map((x) => ({
      id: x.incidencia.id,
      equipoId: x.incidencia.equipo_id,
      equipo: x.incidencia.equipo?.nombre || `Equipo #${x.incidencia.equipo_id}`,
      detalle: x.incidencia.tipo_falla?.nombre || 'Incidencia',
      prioridad: x.incidencia.prioridad,
      horas: x.horas,
    }))

  const ultimos30 = incidencias.filter((i) => tAhora - new Date(i.fecha_reporte).getTime() <= 30 * MS_DIA)
  const recurrentes = agrupar(ultimos30, (i) => ({ id: i.equipo_id, etiqueta: i.equipo?.nombre || `Equipo #${i.equipo_id}` }))
    .filter((x) => x.valor >= UMBRAL_REINCIDENCIA)
    .map((x) => ({ equipoId: x.id, equipo: x.etiqueta, cantidad: x.valor }))

  const preventivo = (uso || [])
    .map((m) => ({
      equipoId: m.equipo_id,
      equipo: m.nombre,
      // Sin mantencion previa, cuenta todo el uso acumulado.
      horas: m.horas_desde_mantencion ?? m.horas_uso,
      nuncaMantenida: m.horas_desde_mantencion === null || m.horas_desde_mantencion === undefined,
    }))
    .filter((m) => m.horas >= UMBRAL_HORAS_PREVENTIVO)
    .sort((a, b) => b.horas - a.horas)

  return {
    buckets,
    reportadasPorBucket,
    resueltasPorBucket,
    gastoCorrectivo,
    gastoPreventivo,
    kpis: {
      reportadas: reportadas.length,
      reportadasAnterior: reportadasAnt.length,
      tasaResolucion: reportadas.length === 0 ? null : Math.round((resueltasDeReportadas / reportadas.length) * 100),
      resueltasEnPeriodo: resueltasEnPeriodo.length,
      mttrHoras,
      mttrAnteriorHoras,
      gasto: sumaGasto(mantEnPeriodo),
      gastoAnterior: sumaGasto(mantAnterior),
      mantenimientos: mantEnPeriodo.length,
      preventivos: mantEnPeriodo.filter((m) => m.tipo === 'preventivo').length,
    },
    tiposFalla,
    categoriasEquipo,
    rankingFallas,
    rankingGasto,
    calor: { matriz, maximo: maximoCalor },
    flota,
    usoSemana,
    atencion: { urgentesViejas, recurrentes, preventivo },
  }
}

/** "5 h", "1 d 4 h" o "—" (para el tiempo medio de resolucion). */
export function formatearDuracionHoras(horas) {
  if (horas === null || horas === undefined || !Number.isFinite(horas)) return '—'
  if (horas < 1) return `${Math.max(1, Math.round(horas * 60))} min`
  if (horas < 24) return `${horas.toLocaleString('es-CL', { maximumFractionDigits: 1 })} h`
  const dias = Math.floor(horas / 24)
  const resto = Math.round(horas - dias * 24)
  return resto > 0 ? `${dias} d ${resto} h` : `${dias} d`
}

/**
 * Escala "bonita" para un eje: tope y marcas en numeros redondos (0, 50.000, 100.000...).
 * @returns {{tope: number, marcas: number[]}}
 */
export function escalaBonita(maximo) {
  const objetivo = Math.max(maximo, 0)
  const potencia = objetivo === 0 ? 1 : 10 ** Math.floor(Math.log10(objetivo))
  const pasos = [1, 2, 5, 10, 20, 50, 100].map((p) => p * potencia / 10)
  let paso = pasos[pasos.length - 1]
  for (const candidato of pasos) {
    if (candidato >= 1 && Math.ceil(objetivo / candidato) <= 5) {
      paso = candidato
      break
    }
  }
  const intervalos = Math.max(Math.ceil(objetivo / paso), 2)
  const marcas = Array.from({ length: intervalos + 1 }, (_, i) => i * paso)
  return { tope: marcas[marcas.length - 1], marcas }
}
