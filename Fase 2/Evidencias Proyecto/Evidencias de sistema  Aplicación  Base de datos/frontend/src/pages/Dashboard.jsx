import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api/client.js'
import EstadoBadge from '../components/EstadoBadge.jsx'
import PrioridadBadge from '../components/PrioridadBadge.jsx'
import TipoFallaBadge from '../components/TipoFallaBadge.jsx'
import StatCard from '../components/StatCard.jsx'
import { formatearFechaHora } from '../utils/formato.js'

const ORDEN_PRIORIDAD = { urgente: 4, alta: 3, media: 2, baja: 1 }

export default function Dashboard() {
  const [equipos, setEquipos] = useState([])
  const [incidencias, setIncidencias] = useState([])
  const [cargando, setCargando] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    Promise.all([api.listarEquipos(), api.listarIncidencias()])
      .then(([equiposData, incidenciasData]) => {
        setEquipos(equiposData)
        setIncidencias(incidenciasData)
      })
      .catch((err) => setError(err.message))
      .finally(() => setCargando(false))
  }, [])

  if (cargando) return <p className="text-slate-500">Cargando panel...</p>
  if (error) return <p className="text-red-600">Error al cargar datos: {error}</p>

  const pendientes = incidencias.filter((i) => i.estado === 'pendiente')
  const enProceso = incidencias.filter((i) => i.estado === 'en_proceso')
  const fueraDeServicio = equipos.filter((e) => e.estado === 'fuera_de_servicio')

  const urgentes = incidencias
    .filter((i) => i.estado !== 'resuelta' && i.estado !== 'descartada')
    .sort((a, b) => (ORDEN_PRIORIDAD[b.prioridad] ?? 0) - (ORDEN_PRIORIDAD[a.prioridad] ?? 0))
    .slice(0, 6)

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
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
            className="text-sm font-medium bg-emerald-600 text-white rounded-md px-3 py-1.5 hover:bg-emerald-700"
          >
            Ver todas las incidencias
          </Link>
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard titulo="Equipos registrados" valor={equipos.length} />
        <StatCard titulo="Incidencias pendientes" valor={pendientes.length} />
        <StatCard titulo="En proceso" valor={enProceso.length} />
        <StatCard titulo="Equipos fuera de servicio" valor={fueraDeServicio.length} />
      </div>

      <div className="bg-white rounded-lg border border-slate-200 shadow-sm">
        <div className="px-5 py-4 border-b border-slate-200">
          <h2 className="font-semibold text-slate-800">
            Incidencias por atender (ordenadas por prioridad)
          </h2>
        </div>
        <table className="w-full text-sm">
          <thead className="text-left text-slate-500 bg-slate-50">
            <tr>
              <th className="px-5 py-2">Fecha y hora</th>
              <th className="px-5 py-2">Equipo</th>
              <th className="px-5 py-2">Tipo de falla</th>
              <th className="px-5 py-2">Prioridad</th>
              <th className="px-5 py-2">Estado</th>
            </tr>
          </thead>
          <tbody>
            {urgentes.map((incidencia) => (
              <tr key={incidencia.id} className="border-t border-slate-100">
                <td className="px-5 py-2 whitespace-nowrap">{formatearFechaHora(incidencia.fecha_reporte)}</td>
                <td className="px-5 py-2">
                  <Link to={`/equipos/${incidencia.equipo_id}`} className="text-emerald-700 hover:underline">
                    #{incidencia.equipo_id}
                  </Link>
                </td>
                <td className="px-5 py-2">
                  <TipoFallaBadge tipoFalla={incidencia.tipo_falla} />
                </td>
                <td className="px-5 py-2">
                  <PrioridadBadge prioridad={incidencia.prioridad} />
                </td>
                <td className="px-5 py-2">
                  <EstadoBadge estado={incidencia.estado} />
                </td>
              </tr>
            ))}
            {urgentes.length === 0 && (
              <tr>
                <td className="px-5 py-4 text-slate-400" colSpan={5}>
                  No hay incidencias pendientes.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
