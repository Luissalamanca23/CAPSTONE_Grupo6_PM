import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api/client.js'
import { visionApi } from '../api/vision.js'
import { ETIQUETA_CATEGORIA_EQUIPO } from '../components/CategoriaEquipoBadge.jsx'
import {
  BarrasHorizontales,
  COLORES,
  GraficoColumnasApiladas,
  GraficoLineas,
  MapaCalor,
  TarjetaGrafico,
  TarjetaKpi,
} from '../components/graficos.jsx'
import StatCard from '../components/StatCard.jsx'
import {
  BLOQUES_HORA,
  DIAS_SEMANA,
  PERIODOS,
  UMBRAL_DEMANDA_ALTA,
  UMBRAL_HORAS_PREVENTIVO,
  UMBRAL_HORAS_SIN_ATENCION,
  UMBRAL_REINCIDENCIA,
  calcularAnalitica,
  calcularDemanda,
  formatearDuracionHoras,
  porcentajeCambio,
} from '../utils/analitica.js'
import { formatearMonto } from '../utils/formato.js'

const ETIQUETA_CATEGORIA = ETIQUETA_CATEGORIA_EQUIPO

// Cada cuanto se vuelve a pedir el estado en vivo de las camaras (si hay pipeline de vision).
const REFRESCO_USO_MS = 5000

// La API entrega a lo mas 500 filas por llamada: para que los totales del panel no queden
// cortos se piden por paginas hasta traer todo (con un tope de seguridad).
const FILAS_POR_LLAMADA = 500
const MAX_LLAMADAS = 40

async function traerTodo(pedir) {
  const todo = []
  for (let i = 0; i < MAX_LLAMADAS; i += 1) {
    const lote = await pedir({ skip: i * FILAS_POR_LLAMADA, limit: FILAS_POR_LLAMADA })
    todo.push(...lote)
    if (lote.length < FILAS_POR_LLAMADA) break
  }
  return todo
}

const formatoNumero = (valor) => Number(valor).toLocaleString('es-CL')
const formatoHoras = (valor) => `${Number(valor).toLocaleString('es-CL', { maximumFractionDigits: 1 })} h`
const formatoHorasDia = (valor) => `${Number(valor).toLocaleString('es-CL', { maximumFractionDigits: 1 })} h/día`
const NIVEL_DEMANDA = { alta: 'alta', normal: 'normal', baja: 'baja' }

/** Monto abreviado para el eje de un grafico: $50 mil, $1,2 M. */
function formatoMontoEje(valor) {
  if (valor >= 1_000_000) return `$${(valor / 1_000_000).toLocaleString('es-CL', { maximumFractionDigits: 1 })} M`
  if (valor >= 1000) return `$${(valor / 1000).toLocaleString('es-CL', { maximumFractionDigits: 1 })} mil`
  return `$${valor}`
}

/** Variacion contra el periodo anterior. `menosEsMejor` decide si bajar se pinta como bueno; null = neutral. */
function variacion(actual, anterior, menosEsMejor) {
  const cambio = porcentajeCambio(actual, anterior)
  if (cambio === null) return { texto: 'Sin datos del periodo anterior', direccion: 'igual', bueno: null }
  if (cambio === 0) return { texto: 'Igual que el periodo anterior', direccion: 'igual', bueno: null }
  const bueno = menosEsMejor === null ? null : menosEsMejor ? cambio < 0 : cambio > 0
  return {
    texto: `${Math.abs(cambio)}% ${cambio > 0 ? 'más' : 'menos'} que el periodo anterior`,
    direccion: cambio > 0 ? 'sube' : 'baja',
    bueno,
  }
}

const ICONOS = {
  alerta: 'M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z',
  repetir:
    'M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15',
  reloj: 'M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z',
  ok: 'M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z',
}

const TONOS = {
  critico: { caja: 'border-red-200 bg-red-50', icono: 'text-red-600', titulo: 'text-red-800' },
  advertencia: { caja: 'border-amber-200 bg-amber-50', icono: 'text-amber-600', titulo: 'text-amber-800' },
  info: { caja: 'border-sky-200 bg-sky-50', icono: 'text-sky-600', titulo: 'text-sky-800' },
  ok: { caja: 'border-emerald-200 bg-emerald-50', icono: 'text-emerald-600', titulo: 'text-emerald-800' },
}

const MAX_ITEMS_ALERTA = 3

function TarjetaAtencion({ tono, icono, titulo, descripcion, items }) {
  const estilo = TONOS[tono]
  const ocultas = items.length - MAX_ITEMS_ALERTA
  return (
    <div className={`rounded-lg border p-4 ${estilo.caja}`}>
      <div className="flex items-start gap-3">
        <svg className={`mt-0.5 h-5 w-5 shrink-0 ${estilo.icono}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d={ICONOS[icono]} />
        </svg>
        <div className="min-w-0 flex-1">
          <h3 className={`text-sm font-semibold ${estilo.titulo}`}>
            {titulo} <span className="font-bold">({items.length})</span>
          </h3>
          <p className="mt-0.5 text-xs text-slate-600">{descripcion}</p>
          <ul className="mt-2 space-y-1">
            {items.slice(0, MAX_ITEMS_ALERTA).map((item) => (
              <li key={item.clave} className="flex flex-wrap items-baseline justify-between gap-x-3 text-sm">
                <Link to={`/equipos/${item.equipoId}`} className="font-medium text-slate-900 hover:underline">
                  {item.equipo}
                </Link>
                <span className="text-xs text-slate-600">{item.texto}</span>
              </li>
            ))}
          </ul>
          {ocultas > 0 && <p className="mt-1 text-xs text-slate-500">y {ocultas} más</p>}
        </div>
      </div>
    </div>
  )
}

export default function Dashboard() {
  const [equipos, setEquipos] = useState([])
  const [incidencias, setIncidencias] = useState([])
  const [mantenimientos, setMantenimientos] = useState([])
  const [usoPorEquipo, setUsoPorEquipo] = useState(new Map())
  const [cargando, setCargando] = useState(true)
  const [error, setError] = useState(null)
  const [periodoClave, setPeriodoClave] = useState('sem8')

  useEffect(() => {
    Promise.all([
      traerTodo((pagina) => api.listarEquipos(null, pagina)),
      traerTodo((pagina) => api.listarIncidencias(pagina)),
      // Si falla el historial de mantenciones el resto del panel sigue funcionando.
      api.listarTodosLosMantenimientos().catch(() => []),
    ])
      .then(([equiposData, incidenciasData, mantenimientosData]) => {
        setEquipos(equiposData)
        setIncidencias(incidenciasData)
        setMantenimientos(mantenimientosData)
      })
      .catch((err) => setError(err.message))
      .finally(() => setCargando(false))
  }, [])

  // Estado en vivo de cada maquina segun las camaras (modulo de vision). Si no hay camaras o
  // el pipeline no esta corriendo, simplemente no aparece el chip: el panel funciona igual.
  useEffect(() => {
    let activo = true
    function cargarUso() {
      visionApi
        .listarMaquinas()
        .then((datos) => activo && setUsoPorEquipo(new Map(datos.map((m) => [m.equipo_id, m]))))
        .catch(() => {})
    }
    cargarUso()
    const temporizador = setInterval(cargarUso, REFRESCO_USO_MS)
    return () => {
      activo = false
      clearInterval(temporizador)
    }
  }, [])

  const periodo = PERIODOS.find((p) => p.valor === periodoClave) || PERIODOS[0]
  const analitica = useMemo(
    () =>
      calcularAnalitica(
        {
          incidencias,
          mantenimientos,
          equipos,
          uso: Array.from(usoPorEquipo.values()),
          etiquetasCategoria: ETIQUETA_CATEGORIA,
        },
        periodo
      ),
    [incidencias, mantenimientos, equipos, usoPorEquipo, periodo]
  )

  // Demanda de las maquinas (acumulado desde la instalacion; no depende del periodo elegido).
  const demanda = useMemo(
    () => calcularDemanda({ equipos, uso: Array.from(usoPorEquipo.values()), etiquetasCategoria: ETIQUETA_CATEGORIA }),
    [equipos, usoPorEquipo]
  )

  if (cargando) return <p className="text-slate-500">Cargando panel...</p>
  if (error) return <p className="text-red-600">Error al cargar datos: {error}</p>

  // Contadores para métricas
  const pendientes = incidencias.filter((i) => i.estado === 'pendiente')
  const enProceso = incidencias.filter((i) => i.estado === 'en_proceso')
  const fueraDeServicio = equipos.filter((e) => e.estado === 'fuera_de_servicio')
  const enMantencion = equipos.filter((e) => e.estado === 'en_mantenimiento')
  const operativos = equipos.filter((e) => e.estado === 'operativo')
  const enUsoAhora = equipos.filter((e) => usoPorEquipo.get(e.id)?.en_uso_ahora).length

  const { kpis, buckets, atencion } = analitica
  const etiquetas = buckets.map((b) => b.etiqueta)
  const etiquetasLargas = buckets.map((b) => b.etiquetaLarga)
  const sumar = (lista) => lista.reduce((total, valor) => total + valor, 0)
  const totalReportadas = sumar(analitica.reportadasPorBucket)
  const totalGasto = sumar(analitica.gastoCorrectivo) + sumar(analitica.gastoPreventivo)

  // Distribuciones: se agrega el porcentaje del total para el tooltip.
  const conPorcentaje = (lista) => {
    const total = sumar(lista.map((item) => item.valor))
    return lista.map((item) => ({ ...item, detalle: `${Math.round((item.valor / total) * 100)}% del total` }))
  }

  // Disponibilidad de la flota (foto de hoy): operativas sobre las que estan en servicio.
  const flotaActiva = equipos.filter((e) => e.estado !== 'retirado').length
  const disponibilidad = flotaActiva === 0 ? null : Math.round((operativos.length / flotaActiva) * 100)
  const hayVision = usoPorEquipo.size > 0

  // Alertas de "Atencion recomendada"
  const alertaUrgentes = atencion.urgentesViejas.map((a) => ({
    clave: `u-${a.id}`,
    equipoId: a.equipoId,
    equipo: a.equipo,
    texto: `${a.detalle} · hace ${formatearDuracionHoras(a.horas)}`,
  }))
  const alertaRecurrentes = atencion.recurrentes.map((a) => ({
    clave: `r-${a.equipoId}`,
    equipoId: a.equipoId,
    equipo: a.equipo,
    texto: `${a.cantidad} incidencias en 30 días`,
  }))
  const alertaPreventivo = atencion.preventivo.map((a) => ({
    clave: `p-${a.equipoId}`,
    equipoId: a.equipoId,
    equipo: a.equipo,
    texto: a.nuncaMantenida
      ? `${formatoHoras(a.horas)} de uso, sin mantención registrada`
      : `${formatoHoras(a.horas)} desde la última mantención`,
  }))
  const hayAlertas = alertaUrgentes.length + alertaRecurrentes.length + alertaPreventivo.length > 0

  // Demanda: las 6 mas usadas y el uso medio por tipo de maquina.
  const demandaMaquinas = (demanda?.maquinas ?? []).slice(0, 6).map((m) => ({
    id: m.id,
    etiqueta: m.etiqueta,
    valor: m.horasPorDia,
    detalle: `${Math.round(m.ocupacion * 100)}% de ocupación · demanda ${NIVEL_DEMANDA[m.nivel]}`,
  }))
  const demandaCategorias = (demanda?.categorias ?? []).map((c) => ({
    id: c.id,
    etiqueta: c.etiqueta,
    valor: c.horasPorDiaPorMaquina,
    detalle: `${c.maquinas} máquinas (${c.porcentajeFlota}% de la flota) · ${c.porcentajeUso}% de las horas de uso`,
  }))
  const categoriasAltas = (demanda?.categorias ?? []).filter((c) => c.nivel === 'alta')

  return (
    <div className="space-y-6">
      {/* 1. Encabezado principal */}
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-2xl font-bold text-slate-900">Panel de gestión</h1>
        <div className="flex gap-2">
          <Link
            to="/equipos"
            className="text-sm font-medium border border-slate-300 text-slate-600 rounded-md px-3 py-1.5 hover:bg-slate-100"
          >
            + Registrar equipo
          </Link>
          <Link
            to="/incidencias"
            className="text-sm font-medium bg-brand-600 text-white rounded-md px-3 py-1.5 hover:bg-brand-700"
          >
            Ver todas las incidencias
          </Link>
        </div>
      </div>

      {/* 2. Tarjetas de métricas generales: estado de la flota e incidencias abiertas */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          titulo="Disponibilidad de la flota"
          valor={disponibilidad === null ? '—' : `${disponibilidad}%`}
          detalle={`${operativos.length} de ${flotaActiva} máquinas operativas · ${enMantencion.length} en mantención · ${fueraDeServicio.length} fuera de servicio`}
        />
        <StatCard titulo="Incidencias pendientes" valor={pendientes.length} />
        <StatCard titulo="En proceso" valor={enProceso.length} />
        {hayVision ? (
          <Link to="/uso" className="block h-full rounded-lg transition-shadow hover:shadow-md [&>div]:h-full">
            <StatCard titulo="En uso ahora" valor={enUsoAhora} detalle="Ver el estado en tiempo real →" />
          </Link>
        ) : (
          <StatCard titulo="Equipos registrados" valor={equipos.length} />
        )}
      </div>

      {/* 3. Atención recomendada: lo que conviene mirar hoy */}
      <section className="space-y-3">
        <div>
          <h2 className="text-lg font-semibold text-slate-800">Atención recomendada</h2>
          <p className="text-xs text-slate-500">Avisos calculados con las incidencias y el uso de las máquinas.</p>
        </div>
        {hayAlertas ? (
          <div className="grid gap-3" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(18rem, 1fr))' }}>
            {alertaUrgentes.length > 0 && (
              <TarjetaAtencion
                tono="critico"
                icono="alerta"
                titulo="Urgentes sin resolver"
                descripcion={`Incidencias urgentes o altas abiertas hace más de ${UMBRAL_HORAS_SIN_ATENCION} horas.`}
                items={alertaUrgentes}
              />
            )}
            {alertaRecurrentes.length > 0 && (
              <TarjetaAtencion
                tono="advertencia"
                icono="repetir"
                titulo="Fallas recurrentes"
                descripcion={`Máquinas con ${UMBRAL_REINCIDENCIA} o más incidencias en los últimos 30 días.`}
                items={alertaRecurrentes}
              />
            )}
            {alertaPreventivo.length > 0 && (
              <TarjetaAtencion
                tono="info"
                icono="reloj"
                titulo="Mantención preventiva sugerida"
                descripcion={`Más de ${UMBRAL_HORAS_PREVENTIVO} horas de uso desde la última mantención (según las cámaras).`}
                items={alertaPreventivo}
              />
            )}
          </div>
        ) : (
          <div className={`flex items-center gap-3 rounded-lg border p-4 ${TONOS.ok.caja}`}>
            <svg className={`h-5 w-5 shrink-0 ${TONOS.ok.icono}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d={ICONOS.ok} />
            </svg>
            <p className={`text-sm font-medium ${TONOS.ok.titulo}`}>
              Todo en orden: no hay incidencias urgentes atrasadas ni máquinas con fallas repetidas.
            </p>
          </div>
        )}
      </section>

      {/* 4. Análisis: un solo filtro de periodo para todo lo que sigue */}
      <section className="space-y-4">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold text-slate-800">Análisis</h2>
            <p className="text-xs text-slate-500">Las cifras y gráficos de esta sección usan el periodo elegido.</p>
          </div>
          <div className="flex flex-wrap gap-1.5" role="group" aria-label="Periodo de análisis">
            {PERIODOS.map((opcion) => {
              const elegido = opcion.valor === periodoClave
              return (
                <button
                  key={opcion.valor}
                  type="button"
                  aria-pressed={elegido}
                  onClick={() => setPeriodoClave(opcion.valor)}
                  className={`rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${
                    elegido ? 'bg-slate-900 text-white' : 'bg-white text-slate-600 border border-slate-200 hover:bg-slate-100'
                  }`}
                >
                  {elegido && <span aria-hidden="true">✓ </span>}
                  {opcion.etiqueta}
                </button>
              )
            })}
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <TarjetaKpi
            titulo="Incidencias reportadas"
            valor={formatoNumero(kpis.reportadas)}
            delta={variacion(kpis.reportadas, kpis.reportadasAnterior, true)}
          />
          <TarjetaKpi
            titulo="Tasa de resolución"
            valor={kpis.tasaResolucion === null ? '—' : `${kpis.tasaResolucion}%`}
            detalle={`${formatoNumero(kpis.resueltasEnPeriodo)} resueltas en el periodo`}
          />
          <TarjetaKpi
            titulo="Tiempo medio de resolución"
            valor={formatearDuracionHoras(kpis.mttrHoras)}
            delta={
              kpis.mttrHoras === null || kpis.mttrAnteriorHoras === null
                ? undefined
                : variacion(kpis.mttrHoras, kpis.mttrAnteriorHoras, true)
            }
            detalle={kpis.mttrHoras === null ? 'Aún no hay incidencias resueltas' : undefined}
          />
          <TarjetaKpi
            titulo="Gasto en mantenciones"
            valor={formatearMonto(kpis.gasto)}
            delta={variacion(kpis.gasto, kpis.gastoAnterior, null)}
            detalle={`${kpis.mantenimientos} mantenciones · ${kpis.preventivos} preventivas`}
          />
        </div>

        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <TarjetaGrafico
            titulo="Incidencias reportadas y resueltas"
            subtitulo={`Por ${periodo.tipo}, ${periodo.etiqueta.toLowerCase()}`}
            leyenda={{
              forma: 'linea',
              items: [
                { color: COLORES.azul, etiqueta: 'Reportadas' },
                { color: COLORES.aqua, etiqueta: 'Resueltas' },
              ],
            }}
            vacio={totalReportadas + sumar(analitica.resueltasPorBucket) === 0}
            tabla={{
              columnas: ['Intervalo', 'Reportadas', 'Resueltas'],
              filas: buckets.map((b, i) => [b.etiquetaLarga, analitica.reportadasPorBucket[i], analitica.resueltasPorBucket[i]]),
            }}
          >
            <GraficoLineas
              etiquetas={etiquetas}
              etiquetasLargas={etiquetasLargas}
              series={[
                { id: 'reportadas', nombre: 'Reportadas', color: COLORES.azul, valores: analitica.reportadasPorBucket },
                { id: 'resueltas', nombre: 'Resueltas', color: COLORES.aqua, valores: analitica.resueltasPorBucket },
              ]}
              formatoValor={formatoNumero}
            />
          </TarjetaGrafico>

          <TarjetaGrafico
            titulo="Gasto en mantenciones"
            subtitulo={`Correctivo y preventivo, por ${periodo.tipo}`}
            leyenda={{
              forma: 'caja',
              items: [
                { color: COLORES.naranja, etiqueta: 'Correctivo' },
                { color: COLORES.gris, etiqueta: 'Preventivo' },
              ],
            }}
            vacio={totalGasto === 0}
            mensajeVacio="No hay mantenciones con costo registrado en este periodo."
            tabla={{
              columnas: ['Intervalo', 'Correctivo', 'Preventivo', 'Total'],
              filas: buckets.map((b, i) => [
                b.etiquetaLarga,
                formatearMonto(analitica.gastoCorrectivo[i]),
                formatearMonto(analitica.gastoPreventivo[i]),
                formatearMonto(analitica.gastoCorrectivo[i] + analitica.gastoPreventivo[i]),
              ]),
            }}
          >
            <GraficoColumnasApiladas
              etiquetas={etiquetas}
              etiquetasLargas={etiquetasLargas}
              series={[
                { id: 'correctivo', nombre: 'Correctivo', color: COLORES.naranja, valores: analitica.gastoCorrectivo },
                { id: 'preventivo', nombre: 'Preventivo', color: COLORES.gris, valores: analitica.gastoPreventivo },
              ]}
              formatoValor={formatearMonto}
              formatoEje={formatoMontoEje}
            />
          </TarjetaGrafico>

          <TarjetaGrafico
            titulo="Tipos de falla más frecuentes"
            subtitulo={`${formatoNumero(kpis.reportadas)} incidencias en el periodo`}
            vacio={analitica.tiposFalla.length === 0}
            tabla={{
              columnas: ['Tipo de falla', 'Incidencias'],
              filas: analitica.tiposFalla.map((t) => [t.etiqueta, t.valor]),
            }}
          >
            <BarrasHorizontales items={conPorcentaje(analitica.tiposFalla)} formatoValor={formatoNumero} nombreValor="incidencias" />
          </TarjetaGrafico>

          <TarjetaGrafico
            titulo="Incidencias por tipo de máquina"
            subtitulo="Qué categorías de equipos fallan más"
            vacio={analitica.categoriasEquipo.length === 0}
            tabla={{
              columnas: ['Categoría', 'Incidencias'],
              filas: analitica.categoriasEquipo.map((c) => [c.etiqueta, c.valor]),
            }}
          >
            <BarrasHorizontales items={conPorcentaje(analitica.categoriasEquipo)} formatoValor={formatoNumero} nombreValor="incidencias" />
          </TarjetaGrafico>

          <TarjetaGrafico
            titulo="Máquinas que más cuestan"
            subtitulo="Las 5 con más gasto en mantenciones"
            vacio={analitica.rankingGasto.length === 0}
            mensajeVacio="No hay mantenciones con costo registrado en este periodo."
            tabla={{
              columnas: ['Máquina', 'Gasto'],
              filas: analitica.rankingGasto.map((m) => [m.etiqueta, formatearMonto(m.valor)]),
            }}
          >
            <BarrasHorizontales items={analitica.rankingGasto} formatoValor={formatearMonto} />
          </TarjetaGrafico>

          <TarjetaGrafico
            titulo="¿Cuándo se reportan las fallas?"
            subtitulo="Incidencias por día de la semana y franja horaria"
            vacio={analitica.calor.maximo === 0}
            tabla={{
              columnas: ['Día', ...BLOQUES_HORA],
              filas: DIAS_SEMANA.map((dia, f) => [dia, ...analitica.calor.matriz[f]]),
            }}
          >
            <MapaCalor matriz={analitica.calor.matriz} maximo={analitica.calor.maximo} filas={DIAS_SEMANA} columnas={BLOQUES_HORA} />
          </TarjetaGrafico>

        </div>
      </section>

      {/* 4b. Demanda: que maquinas se ocupan mas y cuales conviene sumar */}
      {demanda && (
        <section className="space-y-4">
          <div>
            <h2 className="text-lg font-semibold text-slate-800">Demanda de máquinas: qué conviene ampliar</h2>
            <p className="text-xs text-slate-500">
              Uso acumulado de cada máquina desde que se instaló (según las cámaras); no depende del periodo elegido
              arriba. Sirve para decidir qué sumar si el gimnasio crece o se abre otro local.
            </p>
          </div>

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <TarjetaGrafico
              titulo="Máquinas más demandadas"
              subtitulo={`Horas de uso por día · promedio del gimnasio: ${formatoHorasDia(demanda.promedioHorasDia)}`}
              tabla={{
                columnas: ['Máquina', 'Horas por día', 'Ocupación', 'Demanda'],
                filas: demanda.maquinas
                  .slice(0, 6)
                  .map((m) => [m.etiqueta, formatoHorasDia(m.horasPorDia), `${Math.round(m.ocupacion * 100)}%`, NIVEL_DEMANDA[m.nivel]]),
              }}
            >
              <BarrasHorizontales items={demandaMaquinas} formatoValor={formatoHorasDia} nombreValor="de uso al día" />
            </TarjetaGrafico>

            <TarjetaGrafico
              titulo="Demanda por tipo de máquina"
              subtitulo="Horas por día de una máquina promedio de cada tipo"
              tabla={{
                columnas: ['Tipo', 'Máquinas', 'Horas por día (por máquina)', '% de las horas de uso'],
                filas: demanda.categorias.map((c) => [c.etiqueta, c.maquinas, formatoHorasDia(c.horasPorDiaPorMaquina), `${c.porcentajeUso}%`]),
              }}
            >
              <BarrasHorizontales items={demandaCategorias} formatoValor={formatoHorasDia} nombreValor="por máquina" />
            </TarjetaGrafico>

            <div className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm lg:col-span-2">
              <h3 className="text-sm font-semibold text-slate-800">Para ampliar o abrir otro local</h3>
              <div className="mt-3 grid grid-cols-1 gap-6 md:grid-cols-2">
                <div>
                  <p className="text-xs font-medium uppercase tracking-wide text-emerald-700">Conviene sumar más unidades</p>
                  {demanda.sugeridas.length > 0 ? (
                    <ul className="mt-2 space-y-1.5 text-sm">
                      {demanda.sugeridas.map((m) => (
                        <li key={m.id} className="flex flex-wrap items-baseline justify-between gap-x-3">
                          <Link to={`/equipos/${m.id}`} className="font-medium text-slate-900 hover:underline">
                            {m.etiqueta}
                          </Link>
                          <span className="text-xs text-slate-600">
                            {formatoHorasDia(m.horasPorDia)} · {m.indice.toLocaleString('es-CL', { maximumFractionDigits: 1 })}× el promedio
                          </span>
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p className="mt-2 text-sm text-slate-500">Ninguna máquina destaca todavía por sobre el promedio.</p>
                  )}
                  {categoriasAltas.length > 0 && (
                    <p className="mt-3 text-xs text-slate-600">
                      Por tipo, la mayor demanda por máquina está en: {categoriasAltas.map((c) => c.etiqueta).join(', ')}.
                    </p>
                  )}
                </div>
                <div>
                  <p className="text-xs font-medium uppercase tracking-wide text-slate-500">Poca demanda: no es prioridad</p>
                  {demanda.pocaDemanda.length > 0 ? (
                    <ul className="mt-2 space-y-1.5 text-sm">
                      {demanda.pocaDemanda.map((m) => (
                        <li key={m.id} className="flex flex-wrap items-baseline justify-between gap-x-3">
                          <Link to={`/equipos/${m.id}`} className="font-medium text-slate-900 hover:underline">
                            {m.etiqueta}
                          </Link>
                          <span className="text-xs text-slate-600">{formatoHorasDia(m.horasPorDia)}</span>
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p className="mt-2 text-sm text-slate-500">Todas las máquinas tienen un uso razonable.</p>
                  )}
                </div>
              </div>
              <p className="mt-4 text-xs text-slate-500">
                Demanda alta: se usa {UMBRAL_DEMANDA_ALTA.toLocaleString('es-CL')} veces o más el promedio del gimnasio; baja: menos
                de la mitad. Ocupación: parte de las horas de apertura (16 h) en que estuvo ocupada.
              </p>
            </div>
          </div>
        </section>
      )}
    </div>
  )
}
