import { useCallback, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { visionApi } from '../../api/vision.js'
import CategoriaEquipoBadge from '../../components/CategoriaEquipoBadge.jsx'
import EstadoBadge from '../../components/EstadoBadge.jsx'
import PrioridadBadge from '../../components/PrioridadBadge.jsx'
import StatCard from '../../components/StatCard.jsx'
import { formatearFechaHora, formatearMonto } from '../../utils/formato.js'
import GraficoUsoDiario from './GraficoUsoDiario.jsx'
import { ChipVivo, FotoMaquina } from './UsoMaquinas.jsx'
import { formatearCronometro, formatearHoras, haceCuanto } from './uso.js'
import usePolling from './usePolling.js'

const ESTILO_SESION = {
  abierta: 'bg-blue-50 text-blue-700',
  cerrada: 'bg-slate-100 text-slate-700',
  descartada: 'bg-slate-50 text-slate-400 line-through',
}

function Tabla({ columnas, filas, vacio }) {
  if (filas.length === 0) return <p className="p-5 text-sm text-slate-500">{vacio}</p>
  return (
    <div className="overflow-x-auto">
      <table className="min-w-full text-sm">
        <thead className="text-left text-slate-500 bg-slate-50">
          <tr>
            {columnas.map((c) => (
              <th key={c} className="px-4 py-2.5 font-medium whitespace-nowrap">
                {c}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">{filas}</tbody>
      </table>
    </div>
  )
}

export default function UsoMaquinaDetalle() {
  const { id } = useParams()
  const [datos, setDatos] = useState(null)
  const [error, setError] = useState(null)
  const [pestana, setPestana] = useState('sesiones')
  const [versionFoto, setVersionFoto] = useState(Date.now())
  const [mensajeFoto, setMensajeFoto] = useState(null)

  const cargar = useCallback(
    () =>
      visionApi
        .obtenerMaquina(id)
        .then((d) => (setDatos(d), setError(null)))
        .catch((err) => setError(err.message)),
    [id],
  )

  usePolling(cargar, 10000, { clave: id })

  async function cambiarFoto(accion) {
    setMensajeFoto(null)
    try {
      await accion()
      setVersionFoto(Date.now())
      await cargar()
    } catch (err) {
      setMensajeFoto(err.message)
    }
  }

  if (error && !datos) return <p className="text-sm text-red-600">No se pudo cargar la máquina: {error}</p>
  if (!datos) return <p className="text-sm text-slate-500">Cargando…</p>

  const r = datos.resumen
  const camaras = Object.fromEntries(r.camaras.map((c) => [c.id, c.codigo]))
  const pestanas = [
    { clave: 'sesiones', etiqueta: 'Sesiones de uso', total: datos.sesiones.length },
    { clave: 'incidencias', etiqueta: 'Incidencias', total: datos.incidencias.length },
    { clave: 'mantenciones', etiqueta: 'Mantenciones', total: datos.mantenciones.length },
  ]

  return (
    <div className="space-y-6">
      <Link to="/uso" className="text-sm text-emerald-700 hover:underline">
        ← Uso de máquinas
      </Link>

      <div className="flex flex-col md:flex-row gap-6">
        <div className="md:w-72 shrink-0 space-y-2">
          <FotoMaquina
            maquina={{ ...r, foto_version: versionFoto }}
            key={versionFoto}
            className="w-full aspect-[4/3] rounded-lg border border-slate-200"
          />
          <div className="flex flex-wrap gap-2">
            <label className="cursor-pointer text-xs font-medium px-3 py-1.5 rounded-md border border-slate-300 bg-white hover:bg-slate-50">
              Subir foto
              <input
                type="file"
                accept="image/*"
                className="hidden"
                onChange={(e) => e.target.files[0] && cambiarFoto(() => visionApi.subirFoto(r.equipo_id, e.target.files[0]))}
              />
            </label>
            {r.medido_por_camara && (
              <button
                type="button"
                onClick={() => cambiarFoto(() => visionApi.fotoDesdeCamara(r.equipo_id))}
                className="text-xs font-medium px-3 py-1.5 rounded-md border border-slate-300 bg-white hover:bg-slate-50"
              >
                Tomar de la cámara
              </button>
            )}
          </div>
          {mensajeFoto && <p className="text-xs text-red-600">{mensajeFoto}</p>}
        </div>

        <div className="flex-1 space-y-3">
          <div>
            <h1 className="text-2xl font-bold text-slate-900">{r.nombre}</h1>
            <div className="flex flex-wrap items-center gap-2 mt-1 text-sm text-slate-500">
              <span>{r.codigo_activo}</span>
              <CategoriaEquipoBadge categoria={r.categoria} />
              {r.zona && <span>· Zona {r.zona}</span>}
              {(r.marca || r.modelo) && <span>· {[r.marca, r.modelo].filter(Boolean).join(' ')}</span>}
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            {r.estado_vivo ? (
              <ChipVivo estado={r.estado_vivo} />
            ) : (
              <span className="text-xs text-slate-400">
                {r.medido_por_camara ? 'Cámara sin señal en este momento' : 'Ninguna cámara mide esta máquina'}
              </span>
            )}
            {r.camaras.map((c) => (
              <Link key={c.id} to={`/camaras/${c.id}`} className="text-xs text-emerald-700 hover:underline">
                Ver cámara {c.codigo}
              </Link>
            ))}
          </div>
          <p className="text-sm text-slate-600">
            Último uso:{' '}
            <span className="font-medium">{r.en_uso_ahora ? 'ahora (sesión en curso)' : haceCuanto(r.ultima_sesion)}</span>
            {r.ultima_mantencion && (
              <>
                {' '}· Última mantención: <span className="font-medium">{formatearFechaHora(r.ultima_mantencion)}</span>
              </>
            )}
          </p>
          <Link to={`/equipos/${r.equipo_id}`} className="inline-block text-sm text-emerald-700 hover:underline">
            Ver ficha del equipo (QR, datos y estado) →
          </Link>
        </div>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-5 gap-4">
        <StatCard titulo="Uso total" valor={formatearHoras(r.horas_uso)} detalle="horómetro (cámara)" />
        <StatCard titulo="Últimos 7 días" valor={formatearHoras(r.horas_ultimos_7_dias)} />
        <StatCard
          titulo="Desde la última mantención"
          valor={r.horas_desde_mantencion == null ? '—' : formatearHoras(r.horas_desde_mantencion)}
          detalle={r.horas_desde_mantencion == null ? 'sin mantenciones registradas' : 'horas de uso acumuladas'}
        />
        <StatCard titulo="Sesiones" valor={r.sesiones} detalle="sesiones de uso cerradas" />
        <StatCard titulo="Incidencias abiertas" valor={r.incidencias_abiertas} />
      </div>

      <div className="bg-white rounded-lg border border-slate-200 shadow-sm p-5">
        <h2 className="font-semibold text-slate-900">Uso diario · últimos 30 días</h2>
        <p className="text-xs text-slate-500 mb-3">Horas de uso por día medidas por la cámara.</p>
        <GraficoUsoDiario dias={datos.uso_diario} />
      </div>

      <div className="bg-white rounded-lg border border-slate-200 shadow-sm overflow-hidden">
        <div className="flex border-b border-slate-200 overflow-x-auto">
          {pestanas.map((p) => (
            <button
              key={p.clave}
              type="button"
              onClick={() => setPestana(p.clave)}
              className={`px-4 py-3 text-sm font-medium whitespace-nowrap border-b-2 -mb-px ${
                pestana === p.clave
                  ? 'border-emerald-600 text-emerald-700'
                  : 'border-transparent text-slate-500 hover:text-slate-700'
              }`}
            >
              {p.etiqueta} <span className="text-slate-400">({p.total})</span>
            </button>
          ))}
        </div>

        {pestana === 'sesiones' && (
          <Tabla
            columnas={['Inicio', 'Fin', 'Duración', 'Estado', 'Origen', 'Confianza', 'Cámara']}
            vacio="Esta máquina todavía no tiene sesiones de uso registradas."
            filas={datos.sesiones.map((s) => (
              <tr key={s.id}>
                <td className="px-4 py-2.5 whitespace-nowrap">{formatearFechaHora(s.fecha_inicio)}</td>
                <td className="px-4 py-2.5 whitespace-nowrap">{s.fecha_fin ? formatearFechaHora(s.fecha_fin) : 'en curso'}</td>
                <td className="px-4 py-2.5 font-mono">
                  {s.estado === 'abierta' && r.estado_vivo?.sesion_s != null
                    ? formatearCronometro(r.estado_vivo.sesion_s)
                    : formatearCronometro(s.duracion_segundos)}
                </td>
                <td className="px-4 py-2.5">
                  <span className={`px-2 py-0.5 rounded-full text-xs font-semibold ${ESTILO_SESION[s.estado] || ''}`}>
                    {s.estado}
                  </span>
                </td>
                <td className="px-4 py-2.5 text-slate-500">{s.origen === 'ia' ? 'cámara' : s.origen}</td>
                <td className="px-4 py-2.5 text-slate-500">
                  {s.confianza_promedio == null ? '—' : `${Math.round(s.confianza_promedio * 100)} %`}
                </td>
                <td className="px-4 py-2.5 text-slate-500">{camaras[s.camara_id] || '—'}</td>
              </tr>
            ))}
          />
        )}

        {pestana === 'incidencias' && (
          <Tabla
            columnas={['Fecha', 'Tipo de falla', 'Prioridad', 'Estado', 'Origen', 'Reportó']}
            vacio="Sin incidencias registradas."
            filas={datos.incidencias.map((i) => (
              <tr key={i.id}>
                <td className="px-4 py-2.5 whitespace-nowrap">{formatearFechaHora(i.fecha_reporte)}</td>
                <td className="px-4 py-2.5">{i.tipo_falla || '—'}</td>
                <td className="px-4 py-2.5">
                  <PrioridadBadge prioridad={i.prioridad} />
                </td>
                <td className="px-4 py-2.5">
                  <EstadoBadge estado={i.estado} />
                </td>
                <td className="px-4 py-2.5 text-slate-500">{i.origen}</td>
                <td className="px-4 py-2.5 text-slate-500">{i.reportado_por || '—'}</td>
              </tr>
            ))}
          />
        )}

        {pestana === 'mantenciones' && (
          <Tabla
            columnas={['Fecha', 'Tipo', 'Técnico', 'Descripción', 'Costo']}
            vacio="Sin mantenciones registradas. Se registran desde la ficha del equipo."
            filas={datos.mantenciones.map((m) => (
              <tr key={m.id}>
                <td className="px-4 py-2.5 whitespace-nowrap">{formatearFechaHora(m.fecha_fin || m.fecha_inicio)}</td>
                <td className="px-4 py-2.5 capitalize">{m.tipo}</td>
                <td className="px-4 py-2.5">{m.tecnico || '—'}</td>
                <td className="px-4 py-2.5 text-slate-600">{m.descripcion}</td>
                <td className="px-4 py-2.5 whitespace-nowrap">{formatearMonto(m.costo_total)}</td>
              </tr>
            ))}
          />
        )}
      </div>
    </div>
  )
}
