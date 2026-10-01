import { useEffect, useMemo, useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import { api } from '../api/client.js'
import EstadoBadge from '../components/EstadoBadge.jsx'
import CategoriaEquipoBadge from '../components/CategoriaEquipoBadge.jsx'
import CategoriaBadge from '../components/CategoriaBadge.jsx'
import PrioridadBadge from '../components/PrioridadBadge.jsx'
import TipoFallaBadge from '../components/TipoFallaBadge.jsx'
import { formatearFechaHora, formatearMonto } from '../utils/formato.js'
import { getSaludEquipo } from '../utils/saludEquipo.js'

const ESTADOS_ABIERTOS = ['pendiente', 'en_proceso']

const FORM_MANT_INICIAL = { tipo: 'correctivo', tecnico: '', descripcion: '', costo: '' }
const CATEGORIAS_FALLA = ['mecanica', 'electrica', 'otro']
const ESTADOS_INCIDENCIA_HIST = ['pendiente', 'en_proceso', 'resuelta', 'descartada']

export default function EquipoDetalle() {
  const { id } = useParams()
  const [searchParams] = useSearchParams()

  const [equipo, setEquipo] = useState(null)
  const [incidencias, setIncidencias] = useState([])
  const [mantenimientos, setMantenimientos] = useState([])
  const [cargando, setCargando] = useState(true)
  const [error, setError] = useState(null)
  const [regenerando, setRegenerando] = useState(false)

  // ?mantenimiento=1 en la URL (link "Resolver" desde el listado de equipos) abre el
  // formulario de una vez, sin que el tecnico tenga que buscar el boton.
  const [mostrarFormMant, setMostrarFormMant] = useState(() => searchParams.get('mantenimiento') === '1')
  const [formMant, setFormMant] = useState(FORM_MANT_INICIAL)
  const [incidenciasSeleccionadas, setIncidenciasSeleccionadas] = useState(new Set())
  const [enviandoMant, setEnviandoMant] = useState(false)
  const [errorMant, setErrorMant] = useState(null)

  function cargar() {
    Promise.all([
      api.obtenerEquipo(id),
      api.listarIncidencias({ equipo_id: id }),
      api.listarMantenimientos(id),
    ])
      .then(([equipoData, incidenciasData, mantenimientosData]) => {
        setEquipo(equipoData)
        setIncidencias(incidenciasData)
        setMantenimientos(mantenimientosData)
        // Por defecto se preseleccionan todas las incidencias abiertas (el caso comun es
        // "se arreglo todo"); el tecnico puede desmarcar las que no correspondan.
        setIncidenciasSeleccionadas(
          new Set(incidenciasData.filter((i) => ESTADOS_ABIERTOS.includes(i.estado)).map((i) => i.id))
        )
      })
      .catch((err) => setError(err.message))
      .finally(() => setCargando(false))
  }

  useEffect(cargar, [id])

  const incidenciasPorId = useMemo(() => new Map(incidencias.map((i) => [i.id, i])), [incidencias])
  const incidenciasAbiertas = useMemo(
    () => incidencias.filter((i) => ESTADOS_ABIERTOS.includes(i.estado)),
    [incidencias]
  )

  // Filtros del historial de incidencias de esta maquina (categoria/estado/rango de fechas).
  const [filtroCategoriaHist, setFiltroCategoriaHist] = useState('')
  const [filtroEstadoHist, setFiltroEstadoHist] = useState('')
  const [fechaDesdeHist, setFechaDesdeHist] = useState('')
  const [fechaHastaHist, setFechaHastaHist] = useState('')

  const incidenciasFiltradas = useMemo(() => {
    const desde = fechaDesdeHist ? new Date(`${fechaDesdeHist}T00:00:00`) : null
    const hasta = fechaHastaHist ? new Date(`${fechaHastaHist}T23:59:59`) : null
    return incidencias.filter((incidencia) => {
      if (filtroCategoriaHist && incidencia.tipo_falla?.categoria !== filtroCategoriaHist) return false
      if (filtroEstadoHist && incidencia.estado !== filtroEstadoHist) return false
      const fecha = new Date(incidencia.fecha_reporte)
      if (desde && fecha < desde) return false
      if (hasta && fecha > hasta) return false
      return true
    })
  }, [incidencias, filtroCategoriaHist, filtroEstadoHist, fechaDesdeHist, fechaHastaHist])

  const hayFiltrosHistActivos = Boolean(filtroCategoriaHist || filtroEstadoHist || fechaDesdeHist || fechaHastaHist)

  function limpiarFiltrosHist() {
    setFiltroCategoriaHist('')
    setFiltroEstadoHist('')
    setFechaDesdeHist('')
    setFechaHastaHist('')
  }

  // Gastos de mantencion: suma de costo_total registrado en el historial de este equipo.
  const gastosMantencion = useMemo(
    () => mantenimientos.reduce((total, m) => total + (Number(m.costo_total) || 0), 0),
    [mantenimientos]
  )
  const mantenimientosConCosto = useMemo(
    () => mantenimientos.filter((m) => m.costo_total !== null && m.costo_total !== undefined).length,
    [mantenimientos]
  )

  async function regenerarQr() {
    setRegenerando(true)
    setError(null)
    try {
      await api.regenerarQr(id)
      cargar()
    } catch (err) {
      setError(err.message)
    } finally {
      setRegenerando(false)
    }
  }

  function toggleIncidenciaSeleccionada(incidenciaId) {
    setIncidenciasSeleccionadas((previo) => {
      const siguiente = new Set(previo)
      if (siguiente.has(incidenciaId)) siguiente.delete(incidenciaId)
      else siguiente.add(incidenciaId)
      return siguiente
    })
  }

  const listoMant = Boolean(formMant.tecnico.trim() && formMant.descripcion.trim())

  async function enviarMantenimiento(evento) {
    evento.preventDefault()
    if (!listoMant) return

    setEnviandoMant(true)
    setErrorMant(null)
    try {
      await api.crearMantenimiento({
        equipo_id: Number(id),
        tipo: formMant.tipo,
        tecnico: formMant.tecnico.trim(),
        descripcion: formMant.descripcion.trim(),
        incidencia_ids: Array.from(incidenciasSeleccionadas),
        costo_total: formMant.costo.trim() ? Number(formMant.costo) : null,
      })
      setMostrarFormMant(false)
      setFormMant(FORM_MANT_INICIAL)
      cargar()
    } catch (err) {
      setErrorMant(err.message)
    } finally {
      setEnviandoMant(false)
    }
  }

  if (cargando) return <p className="text-slate-500">Cargando...</p>
  if (error) return <p className="text-red-600">{error}</p>

  const token = equipo.qr_activo?.token
  const enlaceReporte = token ? `${window.location.origin}/reportar/${token}` : null
  const salud = getSaludEquipo(equipo)
  const abiertas = equipo.incidencias_abiertas ?? 0

  return (
    <div className="space-y-6">
      <div>
        <Link to="/equipos" className="text-sm text-emerald-700 font-medium">
          ← Volver a equipamiento
        </Link>
      </div>

      <div className={`rounded-lg border-2 ${salud.borde} ${salud.fila} px-5 py-3 flex items-center justify-between gap-3`}>
        <div className="flex items-center gap-3">
          <span className={`w-3 h-3 rounded-full shrink-0 ${salud.punto}`} />
          <div>
            <p className={`font-semibold ${salud.texto}`}>{salud.etiqueta}</p>
            <p className="text-xs text-slate-500">
              {salud.clave === 'negro'
                ? 'Este equipo fue marcado como fuera de servicio.'
                : abiertas === 0
                ? 'Sin incidencias abiertas.'
                : `${abiertas} incidencia${abiertas === 1 ? '' : 's'} abierta${abiertas === 1 ? '' : 's'} (pendiente o en proceso).`}
            </p>
          </div>
        </div>
        <button
          type="button"
          onClick={() => setMostrarFormMant((v) => !v)}
          className="shrink-0 bg-white border border-slate-300 rounded-md px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50"
        >
          {mostrarFormMant ? 'Cancelar' : 'Registrar mantenimiento'}
        </button>
      </div>

      {mostrarFormMant && (
        <form
          onSubmit={enviarMantenimiento}
          className="bg-white rounded-lg border border-slate-200 shadow-sm p-5 space-y-4"
        >
          <div>
            <p className="text-sm font-semibold text-slate-800">Registrar mantenimiento</p>
            <p className="text-xs text-slate-500">
              Deja constancia de qué se hizo. Las incidencias que marques abajo quedan resueltas.
            </p>
          </div>

          {incidenciasAbiertas.length > 0 ? (
            <div>
              <p className="text-xs font-medium text-slate-500 mb-2">Incidencias que quedaron resueltas</p>
              <div className="space-y-1.5">
                {incidenciasAbiertas.map((incidencia) => (
                  <label
                    key={incidencia.id}
                    className="flex items-center gap-2 text-sm text-slate-700 border border-slate-200 rounded-md px-3 py-2 cursor-pointer hover:bg-slate-50"
                  >
                    <input
                      type="checkbox"
                      checked={incidenciasSeleccionadas.has(incidencia.id)}
                      onChange={() => toggleIncidenciaSeleccionada(incidencia.id)}
                      className="shrink-0"
                    />
                    <TipoFallaBadge tipoFalla={incidencia.tipo_falla} />
                    <span className="text-xs text-slate-400 ml-auto whitespace-nowrap">
                      {formatearFechaHora(incidencia.fecha_reporte)}
                    </span>
                  </label>
                ))}
              </div>
            </div>
          ) : (
            <p className="text-xs text-slate-400">
              Este equipo no tiene incidencias abiertas — se guardará como mantenimiento general (ej. preventivo).
            </p>
          )}

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <label className="text-xs text-slate-500 flex flex-col gap-1">
              Tipo
              <select
                value={formMant.tipo}
                onChange={(e) => setFormMant({ ...formMant, tipo: e.target.value })}
                className="border border-slate-300 rounded-md px-2 py-1.5 text-sm text-slate-900"
              >
                <option value="correctivo">Correctivo (arregla una falla)</option>
                <option value="preventivo">Preventivo (revisión programada)</option>
              </select>
            </label>
            <label className="text-xs text-slate-500 flex flex-col gap-1">
              Técnico
              <input
                type="text"
                value={formMant.tecnico}
                onChange={(e) => setFormMant({ ...formMant, tecnico: e.target.value })}
                placeholder="Nombre de quien lo hizo"
                required
                className="border border-slate-300 rounded-md px-2 py-1.5 text-sm text-slate-900"
              />
            </label>
            <label className="text-xs text-slate-500 flex flex-col gap-1">
              Costo total (opcional)
              <input
                type="number"
                min="0"
                step="1"
                inputMode="numeric"
                value={formMant.costo}
                onChange={(e) => setFormMant({ ...formMant, costo: e.target.value })}
                placeholder="Ej. 45000"
                className="border border-slate-300 rounded-md px-2 py-1.5 text-sm text-slate-900"
              />
            </label>
          </div>

          <label className="text-xs text-slate-500 flex flex-col gap-1">
            Qué se hizo
            <textarea
              value={formMant.descripcion}
              onChange={(e) => setFormMant({ ...formMant, descripcion: e.target.value })}
              placeholder="Describe la reparación o revisión realizada"
              required
              rows={3}
              className="border border-slate-300 rounded-md px-3 py-2 text-sm resize-none"
            />
          </label>

          {errorMant && <p className="text-red-600 text-sm">{errorMant}</p>}

          <button
            type="submit"
            disabled={enviandoMant || !listoMant}
            className="bg-emerald-600 text-white rounded-md px-4 py-2 text-sm font-medium hover:bg-emerald-700 disabled:opacity-50"
          >
            {enviandoMant ? 'Guardando...' : 'Guardar mantenimiento'}
          </button>
        </form>
      )}

      <div className="flex flex-col sm:flex-row gap-6">
        <div className="bg-white rounded-lg border border-slate-200 shadow-sm p-6 sm:w-72 shrink-0 space-y-4">
          <div>
            <h1 className="text-xl font-bold text-slate-900">{equipo.nombre}</h1>
            <p className="text-sm text-slate-500">
              {equipo.sucursal?.nombre || 'Sin sucursal'}
              {equipo.zona?.nombre ? ` · ${equipo.zona.nombre}` : ''}
            </p>
            <div className="mt-2 flex flex-wrap gap-1.5">
              <EstadoBadge estado={equipo.estado} />
              <CategoriaEquipoBadge categoria={equipo.categoria} />
            </div>
          </div>

          <dl className="text-sm space-y-1">
            <div className="flex justify-between">
              <dt className="text-slate-400">Código de activo</dt>
              <dd className="font-mono text-xs">{equipo.codigo_activo}</dd>
            </div>
            {equipo.marca && (
              <div className="flex justify-between">
                <dt className="text-slate-400">Marca</dt>
                <dd>{equipo.marca}</dd>
              </div>
            )}
            {equipo.modelo && (
              <div className="flex justify-between">
                <dt className="text-slate-400">Modelo</dt>
                <dd>{equipo.modelo}</dd>
              </div>
            )}
          </dl>

          <div className="border-t border-slate-100 pt-4 text-center space-y-2">
            {token ? (
              <>
                <img
                  src={api.urlCodigoQr(equipo.id)}
                  alt={`Código QR de ${equipo.nombre}`}
                  className="mx-auto w-36 h-36 border border-slate-200 rounded-md"
                />
                <a
                  href={api.urlCodigoQr(equipo.id)}
                  download={`qr-${equipo.codigo_activo}.png`}
                  className="inline-block text-xs font-medium text-emerald-700 underline"
                >
                  Descargar QR para imprimir
                </a>
                <p className="text-[11px] text-slate-400 break-all">{enlaceReporte}</p>
              </>
            ) : (
              <p className="text-xs text-slate-400">Este equipo no tiene un QR activo.</p>
            )}
            <button
              onClick={regenerarQr}
              disabled={regenerando}
              className="text-xs font-medium text-slate-500 underline disabled:opacity-50"
              title="Invalida el QR actual (por ejemplo si el sticker se perdió o dañó) y emite uno nuevo."
            >
              {regenerando ? 'Generando...' : 'Regenerar QR'}
            </button>
          </div>
        </div>

        <div className="flex-1 space-y-6">
          <div className="bg-white rounded-lg border border-slate-200 shadow-sm overflow-hidden">
            <div className="px-5 py-4 border-b border-slate-200">
              <h2 className="font-semibold text-slate-800">Historial de incidencias</h2>
            </div>
            <div className="px-5 py-3 border-b border-slate-100 flex flex-wrap gap-2 items-center">
              <select
                value={filtroCategoriaHist}
                onChange={(e) => setFiltroCategoriaHist(e.target.value)}
                className="border border-slate-300 rounded-md text-xs px-2 py-1.5"
              >
                <option value="">Toda categoría</option>
                {CATEGORIAS_FALLA.map((cat) => (
                  <option key={cat} value={cat}>
                    {cat === 'mecanica' ? 'Mecánica' : cat === 'electrica' ? 'Eléctrica' : 'Otro'}
                  </option>
                ))}
              </select>
              <select
                value={filtroEstadoHist}
                onChange={(e) => setFiltroEstadoHist(e.target.value)}
                className="border border-slate-300 rounded-md text-xs px-2 py-1.5"
              >
                <option value="">Todo estado</option>
                {ESTADOS_INCIDENCIA_HIST.map((estado) => (
                  <option key={estado} value={estado}>
                    {estado}
                  </option>
                ))}
              </select>
              <label className="text-xs text-slate-400 flex items-center gap-1.5">
                Desde
                <input
                  type="date"
                  value={fechaDesdeHist}
                  onChange={(e) => setFechaDesdeHist(e.target.value)}
                  className="border border-slate-300 rounded-md text-xs px-2 py-1.5"
                />
              </label>
              <label className="text-xs text-slate-400 flex items-center gap-1.5">
                Hasta
                <input
                  type="date"
                  value={fechaHastaHist}
                  onChange={(e) => setFechaHastaHist(e.target.value)}
                  className="border border-slate-300 rounded-md text-xs px-2 py-1.5"
                />
              </label>
              {hayFiltrosHistActivos && (
                <button
                  type="button"
                  onClick={limpiarFiltrosHist}
                  className="text-xs font-medium text-slate-500 underline hover:text-slate-700"
                >
                  Limpiar
                </button>
              )}
            </div>
            <div className="overflow-auto max-h-[40vh]">
            <table className="w-full text-sm">
              <thead className="text-left text-slate-500 bg-slate-50 sticky top-0 z-10">
                <tr>
                  <th className="px-5 py-2">Fecha y hora</th>
                  <th className="px-5 py-2">Categoría</th>
                  <th className="px-5 py-2">Tipo de falla</th>
                  <th className="px-5 py-2">Reportado por</th>
                  <th className="px-5 py-2">Prioridad</th>
                  <th className="px-5 py-2">Estado</th>
                </tr>
              </thead>
              <tbody>
                {incidenciasFiltradas.length === 0 && (
                  <tr>
                    <td className="px-5 py-4 text-slate-400" colSpan={6}>
                      {incidencias.length === 0
                        ? 'Esta máquina todavía no tiene incidencias reportadas.'
                        : 'Ninguna incidencia coincide con estos filtros.'}
                    </td>
                  </tr>
                )}
                {incidenciasFiltradas.map((incidencia) => (
                  <tr key={incidencia.id} className="border-t border-slate-100">
                    <td className="px-5 py-2 whitespace-nowrap">{formatearFechaHora(incidencia.fecha_reporte)}</td>
                    <td className="px-5 py-2">
                      <CategoriaBadge categoria={incidencia.tipo_falla?.categoria} />
                    </td>
                    <td className="px-5 py-2">
                      <TipoFallaBadge tipoFalla={incidencia.tipo_falla} />
                    </td>
                    <td className="px-5 py-2">{incidencia.reportado_por || '—'}</td>
                    <td className="px-5 py-2">
                      <PrioridadBadge prioridad={incidencia.prioridad} />
                    </td>
                    <td className="px-5 py-2">
                      <EstadoBadge estado={incidencia.estado} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            </div>
          </div>

          <div className="bg-white rounded-lg border border-slate-200 shadow-sm overflow-hidden">
            <div className="px-5 py-4 border-b border-slate-200 flex flex-wrap items-center justify-between gap-2">
              <h2 className="font-semibold text-slate-800">Historial de mantenimientos</h2>
              <div className="text-right">
                <p className="text-[11px] uppercase tracking-wide text-slate-400">Gastos de mantención</p>
                <p className="text-lg font-bold text-slate-900">{formatearMonto(gastosMantencion)}</p>
                {mantenimientosConCosto > 0 && (
                  <p className="text-[11px] text-slate-400">
                    {mantenimientosConCosto} registro{mantenimientosConCosto === 1 ? '' : 's'} con costo
                  </p>
                )}
              </div>
            </div>
            <div className="overflow-auto max-h-[40vh]">
            <table className="w-full text-sm">
              <thead className="text-left text-slate-500 bg-slate-50 sticky top-0 z-10">
                <tr>
                  <th className="px-5 py-2">Fecha</th>
                  <th className="px-5 py-2">Tipo</th>
                  <th className="px-5 py-2">Técnico</th>
                  <th className="px-5 py-2">Qué se hizo</th>
                  <th className="px-5 py-2">Costo</th>
                  <th className="px-5 py-2">Incidencia relacionada</th>
                </tr>
              </thead>
              <tbody>
                {mantenimientos.length === 0 && (
                  <tr>
                    <td className="px-5 py-4 text-slate-400" colSpan={6}>
                      Todavía no hay mantenimientos registrados para este equipo.
                    </td>
                  </tr>
                )}
                {mantenimientos.map((mantenimiento) => {
                  const incidenciaRelacionada = mantenimiento.incidencia_id
                    ? incidenciasPorId.get(mantenimiento.incidencia_id)
                    : null
                  return (
                    <tr key={mantenimiento.id} className="border-t border-slate-100">
                      <td className="px-5 py-2 whitespace-nowrap">
                        {formatearFechaHora(mantenimiento.fecha_fin || mantenimiento.fecha_inicio)}
                      </td>
                      <td className="px-5 py-2 capitalize">{mantenimiento.tipo}</td>
                      <td className="px-5 py-2">{mantenimiento.tecnico || '—'}</td>
                      <td className="px-5 py-2 text-slate-600">{mantenimiento.descripcion}</td>
                      <td className="px-5 py-2 whitespace-nowrap">{formatearMonto(mantenimiento.costo_total)}</td>
                      <td className="px-5 py-2">
                        {incidenciaRelacionada ? (
                          <TipoFallaBadge tipoFalla={incidenciaRelacionada.tipo_falla} />
                        ) : (
                          <span className="text-xs text-slate-400">General</span>
                        )}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
