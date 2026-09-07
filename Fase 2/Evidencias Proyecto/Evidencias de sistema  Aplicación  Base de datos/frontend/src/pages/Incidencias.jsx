import { useEffect, useState } from 'react'
import { api } from '../api/client.js'
import EstadoBadge from '../components/EstadoBadge.jsx'
import PrioridadBadge from '../components/PrioridadBadge.jsx'
import TipoFallaBadge from '../components/TipoFallaBadge.jsx'
import { formatearFechaHora } from '../utils/formato.js'

const ESTADOS_INCIDENCIA = ['pendiente', 'en_proceso', 'resuelta', 'descartada']
const ORDEN_PRIORIDAD = { urgente: 4, alta: 3, media: 2, baja: 1 }

export default function Incidencias() {
  const [incidencias, setIncidencias] = useState([])
  const [cargando, setCargando] = useState(true)
  const [error, setError] = useState(null)
  const [filtroEstado, setFiltroEstado] = useState('')

  function cargarIncidencias() {
    setCargando(true)
    const filtros = filtroEstado ? { estado: filtroEstado } : {}
    api
      .listarIncidencias(filtros)
      .then((datos) => {
        const ordenadas = [...datos].sort(
          (a, b) => (ORDEN_PRIORIDAD[b.prioridad] ?? 0) - (ORDEN_PRIORIDAD[a.prioridad] ?? 0)
        )
        setIncidencias(ordenadas)
      })
      .catch((err) => setError(err.message))
      .finally(() => setCargando(false))
  }

  useEffect(cargarIncidencias, [filtroEstado])

  async function cambiarEstado(incidencia, nuevoEstado) {
    try {
      await api.actualizarIncidencia(incidencia.id, { estado: nuevoEstado })
      cargarIncidencias()
    } catch (err) {
      setError(err.message)
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-slate-900">Incidencias</h1>
        <select
          value={filtroEstado}
          onChange={(e) => setFiltroEstado(e.target.value)}
          className="border border-slate-300 rounded-md text-sm px-3 py-1.5"
        >
          <option value="">Todos los estados</option>
          {ESTADOS_INCIDENCIA.map((estado) => (
            <option key={estado} value={estado}>
              {estado}
            </option>
          ))}
        </select>
      </div>

      {error && <p className="text-red-600 text-sm">{error}</p>}

      <div className="bg-white rounded-lg border border-slate-200 shadow-sm overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="text-left text-slate-500 bg-slate-50">
            <tr>
              <th className="px-5 py-2">Fecha y hora</th>
              <th className="px-5 py-2">Equipo</th>
              <th className="px-5 py-2">Tipo de falla</th>
              <th className="px-5 py-2">Reportado por</th>
              <th className="px-5 py-2">Prioridad</th>
              <th className="px-5 py-2">Estado</th>
              <th className="px-5 py-2">Cambiar estado</th>
            </tr>
          </thead>
          <tbody>
            {cargando && (
              <tr>
                <td className="px-5 py-4 text-slate-400" colSpan={7}>Cargando...</td>
              </tr>
            )}
            {!cargando && incidencias.length === 0 && (
              <tr>
                <td className="px-5 py-4 text-slate-400" colSpan={7}>
                  No hay incidencias para este filtro.
                </td>
              </tr>
            )}
            {incidencias.map((incidencia) => (
              <tr key={incidencia.id} className="border-t border-slate-100">
                <td className="px-5 py-2 whitespace-nowrap">{formatearFechaHora(incidencia.fecha_reporte)}</td>
                <td className="px-5 py-2">#{incidencia.equipo_id}</td>
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
                <td className="px-5 py-2">
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
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
