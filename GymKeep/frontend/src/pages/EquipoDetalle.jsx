import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '../api/client.js'
import EstadoBadge from '../components/EstadoBadge.jsx'
import PrioridadBadge from '../components/PrioridadBadge.jsx'
import TipoFallaBadge from '../components/TipoFallaBadge.jsx'
import { formatearFechaHora } from '../utils/formato.js'

export default function EquipoDetalle() {
  const { id } = useParams()
  const [equipo, setEquipo] = useState(null)
  const [incidencias, setIncidencias] = useState([])
  const [cargando, setCargando] = useState(true)
  const [error, setError] = useState(null)
  const [regenerando, setRegenerando] = useState(false)

  function cargar() {
    Promise.all([api.obtenerEquipo(id), api.listarIncidencias({ equipo_id: id })])
      .then(([equipoData, incidenciasData]) => {
        setEquipo(equipoData)
        setIncidencias(incidenciasData)
      })
      .catch((err) => setError(err.message))
      .finally(() => setCargando(false))
  }

  useEffect(cargar, [id])

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

  if (cargando) return <p className="text-slate-500">Cargando...</p>
  if (error) return <p className="text-red-600">{error}</p>

  const token = equipo.qr_activo?.token
  const enlaceReporte = token ? `${window.location.origin}/reportar/${token}` : null

  return (
    <div className="space-y-6">
      <div>
        <Link to="/equipos" className="text-sm text-emerald-700 font-medium">
          ← Volver a equipamiento
        </Link>
      </div>

      <div className="flex flex-col sm:flex-row gap-6">
        <div className="bg-white rounded-lg border border-slate-200 shadow-sm p-6 sm:w-72 shrink-0 space-y-4">
          <div>
            <h1 className="text-xl font-bold text-slate-900">{equipo.nombre}</h1>
            <p className="text-sm text-slate-500">
              {equipo.sucursal?.nombre || 'Sin sucursal'}
              {equipo.zona?.nombre ? ` · ${equipo.zona.nombre}` : ''}
            </p>
            <div className="mt-2">
              <EstadoBadge estado={equipo.estado} />
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

        <div className="flex-1 bg-white rounded-lg border border-slate-200 shadow-sm">
          <div className="px-5 py-4 border-b border-slate-200">
            <h2 className="font-semibold text-slate-800">Historial de incidencias</h2>
          </div>
          <table className="w-full text-sm">
            <thead className="text-left text-slate-500 bg-slate-50">
              <tr>
                <th className="px-5 py-2">Fecha y hora</th>
                <th className="px-5 py-2">Tipo de falla</th>
                <th className="px-5 py-2">Origen</th>
                <th className="px-5 py-2">Reportado por</th>
                <th className="px-5 py-2">Prioridad</th>
                <th className="px-5 py-2">Estado</th>
              </tr>
            </thead>
            <tbody>
              {incidencias.length === 0 && (
                <tr>
                  <td className="px-5 py-4 text-slate-400" colSpan={6}>
                    Esta máquina todavía no tiene incidencias reportadas.
                  </td>
                </tr>
              )}
              {incidencias.map((incidencia) => (
                <tr key={incidencia.id} className="border-t border-slate-100">
                  <td className="px-5 py-2 whitespace-nowrap">{formatearFechaHora(incidencia.fecha_reporte)}</td>
                  <td className="px-5 py-2">
                    <TipoFallaBadge tipoFalla={incidencia.tipo_falla} />
                  </td>
                  <td className="px-5 py-2 text-xs text-slate-500 uppercase">{incidencia.origen}</td>
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
    </div>
  )
}
