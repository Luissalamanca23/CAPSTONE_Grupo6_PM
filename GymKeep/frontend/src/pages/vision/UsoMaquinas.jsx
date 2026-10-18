import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { visionApi } from '../../api/vision.js'
import CategoriaEquipoBadge from '../../components/CategoriaEquipoBadge.jsx'
import StatCard from '../../components/StatCard.jsx'
import { ESTADOS_VIVO, formatearHoras, haceCuanto, textoEstadoVivo } from './uso.js'
import usePolling from './usePolling.js'

const ORDENES = {
  horas: { etiqueta: 'Más horas de uso', comparar: (a, b) => b.horas_uso - a.horas_uso },
  semana: { etiqueta: 'Más uso en 7 días', comparar: (a, b) => b.horas_ultimos_7_dias - a.horas_ultimos_7_dias },
  mantencion: {
    etiqueta: 'Más horas desde mantención',
    comparar: (a, b) => (b.horas_desde_mantencion ?? b.horas_uso) - (a.horas_desde_mantencion ?? a.horas_uso),
  },
  nombre: { etiqueta: 'Nombre', comparar: (a, b) => a.nombre.localeCompare(b.nombre) },
}

export function FotoMaquina({ maquina, className = '' }) {
  const [fallo, setFallo] = useState(false)
  if (!maquina.tiene_foto || fallo) {
    return (
      <div className={`flex flex-col items-center justify-center bg-slate-100 text-slate-400 ${className}`}>
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="w-10 h-10">
          <path d="M3 7h3l2-3h8l2 3h3v13H3z" />
          <circle cx="12" cy="13" r="4" />
        </svg>
        <span className="text-xs mt-1">Sin foto</span>
      </div>
    )
  }
  return (
    <img
      src={visionApi.urlFoto(maquina.equipo_id, maquina.foto_version || '')}
      alt={`Foto de ${maquina.nombre}`}
      onError={() => setFallo(true)}
      className={`object-cover bg-slate-100 ${className}`}
    />
  )
}

export function ChipVivo({ estado }) {
  if (!estado) return null
  const estilo = ESTADOS_VIVO[estado.estado] || ESTADOS_VIVO.libre
  const activo = estado.estado === 'en_uso' || estado.estado === 'candidata'
  return (
    <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold ${estilo.chip}`}>
      <span className="relative flex w-2 h-2">
        {activo && <span className={`absolute inline-flex h-full w-full rounded-full opacity-60 animate-ping ${estilo.punto}`} />}
        <span className={`relative inline-flex rounded-full w-2 h-2 ${estilo.punto}`} />
      </span>
      {textoEstadoVivo(estado)}
    </span>
  )
}

function TarjetaMaquina({ maquina }) {
  return (
    <Link
      to={`/uso/${maquina.equipo_id}`}
      className="group bg-white rounded-lg border border-slate-200 shadow-sm overflow-hidden hover:border-brand-400 hover:shadow transition"
    >
      <div className="relative">
        <FotoMaquina maquina={maquina} className="w-full aspect-[4/3]" />
        <div className="absolute top-2 left-2">
          <ChipVivo estado={maquina.estado_vivo} />
        </div>
      </div>
      <div className="p-4 space-y-3">
        <div>
          <p className="font-semibold text-slate-900 group-hover:text-brand-700">{maquina.nombre}</p>
          <div className="flex items-center gap-2 mt-1">
            <span className="text-xs text-slate-500">{maquina.codigo_activo}</span>
            <CategoriaEquipoBadge categoria={maquina.categoria} />
          </div>
        </div>
        <div>
          <p className="text-2xl font-bold text-slate-900">{formatearHoras(maquina.horas_uso)}</p>
          <p className="text-xs text-slate-500">
            de uso total · {maquina.sesiones} {maquina.sesiones === 1 ? 'sesión' : 'sesiones'}
          </p>
        </div>
        <dl className="grid grid-cols-2 gap-x-3 gap-y-1 text-xs">
          <dt className="text-slate-500">Últimos 7 días</dt>
          <dd className="text-slate-800 text-right">{formatearHoras(maquina.horas_ultimos_7_dias)}</dd>
          <dt className="text-slate-500">Desde mantención</dt>
          <dd className="text-slate-800 text-right">
            {maquina.horas_desde_mantencion == null ? 'Sin registro' : formatearHoras(maquina.horas_desde_mantencion)}
          </dd>
          <dt className="text-slate-500">Último uso</dt>
          <dd className="text-slate-800 text-right">{haceCuanto(maquina.ultima_sesion)}</dd>
        </dl>
        <div className="flex items-center justify-between pt-2 border-t border-slate-100 text-xs">
          {maquina.medido_por_camara ? (
            <span className="text-slate-500">Cámara {maquina.camaras.map((c) => c.codigo).join(', ')}</span>
          ) : (
            <span className="text-slate-400">Sin cámara (no medido)</span>
          )}
          {maquina.incidencias_abiertas > 0 && (
            <span className="px-2 py-0.5 rounded-full bg-orange-100 text-orange-700 font-semibold">
              {maquina.incidencias_abiertas} incidencia{maquina.incidencias_abiertas > 1 ? 's' : ''}
            </span>
          )}
        </div>
      </div>
    </Link>
  )
}

export default function UsoMaquinas() {
  const [maquinas, setMaquinas] = useState(null)
  const [error, setError] = useState(null)
  const [busqueda, setBusqueda] = useState('')
  const [orden, setOrden] = useState('horas')
  const [soloMedidas, setSoloMedidas] = useState(false)

  // El estado "en uso ahora" cambia segundo a segundo: se refresca solo.
  usePolling(
    (vigente) =>
      visionApi
        .listarMaquinas()
        .then((datos) => vigente() && (setMaquinas(datos), setError(null)))
        .catch((err) => vigente() && setError(err.message)),
    5000,
  )

  const visibles = useMemo(() => {
    if (!maquinas) return []
    const texto = busqueda.trim().toLowerCase()
    return maquinas
      .filter((m) => !soloMedidas || m.medido_por_camara)
      .filter((m) => !texto || `${m.nombre} ${m.codigo_activo} ${m.zona || ''}`.toLowerCase().includes(texto))
      .sort(ORDENES[orden].comparar)
  }, [maquinas, busqueda, orden, soloMedidas])

  const totales = useMemo(() => {
    if (!maquinas) return null
    const medidas = maquinas.filter((m) => m.medido_por_camara)
    const masUsada = [...maquinas].sort(ORDENES.semana.comparar)[0]
    return {
      medidas: medidas.length,
      enUso: maquinas.filter((m) => m.en_uso_ahora).length,
      semana: maquinas.reduce((suma, m) => suma + m.horas_ultimos_7_dias, 0),
      masUsada: masUsada && masUsada.horas_ultimos_7_dias > 0 ? masUsada : null,
    }
  }, [maquinas])

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Uso de máquinas</h1>
        <p className="text-sm text-slate-500">
          Tiempo de uso medido por las cámaras (horómetro) e historial de cada máquina.
        </p>
      </div>

      {error && <p className="text-sm text-red-600">No se pudo cargar el uso de las máquinas: {error}</p>}

      {totales && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <StatCard
            titulo="Medidas por cámara"
            valor={`${totales.medidas} de ${maquinas.length}`}
            detalle="máquinas con zona definida en una cámara"
          />
          <StatCard titulo="En uso ahora" valor={totales.enUso} detalle="según las cámaras en línea" />
          <StatCard titulo="Uso últimos 7 días" valor={formatearHoras(totales.semana)} detalle="suma de todas las máquinas" />
          <StatCard
            titulo="Más usada (7 días)"
            valor={totales.masUsada ? formatearHoras(totales.masUsada.horas_ultimos_7_dias) : '—'}
            detalle={totales.masUsada ? totales.masUsada.nombre : 'sin uso registrado'}
          />
        </div>
      )}

      <div className="flex flex-col sm:flex-row sm:items-center gap-3">
        <input
          type="search"
          value={busqueda}
          onChange={(e) => setBusqueda(e.target.value)}
          placeholder="Buscar por nombre, código o zona"
          className="w-full sm:w-72 rounded-lg border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
        />
        <select
          value={orden}
          onChange={(e) => setOrden(e.target.value)}
          className="rounded-lg border border-slate-300 px-3 py-2 text-sm bg-white"
        >
          {Object.entries(ORDENES).map(([clave, o]) => (
            <option key={clave} value={clave}>
              Ordenar: {o.etiqueta}
            </option>
          ))}
        </select>
        <label className="inline-flex items-center gap-2 text-sm text-slate-600">
          <input type="checkbox" checked={soloMedidas} onChange={(e) => setSoloMedidas(e.target.checked)} />
          Solo medidas por cámara
        </label>
      </div>

      {maquinas === null && !error && <p className="text-sm text-slate-500">Cargando…</p>}
      {maquinas && visibles.length === 0 && (
        <p className="text-sm text-slate-500">No hay máquinas que coincidan con la búsqueda.</p>
      )}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
        {visibles.map((m) => (
          <TarjetaMaquina key={m.equipo_id} maquina={m} />
        ))}
      </div>
    </div>
  )
}
