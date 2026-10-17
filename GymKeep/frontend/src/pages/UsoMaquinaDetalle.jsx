import { useEffect, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '../api/client.js'
import CategoriaEquipoBadge from '../components/CategoriaEquipoBadge.jsx'
import EstadoBadge from '../components/EstadoBadge.jsx'
import EstadoVivoChip from '../components/EstadoVivoChip.jsx'
import PrioridadBadge from '../components/PrioridadBadge.jsx'
import Paginacion from '../components/Paginacion.jsx'
import StatCard from '../components/StatCard.jsx'
import { formatearFechaHora, formatearMonto } from '../utils/formato.js'
import { usePaginacion } from '../utils/paginacion.js'
import { formatearDuracion, formatearHoras } from '../utils/vision.js'

const REFRESCO_MS = 5000

// Grafico de barras de las horas de uso por dia (ultimos 30 dias), dibujado en SVG.
function GraficoUsoDiario({ datos }) {
  const ancho = 720
  const alto = 190
  const margen = { izq: 38, der: 8, arriba: 10, abajo: 24 }
  const areaAncho = ancho - margen.izq - margen.der
  const areaAlto = alto - margen.arriba - margen.abajo

  const maximo = Math.max(1, ...datos.map((d) => d.horas))
  // Tope "redondo" del eje para que las marcas queden en numeros agradables.
  const tope = Math.ceil(maximo)
  const marcas = [0, tope / 2, tope]
  const anchoBarra = areaAncho / Math.max(datos.length, 1)

  return (
    <svg viewBox={`0 0 ${ancho} ${alto}`} className="w-full h-auto" role="img" aria-label="Horas de uso por día, últimos 30 días">
      {marcas.map((marca) => {
        const y = margen.arriba + areaAlto - (marca / tope) * areaAlto
        return (
          <g key={marca}>
            <line x1={margen.izq} x2={ancho - margen.der} y1={y} y2={y} stroke="#e2e8f0" strokeWidth="1" />
            <text x={margen.izq - 6} y={y + 4} textAnchor="end" fontSize="11" fill="#94a3b8">
              {Number.isInteger(marca) ? marca : marca.toFixed(1)} h
            </text>
          </g>
        )
      })}

      {datos.map((dia, i) => {
        const alturaBarra = (dia.horas / tope) * areaAlto
        const x = margen.izq + i * anchoBarra + anchoBarra * 0.15
        const y = margen.arriba + areaAlto - alturaBarra
        const fecha = new Date(`${dia.fecha}T00:00:00`)
        return (
          <g key={dia.fecha}>
            <rect
              x={x}
              y={dia.horas > 0 ? y : margen.arriba + areaAlto - 1}
              width={anchoBarra * 0.7}
              height={dia.horas > 0 ? alturaBarra : 1}
              rx="2"
              fill={dia.horas > 0 ? '#10b981' : '#cbd5e1'}
            >
              <title>
                {fecha.toLocaleDateString('es-CL')} · {formatearHoras(dia.horas)} · {dia.sesiones} sesion
                {dia.sesiones === 1 ? '' : 'es'}
              </title>
            </rect>
            {i % 5 === 0 && (
              <text x={x + anchoBarra * 0.35} y={alto - 8} textAnchor="middle" fontSize="11" fill="#94a3b8">
                {fecha.toLocaleDateString('es-CL', { day: '2-digit', month: '2-digit' })}
              </text>
            )}
          </g>
        )
      })}
    </svg>
  )
}

const PESTANAS = [
  { valor: 'sesiones', etiqueta: 'Sesiones de uso' },
  { valor: 'incidencias', etiqueta: 'Incidencias' },
  { valor: 'mantenciones', etiqueta: 'Mantenciones' },
]

function Vacio({ children }) {
  return (
    <tr>
      <td className="px-5 py-4 text-slate-400" colSpan={6}>
        {children}
      </td>
    </tr>
  )
}

export default function UsoMaquinaDetalle() {
  const { id } = useParams()
  const [detalle, setDetalle] = useState(null)
  const [cargando, setCargando] = useState(true)
  const [error, setError] = useState(null)
  const [pestana, setPestana] = useState('sesiones')

  const [fotoMarca, setFotoMarca] = useState(() => Date.now())
  const [fotoFallo, setFotoFallo] = useState(false)
  const [fotoNueva, setFotoNueva] = useState(false)
  const [ocupado, setOcupado] = useState(false)
  const [avisoFoto, setAvisoFoto] = useState(null)
  const inputFoto = useRef(null)

  // Un paginador por pestana (los hooks van antes de los return anticipados de mas abajo).
  const paginacionSesiones = usePaginacion(detalle?.sesiones || [], 10, id)
  const paginacionIncidencias = usePaginacion(detalle?.incidencias || [], 10, id)
  const paginacionMantenciones = usePaginacion(detalle?.mantenciones || [], 10, id)

  useEffect(() => {
    let activo = true

    function cargar() {
      api
        .obtenerUsoMaquina(id)
        .then((datos) => {
          if (!activo) return
          setDetalle(datos)
          setError(null)
        })
        .catch((err) => activo && setError(err.message))
        .finally(() => activo && setCargando(false))
    }

    setCargando(true)
    cargar()
    const temporizador = setInterval(cargar, REFRESCO_MS)
    return () => {
      activo = false
      clearInterval(temporizador)
    }
  }, [id])

  async function subirFoto(evento) {
    const archivo = evento.target.files?.[0]
    evento.target.value = ''
    if (!archivo) return
    setOcupado(true)
    setAvisoFoto(null)
    try {
      await api.subirFotoMaquina(id, archivo)
      setFotoFallo(false)
      setFotoNueva(true)
      setFotoMarca(Date.now())
      setAvisoFoto({ tipo: 'ok', texto: 'Foto actualizada.' })
    } catch (err) {
      setAvisoFoto({ tipo: 'error', texto: err.message })
    } finally {
      setOcupado(false)
    }
  }

  async function tomarDeCamara() {
    setOcupado(true)
    setAvisoFoto(null)
    try {
      await api.fotoMaquinaDesdeCamara(id)
      setFotoFallo(false)
      setFotoNueva(true)
      setFotoMarca(Date.now())
      setAvisoFoto({ tipo: 'ok', texto: 'Foto tomada de la cámara.' })
    } catch (err) {
      setAvisoFoto({ tipo: 'error', texto: err.message })
    } finally {
      setOcupado(false)
    }
  }

  if (cargando && !detalle) return <p className="text-slate-500">Cargando...</p>
  if (error && !detalle) return <p className="text-red-600">{error}</p>
  if (!detalle) return null

  const { resumen, uso_diario: usoDiario, sesiones, incidencias, mantenciones } = detalle
  const vivo = resumen.estado_vivo
  const mostrarFoto = !fotoFallo && (resumen.tiene_foto || fotoNueva)

  return (
    <div className="space-y-6">
      <div>
        <Link to="/uso" className="text-sm text-emerald-700 font-medium">
          ← Volver a uso de máquinas
        </Link>
      </div>

      <div className="flex flex-col lg:flex-row gap-6">
        <div className="bg-white rounded-lg border border-slate-200 shadow-sm p-5 lg:w-80 shrink-0 space-y-4">
          <div className="relative aspect-video bg-slate-100 rounded-md overflow-hidden">
            {mostrarFoto ? (
              <img
                src={api.urlFotoMaquina(resumen.equipo_id, fotoMarca)}
                alt={`Foto de ${resumen.nombre}`}
                onError={() => setFotoFallo(true)}
                className="w-full h-full object-cover"
              />
            ) : (
              <div className="w-full h-full flex items-center justify-center text-xs text-slate-400">Sin foto</div>
            )}
          </div>

          <div className="flex flex-wrap gap-2">
            <input ref={inputFoto} type="file" accept="image/jpeg,image/png" onChange={subirFoto} className="hidden" />
            <button
              type="button"
              onClick={() => inputFoto.current?.click()}
              disabled={ocupado}
              className="text-xs font-medium border border-slate-300 rounded-md px-3 py-1.5 hover:bg-slate-50 disabled:opacity-50"
            >
              Subir foto
            </button>
            <button
              type="button"
              onClick={tomarDeCamara}
              disabled={ocupado || !resumen.medido_por_camara}
              title={resumen.medido_por_camara ? undefined : 'La máquina no tiene una zona en ninguna cámara.'}
              className="text-xs font-medium border border-slate-300 rounded-md px-3 py-1.5 hover:bg-slate-50 disabled:opacity-50"
            >
              Tomar de la cámara
            </button>
          </div>
          {avisoFoto && (
            <p className={`text-xs ${avisoFoto.tipo === 'ok' ? 'text-emerald-700' : 'text-red-600'}`}>{avisoFoto.texto}</p>
          )}

          <div>
            <h1 className="text-xl font-bold text-slate-900">{resumen.nombre}</h1>
            <p className="text-sm text-slate-500">
              {[resumen.marca, resumen.modelo].filter(Boolean).join(' · ') || 'Sin marca/modelo'}
              {resumen.zona ? ` · ${resumen.zona}` : ''}
            </p>
            <div className="mt-2 flex flex-wrap items-center gap-2">
              <EstadoBadge estado={resumen.estado} />
              <CategoriaEquipoBadge categoria={resumen.categoria} />
              {vivo && <EstadoVivoChip vivo={vivo} />}
            </div>
          </div>

          <dl className="text-sm space-y-1">
            <div className="flex justify-between gap-2">
              <dt className="text-slate-400">Código de activo</dt>
              <dd className="font-mono text-xs">{resumen.codigo_activo}</dd>
            </div>
            <div className="flex justify-between gap-2">
              <dt className="text-slate-400">Cámara</dt>
              <dd className="text-right">
                {resumen.camaras.length === 0
                  ? 'No medida'
                  : resumen.camaras.map((camara, i) => (
                      <span key={camara.id}>
                        {i > 0 && ', '}
                        <Link to={`/camaras/${camara.id}`} className="text-emerald-700 hover:underline">
                          {camara.nombre}
                        </Link>
                      </span>
                    ))}
              </dd>
            </div>
          </dl>

          <Link to={`/equipos/${resumen.equipo_id}`} className="inline-block text-sm font-medium text-emerald-700 hover:underline">
            Ver ficha del equipo (QR, costos) →
          </Link>
        </div>

        <div className="flex-1 min-w-0 space-y-4">
          <div className="grid grid-cols-2 xl:grid-cols-4 gap-4">
            <StatCard titulo="Uso total" valor={formatearHoras(resumen.horas_uso)} detalle="Horómetro" />
            <StatCard titulo="Últimos 7 días" valor={formatearHoras(resumen.horas_ultimos_7_dias)} />
            <StatCard
              titulo="Desde la mantención"
              valor={
                resumen.horas_desde_mantencion === null || resumen.horas_desde_mantencion === undefined
                  ? '—'
                  : formatearHoras(resumen.horas_desde_mantencion)
              }
              detalle={
                resumen.ultima_mantencion
                  ? `Última: ${formatearFechaHora(resumen.ultima_mantencion)}`
                  : 'Nunca tuvo una mantención'
              }
            />
            <StatCard
              titulo="Sesiones"
              valor={resumen.sesiones}
              detalle={`${resumen.incidencias_abiertas} incidencia${resumen.incidencias_abiertas === 1 ? '' : 's'} abierta${
                resumen.incidencias_abiertas === 1 ? '' : 's'
              }`}
            />
          </div>

          <div className="bg-white rounded-lg border border-slate-200 shadow-sm p-5">
            <h2 className="font-semibold text-slate-800 mb-2">Horas de uso por día (últimos 30 días)</h2>
            <GraficoUsoDiario datos={usoDiario} />
          </div>
        </div>
      </div>

      <div className="bg-white rounded-lg border border-slate-200 shadow-sm overflow-hidden">
        <div className="flex gap-1 border-b border-slate-200 px-3 pt-2 overflow-x-auto">
          {PESTANAS.map((p) => (
            <button
              key={p.valor}
              type="button"
              onClick={() => setPestana(p.valor)}
              className={`px-4 py-2 text-sm font-medium whitespace-nowrap border-b-2 -mb-px ${
                pestana === p.valor
                  ? 'border-emerald-600 text-emerald-700'
                  : 'border-transparent text-slate-500 hover:text-slate-700'
              }`}
            >
              {p.etiqueta}
            </button>
          ))}
        </div>

        <div className="overflow-auto max-h-[50vh]">
          {pestana === 'sesiones' && (
            <table className="w-full text-sm">
              <thead className="text-left text-slate-500 bg-slate-50 sticky top-0 z-10">
                <tr>
                  <th className="px-5 py-2">Inicio</th>
                  <th className="px-5 py-2">Fin</th>
                  <th className="px-5 py-2">Duración</th>
                  <th className="px-5 py-2">Estado</th>
                  <th className="px-5 py-2">Confianza</th>
                </tr>
              </thead>
              <tbody>
                {sesiones.length === 0 && <Vacio>Todavía no hay sesiones de uso registradas.</Vacio>}
                {paginacionSesiones.visibles.map((sesion) => {
                  const abierta = sesion.estado === 'abierta'
                  return (
                    <tr key={sesion.id} className="border-t border-slate-100">
                      <td className="px-5 py-2 whitespace-nowrap">{formatearFechaHora(sesion.fecha_inicio)}</td>
                      <td className="px-5 py-2 whitespace-nowrap">{abierta ? 'En curso' : formatearFechaHora(sesion.fecha_fin)}</td>
                      <td className="px-5 py-2 whitespace-nowrap">
                        {abierta && vivo?.sesion_s != null
                          ? formatearDuracion(vivo.sesion_s)
                          : formatearDuracion(sesion.duracion_segundos)}
                      </td>
                      <td className="px-5 py-2 capitalize">{sesion.estado}</td>
                      <td className="px-5 py-2">
                        {sesion.confianza_promedio != null ? `${Math.round(sesion.confianza_promedio * 100)} %` : '—'}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          )}

          {pestana === 'incidencias' && (
            <table className="w-full text-sm">
              <thead className="text-left text-slate-500 bg-slate-50 sticky top-0 z-10">
                <tr>
                  <th className="px-5 py-2">Fecha y hora</th>
                  <th className="px-5 py-2">Tipo de falla</th>
                  <th className="px-5 py-2">Reportado por</th>
                  <th className="px-5 py-2">Prioridad</th>
                  <th className="px-5 py-2">Estado</th>
                </tr>
              </thead>
              <tbody>
                {incidencias.length === 0 && <Vacio>Esta máquina no tiene incidencias.</Vacio>}
                {paginacionIncidencias.visibles.map((incidencia) => (
                  <tr key={incidencia.id} className="border-t border-slate-100">
                    <td className="px-5 py-2 whitespace-nowrap">{formatearFechaHora(incidencia.fecha_reporte)}</td>
                    <td className="px-5 py-2">{incidencia.tipo_falla || '—'}</td>
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
          )}

          {pestana === 'mantenciones' && (
            <table className="w-full text-sm">
              <thead className="text-left text-slate-500 bg-slate-50 sticky top-0 z-10">
                <tr>
                  <th className="px-5 py-2">Fecha</th>
                  <th className="px-5 py-2">Tipo</th>
                  <th className="px-5 py-2">Técnico</th>
                  <th className="px-5 py-2">Qué se hizo</th>
                  <th className="px-5 py-2">Costo</th>
                </tr>
              </thead>
              <tbody>
                {mantenciones.length === 0 && <Vacio>Esta máquina no tiene mantenciones registradas.</Vacio>}
                {paginacionMantenciones.visibles.map((m) => (
                  <tr key={m.id} className="border-t border-slate-100">
                    <td className="px-5 py-2 whitespace-nowrap">{formatearFechaHora(m.fecha_fin || m.fecha_inicio)}</td>
                    <td className="px-5 py-2 capitalize">{m.tipo}</td>
                    <td className="px-5 py-2">{m.tecnico || '—'}</td>
                    <td className="px-5 py-2 text-slate-600">{m.descripcion}</td>
                    <td className="px-5 py-2 whitespace-nowrap font-medium">{formatearMonto(m.costo_total)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        {pestana === 'sesiones' && <Paginacion paginacion={paginacionSesiones} />}
        {pestana === 'incidencias' && <Paginacion paginacion={paginacionIncidencias} />}
        {pestana === 'mantenciones' && <Paginacion paginacion={paginacionMantenciones} />}
      </div>
    </div>
  )
}
