import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api/client.js'
import CategoriaEquipoBadge from '../components/CategoriaEquipoBadge.jsx'
import EstadoVivoChip from '../components/EstadoVivoChip.jsx'
import Paginacion from '../components/Paginacion.jsx'
import StatCard from '../components/StatCard.jsx'
import { formatearFechaHora } from '../utils/formato.js'
import { usePaginacion } from '../utils/paginacion.js'
import { formatearHoras } from '../utils/vision.js'

const ORDENES = [
  { valor: 'horas_uso', etiqueta: 'Más horas de uso' },
  { valor: 'horas_ultimos_7_dias', etiqueta: 'Más uso en 7 días' },
  { valor: 'horas_desde_mantencion', etiqueta: 'Más horas desde la mantención' },
  { valor: 'nombre', etiqueta: 'Nombre' },
]

// Cada cuanto se vuelve a pedir el estado en vivo (los chips "En uso 04:39" se mueven solos).
const REFRESCO_MS = 5000

function TarjetaMaquina({ maquina }) {
  const [fotoFallo, setFotoFallo] = useState(false)

  return (
    <Link
      to={`/uso/${maquina.equipo_id}`}
      className="bg-white rounded-lg border border-slate-200 shadow-sm overflow-hidden hover:border-emerald-400 transition-colors flex flex-col"
    >
      <div className="relative aspect-video bg-slate-100">
        {maquina.tiene_foto && !fotoFallo ? (
          <img
            src={api.urlFotoMaquina(maquina.equipo_id)}
            alt={`Foto de ${maquina.nombre}`}
            onError={() => setFotoFallo(true)}
            className="w-full h-full object-cover"
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center text-xs text-slate-400">Sin foto</div>
        )}
        {maquina.estado_vivo && <EstadoVivoChip vivo={maquina.estado_vivo} className="absolute top-2 left-2 shadow" />}
      </div>

      <div className="p-4 flex-1 flex flex-col gap-3">
        <div>
          <div className="flex items-start justify-between gap-2">
            <h2 className="font-semibold text-slate-900 leading-tight">{maquina.nombre}</h2>
            <CategoriaEquipoBadge categoria={maquina.categoria} />
          </div>
          <p className="text-xs text-slate-400 font-mono mt-0.5">{maquina.codigo_activo}</p>
        </div>

        <div>
          <p className="text-3xl font-bold text-slate-900 leading-none">{formatearHoras(maquina.horas_uso)}</p>
          <p className="text-xs text-slate-400 mt-1">
            de uso total · {maquina.sesiones} sesion{maquina.sesiones === 1 ? '' : 'es'}
          </p>
        </div>

        <dl className="text-xs space-y-1 mt-auto">
          <div className="flex justify-between gap-2">
            <dt className="text-slate-400">Últimos 7 días</dt>
            <dd className="text-slate-700">{formatearHoras(maquina.horas_ultimos_7_dias)}</dd>
          </div>
          <div className="flex justify-between gap-2">
            <dt className="text-slate-400">Desde la última mantención</dt>
            <dd className="text-slate-700">
              {maquina.horas_desde_mantencion === null || maquina.horas_desde_mantencion === undefined
                ? 'Sin mantención'
                : formatearHoras(maquina.horas_desde_mantencion)}
            </dd>
          </div>
          <div className="flex justify-between gap-2">
            <dt className="text-slate-400">Último uso</dt>
            <dd className="text-slate-700">{formatearFechaHora(maquina.ultima_sesion)}</dd>
          </div>
          <div className="flex justify-between gap-2">
            <dt className="text-slate-400">Cámara</dt>
            <dd className="text-slate-700 text-right">
              {maquina.medido_por_camara ? maquina.camaras.map((c) => c.nombre).join(', ') || 'Sí' : 'No medida'}
            </dd>
          </div>
          {maquina.incidencias_abiertas > 0 && (
            <div className="flex justify-between gap-2">
              <dt className="text-slate-400">Incidencias abiertas</dt>
              <dd className="font-semibold text-amber-700">{maquina.incidencias_abiertas}</dd>
            </div>
          )}
        </dl>
      </div>
    </Link>
  )
}

// Uso de cada maquina segun las camaras: horometro, ultimos 7 dias, horas desde la ultima
// mantencion y estado en vivo. Base del mantenimiento preventivo por uso.
export default function UsoMaquinas() {
  const [maquinas, setMaquinas] = useState([])
  const [cargando, setCargando] = useState(true)
  const [error, setError] = useState(null)

  const [busqueda, setBusqueda] = useState('')
  const [orden, setOrden] = useState('horas_uso')
  const [soloMedidas, setSoloMedidas] = useState(false)

  useEffect(() => {
    let activo = true

    function cargar() {
      api
        .listarUsoMaquinas()
        .then((datos) => {
          if (!activo) return
          setMaquinas(datos)
          setError(null)
        })
        .catch((err) => activo && setError(err.message))
        .finally(() => activo && setCargando(false))
    }

    cargar()
    const temporizador = setInterval(cargar, REFRESCO_MS)
    return () => {
      activo = false
      clearInterval(temporizador)
    }
  }, [])

  const medidas = useMemo(() => maquinas.filter((m) => m.medido_por_camara), [maquinas])
  const enUsoAhora = useMemo(() => maquinas.filter((m) => m.en_uso_ahora), [maquinas])
  const horas7Dias = useMemo(() => maquinas.reduce((total, m) => total + (m.horas_ultimos_7_dias || 0), 0), [maquinas])
  const masUsada = useMemo(
    () => maquinas.reduce((mejor, m) => (m.horas_uso > (mejor?.horas_uso ?? 0) ? m : mejor), null),
    [maquinas]
  )

  const visibles = useMemo(() => {
    const texto = busqueda.trim().toLowerCase()
    const filtradas = maquinas.filter((m) => {
      if (soloMedidas && !m.medido_por_camara) return false
      if (!texto) return true
      return [m.nombre, m.codigo_activo, m.marca, m.modelo, m.zona].some((campo) =>
        (campo || '').toLowerCase().includes(texto)
      )
    })
    return filtradas.sort((a, b) => {
      if (orden === 'nombre') return a.nombre.localeCompare(b.nombre, 'es')
      // Las que nunca tuvieron mantencion (null) van al final del orden por horas desde mantencion.
      return (b[orden] ?? -1) - (a[orden] ?? -1)
    })
  }, [maquinas, busqueda, orden, soloMedidas])

  const paginacion = usePaginacion(visibles, 12, `${busqueda}|${orden}|${soloMedidas}`)

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-2">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Uso de máquinas</h1>
          <p className="text-sm text-slate-500">Tiempo de uso medido por las cámaras, máquina por máquina.</p>
        </div>
        <Link to="/camaras" className="text-sm font-medium text-emerald-700 hover:underline">
          Ver cámaras →
        </Link>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          titulo="Máquinas medidas"
          valor={`${medidas.length} / ${maquinas.length}`}
          detalle="Con una cámara que las mira"
        />
        <StatCard
          titulo="En uso ahora"
          valor={enUsoAhora.length}
          detalle={enUsoAhora.length > 0 ? enUsoAhora.map((m) => m.nombre).join(', ') : 'Ninguna en este momento'}
        />
        <StatCard titulo="Uso últimos 7 días" valor={formatearHoras(horas7Dias)} detalle="Entre todas las máquinas" />
        <StatCard
          titulo="Más usada"
          valor={masUsada && masUsada.horas_uso > 0 ? masUsada.nombre : '—'}
          detalle={masUsada && masUsada.horas_uso > 0 ? `${formatearHoras(masUsada.horas_uso)} de uso total` : 'Aún sin sesiones'}
        />
      </div>

      {error && <p className="text-red-600 text-sm">{error}</p>}

      <div className="bg-white rounded-lg border border-slate-200 shadow-sm p-4 flex flex-wrap gap-2 items-center">
        <input
          type="text"
          value={busqueda}
          onChange={(e) => setBusqueda(e.target.value)}
          placeholder="Buscar por nombre, código, marca, zona..."
          className="flex-1 min-w-[200px] border border-slate-300 rounded-md px-3 py-1.5 text-sm"
        />
        <select
          value={orden}
          onChange={(e) => setOrden(e.target.value)}
          className="border border-slate-300 rounded-md text-sm px-2.5 py-1.5"
          aria-label="Ordenar por"
        >
          {ORDENES.map((o) => (
            <option key={o.valor} value={o.valor}>
              {o.etiqueta}
            </option>
          ))}
        </select>
        <label className="text-sm text-slate-600 flex items-center gap-2">
          <input type="checkbox" checked={soloMedidas} onChange={(e) => setSoloMedidas(e.target.checked)} />
          Solo medidas por cámara
        </label>
      </div>

      {cargando && <p className="text-slate-500">Cargando...</p>}
      {!cargando && visibles.length === 0 && (
        <p className="text-slate-400 text-sm">
          {maquinas.length === 0
            ? 'Todavía no hay máquinas registradas.'
            : 'Ninguna máquina coincide con estos filtros.'}
        </p>
      )}

      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">
        {paginacion.visibles.map((maquina) => (
          <TarjetaMaquina key={maquina.equipo_id} maquina={maquina} />
        ))}
      </div>

      {paginacion.total > paginacion.porPagina && (
        <div className="bg-white rounded-lg border border-slate-200 shadow-sm">
          <Paginacion paginacion={paginacion} />
        </div>
      )}
    </div>
  )
}
