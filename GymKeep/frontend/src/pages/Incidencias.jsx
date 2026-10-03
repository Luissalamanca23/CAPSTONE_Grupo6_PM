import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api/client.js'
import EstadoBadge from '../components/EstadoBadge.jsx'
import PrioridadBadge from '../components/PrioridadBadge.jsx'
import TipoFallaBadge from '../components/TipoFallaBadge.jsx'
import CategoriaBadge from '../components/CategoriaBadge.jsx'
import { formatearFechaHora } from '../utils/formato.js'
import { getSaludEquipo } from '../utils/saludEquipo.js'

const ESTADOS_INCIDENCIA = ['pendiente', 'en_proceso', 'resuelta', 'descartada']
const PRIORIDADES = ['baja', 'media', 'alta', 'urgente']
const CATEGORIAS = ['mecanica', 'electrica', 'otro']
const POR_PAGINA = 25

const FILTROS_INICIALES = { estado: '', categoria: '', prioridad: '', fecha_desde: '', fecha_hasta: '' }

// yyyy-mm-dd en hora LOCAL (no usar toISOString: convierte a UTC y puede correr el dia).
function paraInputFecha(fecha) {
  const y = fecha.getFullYear()
  const m = String(fecha.getMonth() + 1).padStart(2, '0')
  const d = String(fecha.getDate()).padStart(2, '0')
  return `${y}-${m}-${d}`
}

function calcularRangoPreset(preset) {
  const hoy = new Date()
  if (preset === 'hoy') {
    const f = paraInputFecha(hoy)
    return { fecha_desde: f, fecha_hasta: f }
  }
  if (preset === 'semana') {
    const diaSemana = (hoy.getDay() + 6) % 7 // 0 = lunes
    const inicio = new Date(hoy)
    inicio.setDate(hoy.getDate() - diaSemana)
    return { fecha_desde: paraInputFecha(inicio), fecha_hasta: paraInputFecha(hoy) }
  }
  if (preset === 'mes') {
    const inicio = new Date(hoy.getFullYear(), hoy.getMonth(), 1)
    return { fecha_desde: paraInputFecha(inicio), fecha_hasta: paraInputFecha(hoy) }
  }
  return { fecha_desde: '', fecha_hasta: '' }
}

export default function Incidencias() {
  const [incidencias, setIncidencias] = useState([])
  const [total, setTotal] = useState(0)
  const [cargando, setCargando] = useState(true)
  const [error, setError] = useState(null)
  const [pagina, setPagina] = useState(1)

  const [filtros, setFiltros] = useState(FILTROS_INICIALES)
  const [presetFecha, setPresetFecha] = useState('todos') // todos | hoy | semana | mes | personalizado
  const [textoBusqueda, setTextoBusqueda] = useState('')
  const [busqueda, setBusqueda] = useState('') // version "debounced" de textoBusqueda

  // Espera un momento sin que el usuario escriba antes de disparar la busqueda, para no
  // hacer una peticion por cada letra.
  useEffect(() => {
    const temporizador = setTimeout(() => setBusqueda(textoBusqueda.trim()), 400)
    return () => clearTimeout(temporizador)
  }, [textoBusqueda])

  function cambiarFiltro(campo, valor) {
    setFiltros((f) => ({ ...f, [campo]: valor }))
    setPagina(1)
  }

  function elegirPreset(preset) {
    setPresetFecha(preset)
    const rango = calcularRangoPreset(preset)
    setFiltros((f) => ({ ...f, ...rango }))
    setPagina(1)
  }

  function limpiarFiltros() {
    setFiltros(FILTROS_INICIALES)
    setPresetFecha('todos')
    setTextoBusqueda('')
    setBusqueda('')
    setPagina(1)
  }

  const hayFiltrosActivos =
    Boolean(filtros.estado || filtros.categoria || filtros.prioridad || filtros.fecha_desde || busqueda)

  useEffect(() => {
    setCargando(true)
    setError(null)
    const params = {}
    if (filtros.estado) params.estado = filtros.estado
    if (filtros.categoria) params.categoria = filtros.categoria
    if (filtros.prioridad) params.prioridad = filtros.prioridad
    if (filtros.fecha_desde) params.fecha_desde = filtros.fecha_desde
    if (filtros.fecha_hasta) params.fecha_hasta = filtros.fecha_hasta
    if (busqueda) params.q = busqueda
    params.skip = (pagina - 1) * POR_PAGINA
    params.limit = POR_PAGINA

    api
      .listarIncidenciasPaginado(params)
      .then(({ items, total: totalRecibido }) => {
        setIncidencias(items)
        setTotal(totalRecibido)
      })
      .catch((err) => setError(err.message))
      .finally(() => setCargando(false))
  }, [filtros, busqueda, pagina])

  async function cambiarEstado(incidencia, nuevoEstado) {
    try {
      await api.actualizarIncidencia(incidencia.id, { estado: nuevoEstado })
      setIncidencias((lista) =>
        lista.map((i) => (i.id === incidencia.id ? { ...i, estado: nuevoEstado } : i))
      )
    } catch (err) {
      setError(err.message)
    }
  }

  const totalPaginas = Math.max(1, Math.ceil(total / POR_PAGINA))
  const desde = total === 0 ? 0 : (pagina - 1) * POR_PAGINA + 1
  const hasta = Math.min(pagina * POR_PAGINA, total)

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-slate-900">Incidencias</h1>
        <p className="text-sm text-slate-400">{total} en total</p>
      </div>

      {/* Barra de busqueda y filtros: categoria + prioridad + estado son las 3 formas de
          clasificar una incidencia, ademas de fecha y texto libre. */}
      <div className="bg-white rounded-lg border border-slate-200 shadow-sm p-4 space-y-3">
        <input
          type="text"
          value={textoBusqueda}
          onChange={(e) => setTextoBusqueda(e.target.value)}
          placeholder="Buscar por máquina, descripción o quién reportó..."
          className="w-full border border-slate-300 rounded-md px-3 py-2 text-sm"
        />

        <div className="flex flex-wrap items-center gap-2">
          {[
            { valor: 'todos', etiqueta: 'Todos' },
            { valor: 'hoy', etiqueta: 'Hoy' },
            { valor: 'semana', etiqueta: 'Esta semana' },
            { valor: 'mes', etiqueta: 'Este mes' },
            { valor: 'personalizado', etiqueta: 'Rango' },
          ].map((opcion) => (
            <button
              key={opcion.valor}
              type="button"
              onClick={() => elegirPreset(opcion.valor)}
              className={`px-3 py-1.5 rounded-full text-xs font-medium border transition-colors ${
                presetFecha === opcion.valor
                  ? 'border-emerald-600 bg-emerald-50 text-emerald-700'
                  : 'border-slate-200 text-slate-600 hover:border-slate-300'
              }`}
            >
              {opcion.etiqueta}
            </button>
          ))}

          {presetFecha === 'personalizado' && (
            <div className="flex items-center gap-1.5 text-xs">
              <input
                type="date"
                value={filtros.fecha_desde}
                onChange={(e) => cambiarFiltro('fecha_desde', e.target.value)}
                className="border border-slate-300 rounded-md px-2 py-1"
              />
              <span className="text-slate-400">a</span>
              <input
                type="date"
                value={filtros.fecha_hasta}
                onChange={(e) => cambiarFiltro('fecha_hasta', e.target.value)}
                className="border border-slate-300 rounded-md px-2 py-1"
              />
            </div>
          )}
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <select
            value={filtros.categoria}
            onChange={(e) => cambiarFiltro('categoria', e.target.value)}
            className="border border-slate-300 rounded-md text-sm px-2.5 py-1.5"
          >
            <option value="">Toda categoría</option>
            {CATEGORIAS.map((c) => (
              <option key={c} value={c}>
                {c === 'mecanica' ? 'Mecánica' : c === 'electrica' ? 'Eléctrica' : 'Otro'}
              </option>
            ))}
          </select>
          <select
            value={filtros.prioridad}
            onChange={(e) => cambiarFiltro('prioridad', e.target.value)}
            className="border border-slate-300 rounded-md text-sm px-2.5 py-1.5"
          >
            <option value="">Toda prioridad</option>
            {PRIORIDADES.map((p) => (
              <option key={p} value={p}>
                {p[0].toUpperCase() + p.slice(1)}
              </option>
            ))}
          </select>
          <select
            value={filtros.estado}
            onChange={(e) => cambiarFiltro('estado', e.target.value)}
            className="border border-slate-300 rounded-md text-sm px-2.5 py-1.5"
          >
            <option value="">Todo estado</option>
            {ESTADOS_INCIDENCIA.map((estado) => (
              <option key={estado} value={estado}>
                {estado}
              </option>
            ))}
          </select>

          {hayFiltrosActivos && (
            <button
              type="button"
              onClick={limpiarFiltros}
              className="text-xs font-medium text-slate-500 underline hover:text-slate-700 ml-auto"
            >
              Limpiar filtros
            </button>
          )}
        </div>
      </div>

      {error && <p className="text-red-600 text-sm">{error}</p>}

      {/* Bloque contenido con su propio scroll: aunque haya cientos de incidencias, la
          pagina no crece sin limite. */}
      <div className="bg-white rounded-lg border border-slate-200 shadow-sm overflow-hidden">
        <div className="overflow-auto max-h-[65vh]">
          <table className="w-full text-sm">
            <thead className="text-left text-slate-500 bg-slate-50 sticky top-0 z-10">
              <tr>
                <th className="px-4 py-2">Fecha y hora</th>
                <th className="px-4 py-2">Equipo</th>
                <th className="px-4 py-2">Categoría</th>
                <th className="px-4 py-2">Tipo de falla</th>
                <th className="px-4 py-2">Reportado por</th>
                <th className="px-4 py-2">Prioridad</th>
                <th className="px-4 py-2">Estado</th>
                <th className="px-4 py-2">Cambiar estado</th>
              </tr>
            </thead>
            <tbody>
              {cargando && (
                <tr>
                  <td className="px-4 py-6 text-slate-400 text-center" colSpan={8}>
                    Cargando...
                  </td>
                </tr>
              )}
              {!cargando && incidencias.length === 0 && (
                <tr>
                  <td className="px-4 py-6 text-slate-400 text-center" colSpan={8}>
                    {hayFiltrosActivos
                      ? 'No hay incidencias que coincidan con estos filtros.'
                      : 'Todavía no hay incidencias registradas.'}
                  </td>
                </tr>
              )}
              {incidencias.map((incidencia) => {
                const salud = getSaludEquipo(incidencia.equipo)
                return (
                  <tr key={incidencia.id} className={`border-t border-slate-100 border-l-4 ${salud.borde} ${salud.fila}`}>
                    <td className="px-4 py-2 whitespace-nowrap">{formatearFechaHora(incidencia.fecha_reporte)}</td>
                    <td className="px-4 py-2">
                      {incidencia.equipo ? (
                        <Link
                          to={`/equipos/${incidencia.equipo.id}`}
                          className="font-medium text-slate-900 hover:text-emerald-700 inline-flex items-center gap-1.5"
                        >
                          <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${salud.punto}`} />
                          {incidencia.equipo.nombre}
                        </Link>
                      ) : (
                        `#${incidencia.equipo_id}`
                      )}
                    </td>
                    <td className="px-4 py-2">
                      <CategoriaBadge categoria={incidencia.tipo_falla?.categoria} />
                    </td>
                    <td className="px-4 py-2">
                      <TipoFallaBadge tipoFalla={incidencia.tipo_falla} />
                    </td>
                    <td className="px-4 py-2">{incidencia.reportado_por || '—'}</td>
                    <td className="px-4 py-2">
                      <PrioridadBadge prioridad={incidencia.prioridad} />
                    </td>
                    <td className="px-4 py-2">
                      <EstadoBadge estado={incidencia.estado} />
                    </td>
                    <td className="px-4 py-2">
                      <select
                        value={incidencia.estado}
                        onChange={(e) => cambiarEstado(incidencia, e.target.value)}
                        className="border border-slate-300 rounded-md text-xs px-2 py-1"
                      >
                        {ESTADOS_INCIDENCIA.map((estado) => (
                          <option key={estado} value={estado}>
                            {estado}
                          </option>
                        ))}
                      </select>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>

        <div className="flex items-center justify-between gap-3 px-4 py-3 border-t border-slate-200 text-sm">
          <p className="text-slate-400 text-xs">
            {total === 0 ? 'Sin resultados' : `Mostrando ${desde}–${hasta} de ${total}`}
          </p>
          <div className="flex items-center gap-2">
            <button
              type="button"
              disabled={pagina <= 1}
              onClick={() => setPagina((p) => Math.max(1, p - 1))}
              className="px-3 py-1.5 rounded-md border border-slate-300 text-xs font-medium text-slate-600 disabled:opacity-40 hover:bg-slate-50"
            >
              ‹ Anterior
            </button>
            <span className="text-xs text-slate-500">
              Página {pagina} de {totalPaginas}
            </span>
            <button
              type="button"
              disabled={pagina >= totalPaginas}
              onClick={() => setPagina((p) => Math.min(totalPaginas, p + 1))}
              className="px-3 py-1.5 rounded-md border border-slate-300 text-xs font-medium text-slate-600 disabled:opacity-40 hover:bg-slate-50"
            >
              Siguiente ›
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
