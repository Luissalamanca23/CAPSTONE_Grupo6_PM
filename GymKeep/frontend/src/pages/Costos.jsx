import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api/client.js'
import CategoriaEquipoBadge from '../components/CategoriaEquipoBadge.jsx'
import StatCard from '../components/StatCard.jsx'
import { formatearFechaHora, formatearMonto } from '../utils/formato.js'

const TIPOS_MANTENIMIENTO = [
  { valor: 'correctivo', etiqueta: 'Correctivo' },
  { valor: 'preventivo', etiqueta: 'Preventivo' },
]

// Vista consolidada de TODOS los mantenimientos del gimnasio (no solo los de un equipo):
// cuanto se ha gastado, en que maquinas, y el detalle completo de cada registro.
export default function Costos() {
  const [equipos, setEquipos] = useState([])
  const [mantenimientos, setMantenimientos] = useState([])
  const [cargando, setCargando] = useState(true)
  const [error, setError] = useState(null)

  const [filtroEquipo, setFiltroEquipo] = useState('')
  const [filtroTipo, setFiltroTipo] = useState('')
  const [fechaDesde, setFechaDesde] = useState('')
  const [fechaHasta, setFechaHasta] = useState('')
  const [busquedaInput, setBusquedaInput] = useState('')
  const [busqueda, setBusqueda] = useState('')

  useEffect(() => {
    api.listarEquipos().catch((err) => setError(err.message)).then((datos) => datos && setEquipos(datos))
  }, [])

  // Debounce de la busqueda de texto para no pegarle a la API en cada tecla.
  useEffect(() => {
    const temporizador = setTimeout(() => setBusqueda(busquedaInput.trim()), 350)
    return () => clearTimeout(temporizador)
  }, [busquedaInput])

  useEffect(() => {
    setCargando(true)
    const filtros = {}
    if (filtroEquipo) filtros.equipo_id = filtroEquipo
    if (filtroTipo) filtros.tipo = filtroTipo
    if (fechaDesde) filtros.fecha_desde = fechaDesde
    if (fechaHasta) filtros.fecha_hasta = fechaHasta
    if (busqueda) filtros.q = busqueda
    api
      .listarTodosLosMantenimientos(filtros)
      .then(setMantenimientos)
      .catch((err) => setError(err.message))
      .finally(() => setCargando(false))
  }, [filtroEquipo, filtroTipo, fechaDesde, fechaHasta, busqueda])

  const hayFiltrosActivos = Boolean(filtroEquipo || filtroTipo || fechaDesde || fechaHasta || busqueda)

  function limpiarFiltros() {
    setFiltroEquipo('')
    setFiltroTipo('')
    setFechaDesde('')
    setFechaHasta('')
    setBusquedaInput('')
    setBusqueda('')
  }

  const totalGastado = useMemo(
    () => mantenimientos.reduce((total, m) => total + (Number(m.costo_total) || 0), 0),
    [mantenimientos]
  )
  const conCosto = useMemo(
    () => mantenimientos.filter((m) => m.costo_total !== null && m.costo_total !== undefined).length,
    [mantenimientos]
  )
  const promedio = conCosto > 0 ? totalGastado / conCosto : 0
  const totalCorrectivo = useMemo(
    () =>
      mantenimientos
        .filter((m) => m.tipo === 'correctivo')
        .reduce((total, m) => total + (Number(m.costo_total) || 0), 0),
    [mantenimientos]
  )
  const totalPreventivo = useMemo(
    () =>
      mantenimientos
        .filter((m) => m.tipo === 'preventivo')
        .reduce((total, m) => total + (Number(m.costo_total) || 0), 0),
    [mantenimientos]
  )

  const topEquipos = useMemo(() => {
    const porEquipo = new Map()
    for (const m of mantenimientos) {
      if (!m.equipo || !m.costo_total) continue
      const actual = porEquipo.get(m.equipo.id) || { equipo: m.equipo, total: 0, registros: 0 }
      actual.total += Number(m.costo_total)
      actual.registros += 1
      porEquipo.set(m.equipo.id, actual)
    }
    return Array.from(porEquipo.values())
      .sort((a, b) => b.total - a.total)
      .slice(0, 5)
  }, [mantenimientos])

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-slate-900">Costos de mantención</h1>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          titulo="Gasto total"
          valor={formatearMonto(totalGastado)}
          detalle={`${mantenimientos.length} mantenimiento${mantenimientos.length === 1 ? '' : 's'} en total`}
        />
        <StatCard titulo="Con costo registrado" valor={conCosto} detalle={`de ${mantenimientos.length} registros`} />
        <StatCard titulo="Promedio por mantenimiento" valor={formatearMonto(promedio)} />
        <StatCard
          titulo="Correctivo vs. preventivo"
          valor={formatearMonto(totalCorrectivo)}
          detalle={`Preventivo: ${formatearMonto(totalPreventivo)}`}
        />
      </div>

      {error && <p className="text-red-600 text-sm">{error}</p>}

      <div className="bg-white rounded-lg border border-slate-200 shadow-sm p-4 flex flex-wrap gap-2 items-center">
        <input
          type="text"
          value={busquedaInput}
          onChange={(e) => setBusquedaInput(e.target.value)}
          placeholder="Buscar por técnico, descripción, equipo..."
          className="flex-1 min-w-[200px] border border-slate-300 rounded-md px-3 py-1.5 text-sm"
        />
        <select
          value={filtroEquipo}
          onChange={(e) => setFiltroEquipo(e.target.value)}
          className="border border-slate-300 rounded-md text-sm px-2.5 py-1.5"
        >
          <option value="">Todo equipo</option>
          {equipos.map((eq) => (
            <option key={eq.id} value={eq.id}>
              {eq.nombre}
            </option>
          ))}
        </select>
        <select
          value={filtroTipo}
          onChange={(e) => setFiltroTipo(e.target.value)}
          className="border border-slate-300 rounded-md text-sm px-2.5 py-1.5"
        >
          <option value="">Todo tipo</option>
          {TIPOS_MANTENIMIENTO.map((t) => (
            <option key={t.valor} value={t.valor}>
              {t.etiqueta}
            </option>
          ))}
        </select>
        <label className="text-xs text-slate-400 flex items-center gap-1.5">
          Desde
          <input
            type="date"
            value={fechaDesde}
            onChange={(e) => setFechaDesde(e.target.value)}
            className="border border-slate-300 rounded-md text-sm px-2 py-1.5"
          />
        </label>
        <label className="text-xs text-slate-400 flex items-center gap-1.5">
          Hasta
          <input
            type="date"
            value={fechaHasta}
            onChange={(e) => setFechaHasta(e.target.value)}
            className="border border-slate-300 rounded-md text-sm px-2 py-1.5"
          />
        </label>
        {hayFiltrosActivos && (
          <button
            type="button"
            onClick={limpiarFiltros}
            className="text-xs font-medium text-slate-500 underline hover:text-slate-700"
          >
            Limpiar
          </button>
        )}
      </div>

      {topEquipos.length > 0 && (
        <div className="bg-white rounded-lg border border-slate-200 shadow-sm p-5">
          <h2 className="font-semibold text-slate-800 mb-3">Máquinas con más gasto</h2>
          <div className="space-y-2">
            {topEquipos.map(({ equipo, total, registros }) => (
              <div key={equipo.id} className="flex items-center justify-between text-sm gap-3">
                <Link
                  to={`/equipos/${equipo.id}`}
                  className="font-medium text-slate-900 hover:text-emerald-700 flex items-center gap-2 min-w-0"
                >
                  <span className="truncate">{equipo.nombre}</span>
                  <CategoriaEquipoBadge categoria={equipo.categoria} />
                </Link>
                <span className="text-slate-600 whitespace-nowrap">
                  {formatearMonto(total)} <span className="text-xs text-slate-400">({registros})</span>
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="bg-white rounded-lg border border-slate-200 shadow-sm overflow-hidden">
        <div className="overflow-auto max-h-[60vh]">
          <table className="w-full text-sm">
            <thead className="text-left text-slate-500 bg-slate-50 sticky top-0 z-10">
              <tr>
                <th className="px-5 py-2">Fecha</th>
                <th className="px-5 py-2">Equipo</th>
                <th className="px-5 py-2">Categoría</th>
                <th className="px-5 py-2">Tipo</th>
                <th className="px-5 py-2">Técnico</th>
                <th className="px-5 py-2">Qué se hizo</th>
                <th className="px-5 py-2">Costo</th>
              </tr>
            </thead>
            <tbody>
              {cargando && (
                <tr>
                  <td className="px-5 py-4 text-slate-400" colSpan={7}>
                    Cargando...
                  </td>
                </tr>
              )}
              {!cargando && mantenimientos.length === 0 && (
                <tr>
                  <td className="px-5 py-4 text-slate-400" colSpan={7}>
                    {hayFiltrosActivos
                      ? 'Ningún mantenimiento coincide con estos filtros.'
                      : 'Todavía no hay mantenimientos registrados.'}
                  </td>
                </tr>
              )}
              {mantenimientos.map((m) => (
                <tr key={m.id} className="border-t border-slate-100">
                  <td className="px-5 py-2 whitespace-nowrap">{formatearFechaHora(m.fecha_fin || m.fecha_inicio)}</td>
                  <td className="px-5 py-2">
                    {m.equipo ? (
                      <Link to={`/equipos/${m.equipo.id}`} className="font-medium text-slate-900 hover:text-emerald-700">
                        {m.equipo.nombre}
                      </Link>
                    ) : (
                      '—'
                    )}
                  </td>
                  <td className="px-5 py-2">
                    <CategoriaEquipoBadge categoria={m.equipo?.categoria} />
                  </td>
                  <td className="px-5 py-2 capitalize">{m.tipo}</td>
                  <td className="px-5 py-2">{m.tecnico || '—'}</td>
                  <td className="px-5 py-2 text-slate-600">{m.descripcion}</td>
                  <td className="px-5 py-2 whitespace-nowrap font-medium">{formatearMonto(m.costo_total)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
