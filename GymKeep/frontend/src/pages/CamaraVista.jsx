import { useEffect, useMemo, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '../api/client.js'
import { CATEGORIAS_EQUIPO } from '../components/CategoriaEquipoBadge.jsx'
import EstadoVivoChip from '../components/EstadoVivoChip.jsx'
import Paginacion from '../components/Paginacion.jsx'
import { usePaginacion } from '../utils/paginacion.js'
import { ESTADOS_VIVO, formatearHace, textoEstadoVivo } from '../utils/vision.js'

const REFRESCO_VIVO_MS = 1000
const REFRESCO_SIN_SENAL_MS = 5000
// Distancia (en px) al primer punto a la que un clic cierra el poligono que se esta dibujando.
const RADIO_CIERRE_PX = 14

const limitar = (valor) => Math.min(1, Math.max(0, valor))

function centro(puntos) {
  const suma = puntos.reduce((acc, [x, y]) => [acc[0] + x, acc[1] + y], [0, 0])
  return [suma[0] / puntos.length, suma[1] / puntos.length]
}

function abreviar(texto, largo = 14) {
  return texto.length > largo ? `${texto.slice(0, largo - 1)}…` : texto
}

const PARAMETROS_CAMPOS = [
  { campo: 't_on_s', etiqueta: 'T_on (s)', ayuda: 'Presencia continua necesaria para abrir una sesión de uso.', min: 1, max: 600, paso: 1 },
  { campo: 't_off_s', etiqueta: 'T_off (s)', ayuda: 'Ausencia continua para cerrarla. Debe superar el descanso entre series.', min: 1, max: 1800, paso: 1 },
  { campo: 'confianza_min', etiqueta: 'Confianza mínima', ayuda: 'Confianza de la detección (0,05 a 0,95). Bájala si la cámara es de baja resolución.', min: 0.05, max: 0.95, paso: 0.05 },
  { campo: 'gracia_s', etiqueta: 'Gracia (s)', ayuda: 'Huecos de detección que no cuentan como ausencia. Menor que T_off.', min: 0, max: 60, paso: 1 },
  { campo: 'escala_tiempo', etiqueta: 'Escala de tiempo', ayuda: 'Segundos reales por segundo de video (1 en una cámara en vivo).', min: 0.1, max: 10, paso: 0.1 },
]

export default function CamaraVista() {
  const { id } = useParams()
  const contenedor = useRef(null)
  const inputImagen = useRef(null)

  const [detalle, setDetalle] = useState(null)
  const [vivo, setVivo] = useState(null)
  const [imagenSrc, setImagenSrc] = useState(null)
  const [streamFalla, setStreamFalla] = useState(false)
  const [cargando, setCargando] = useState(true)
  const [error, setError] = useState(null)
  const [aviso, setAviso] = useState(null)

  // Edicion de zonas: 'ver' | 'dibujar' | 'editar'. `puntos` es la copia de trabajo.
  const [modo, setModo] = useState('ver')
  const [puntos, setPuntos] = useState([])
  const [cerrada, setCerrada] = useState(false)
  const [equipoDestino, setEquipoDestino] = useState(null) // maquina a la que se le dibuja la zona (null = nueva)
  const [arrastre, setArrastre] = useState(null)
  const [guardando, setGuardando] = useState(false)
  const [confirmarQuitar, setConfirmarQuitar] = useState(null)

  const [equiposSucursal, setEquiposSucursal] = useState([])
  const [asignacion, setAsignacion] = useState({ tipo: 'existente', equipoId: '', nombre: '', codigo: '', categoria: '' })

  const [parametros, setParametros] = useState(null)

  function cargarDetalle({ conParametros = false } = {}) {
    return api
      .obtenerCamara(id)
      .then((datos) => {
        setDetalle(datos)
        if (conParametros) setParametros({ ...datos.parametros })
        if (datos.tiene_cuadro) setImagenSrc((actual) => actual || api.urlCuadroCamara(id, Date.now()))
        setError(null)
        return datos
      })
      .catch((err) => setError(err.message))
      .finally(() => setCargando(false))
  }

  useEffect(() => {
    setCargando(true)
    setImagenSrc(null)
    setStreamFalla(false)
    cargarDetalle({ conParametros: true })
  }, [id])

  // Estado en vivo: cada 1 s si el pipeline esta enviando datos, y cada 5 s si no.
  const enLinea = Boolean(vivo?.en_linea)
  useEffect(() => {
    let activo = true
    function consultar() {
      api
        .obtenerVivo(id)
        .then((datos) => activo && setVivo(datos))
        .catch(() => {})
    }
    consultar()
    const temporizador = setInterval(consultar, enLinea ? REFRESCO_VIVO_MS : REFRESCO_SIN_SENAL_MS)
    return () => {
      activo = false
      clearInterval(temporizador)
    }
  }, [id, enLinea])

  // Con el pipeline enviando y sin editar zonas, la imagen es el video en vivo (MJPEG, un solo
  // <img> que el navegador va renovando). Al dibujar/editar la imagen se queda quieta, y si el
  // stream falla se vuelve a pedir un cuadro por vez (abajo).
  const transmitiendo = enLinea && Boolean(vivo?.cuadro_timestamp) && modo === 'ver' && !streamFalla

  // Fuera del stream, cada cuadro nuevo se precarga antes de mostrarlo, para que no parpadee.
  const marcaCuadro = vivo?.cuadro_timestamp ? new Date(vivo.cuadro_timestamp).getTime() : null
  useEffect(() => {
    if (!marcaCuadro || transmitiendo) return
    const url = api.urlCuadroCamara(id, marcaCuadro)
    const imagen = new Image()
    imagen.onload = () => setImagenSrc(url)
    imagen.src = url
  }, [id, marcaCuadro, transmitiendo])

  // Las maquinas de la sucursal se piden la primera vez que se necesitan (al cerrar una zona nueva).
  async function cargarEquiposSucursal() {
    if (!detalle || equiposSucursal.length > 0) return
    try {
      setEquiposSucursal(await api.listarEquipos(detalle.sucursal_id))
    } catch (err) {
      setAviso({ tipo: 'error', texto: err.message })
    }
  }

  const vivoPorEquipo = useMemo(() => {
    const mapa = new Map()
    for (const m of vivo?.maquinas || []) mapa.set(m.equipo_id, m)
    return mapa
  }, [vivo])

  const maquinas = detalle?.lista_maquinas || []
  // Solo la lista lateral se pagina; la imagen siempre dibuja las zonas de TODAS las maquinas.
  const paginacionMaquinas = usePaginacion(maquinas, 8, id)
  const conZona = maquinas.filter((m) => m.roi && m.roi.length >= 3)
  const equiposDisponibles = equiposSucursal.filter((eq) => !conZona.some((m) => m.equipo_id === eq.id))

  function puntoDesdeEvento(evento) {
    const caja = contenedor.current.getBoundingClientRect()
    return [
      Math.round(limitar((evento.clientX - caja.left) / caja.width) * 10000) / 10000,
      Math.round(limitar((evento.clientY - caja.top) / caja.height) * 10000) / 10000,
    ]
  }

  function empezarDibujo(equipo = null) {
    setModo('dibujar')
    setPuntos([])
    setCerrada(false)
    setEquipoDestino(equipo)
    setConfirmarQuitar(null)
    setAviso(null)
  }

  function empezarEdicion(maquina) {
    setModo('editar')
    setPuntos(maquina.roi.map(([x, y]) => [x, y]))
    setCerrada(true)
    setEquipoDestino(maquina)
    setConfirmarQuitar(null)
    setAviso(null)
  }

  function cancelarEdicion() {
    setModo('ver')
    setPuntos([])
    setCerrada(false)
    setEquipoDestino(null)
    setArrastre(null)
  }

  function cerrarPoligono() {
    if (puntos.length < 3) return
    setCerrada(true)
    if (!equipoDestino) cargarEquiposSucursal()
  }

  function clicEnImagen(evento) {
    if (modo !== 'dibujar' || cerrada) return
    const nuevo = puntoDesdeEvento(evento)
    if (puntos.length >= 3) {
      const caja = contenedor.current.getBoundingClientRect()
      const dx = (nuevo[0] - puntos[0][0]) * caja.width
      const dy = (nuevo[1] - puntos[0][1]) * caja.height
      if (Math.hypot(dx, dy) <= RADIO_CIERRE_PX) {
        cerrarPoligono()
        return
      }
    }
    if (puntos.length >= 40) {
      setAviso({ tipo: 'error', texto: 'Una zona admite hasta 40 puntos.' })
      return
    }
    setPuntos([...puntos, nuevo])
  }

  async function guardarZona() {
    if (puntos.length < 3) return
    setGuardando(true)
    setAviso(null)
    try {
      let equipoId = equipoDestino?.equipo_id
      if (!equipoId) {
        if (asignacion.tipo === 'existente') {
          if (!asignacion.equipoId) throw new Error('Elige la máquina a la que corresponde esta zona.')
          equipoId = Number(asignacion.equipoId)
        } else {
          if (!asignacion.nombre.trim() || !asignacion.codigo.trim()) {
            throw new Error('Para crear la máquina indica su nombre y su código de activo.')
          }
          const creado = await api.crearEquipo({
            codigo_activo: asignacion.codigo.trim(),
            nombre: asignacion.nombre.trim(),
            categoria: asignacion.categoria || null,
            sucursal_id: detalle.sucursal_id,
          })
          equipoId = creado.id
          setEquiposSucursal((lista) => [...lista, creado])
        }
      }
      await api.guardarZona(id, equipoId, puntos)
      await cargarDetalle()
      cancelarEdicion()
      setAsignacion({ tipo: 'existente', equipoId: '', nombre: '', codigo: '', categoria: '' })
      setAviso({ tipo: 'ok', texto: 'Zona guardada. El pipeline la aplica en unos segundos, sin reiniciarse.' })
    } catch (err) {
      setAviso({ tipo: 'error', texto: err.message })
    } finally {
      setGuardando(false)
    }
  }

  async function quitarZona(equipoId) {
    setAviso(null)
    try {
      await api.quitarZona(id, equipoId)
      setConfirmarQuitar(null)
      await cargarDetalle()
      setAviso({ tipo: 'ok', texto: 'Máquina quitada de esta cámara. El equipo sigue en el inventario.' })
    } catch (err) {
      setAviso({ tipo: 'error', texto: err.message })
    }
  }

  async function guardarParametros(evento) {
    evento.preventDefault()
    setAviso(null)
    try {
      const numeros = Object.fromEntries(Object.entries(parametros).map(([clave, valor]) => [clave, Number(valor)]))
      const guardados = await api.guardarParametrosCamara(id, numeros)
      setParametros({ ...guardados })
      setAviso({ tipo: 'ok', texto: 'Parámetros guardados.' })
    } catch (err) {
      setAviso({ tipo: 'error', texto: err.message })
    }
  }

  async function subirImagen(evento) {
    const archivo = evento.target.files?.[0]
    evento.target.value = ''
    if (!archivo) return
    setAviso(null)
    try {
      await api.subirCuadroCamara(id, archivo)
      setImagenSrc(api.urlCuadroCamara(id, Date.now()))
      await cargarDetalle()
      setAviso({ tipo: 'ok', texto: 'Imagen de referencia subida. Ya puedes dibujar las zonas.' })
    } catch (err) {
      setAviso({ tipo: 'error', texto: err.message })
    }
  }

  if (cargando && !detalle) return <p className="text-slate-500">Cargando...</p>
  if (error && !detalle) return <p className="text-red-600">{error}</p>
  if (!detalle) return null

  const editando = modo !== 'ver'
  const comandoPipeline = `VISION_CAMARA=${detalle.codigo} VISION_FUENTE=rtsp://usuario:clave@ip/stream \\\n  docker compose -f docker-compose.yml -f docker-compose.vision.yml up -d --build vision`

  return (
    <div className="space-y-6">
      <div>
        <Link to="/camaras" className="text-sm text-emerald-700 font-medium">
          ← Volver a cámaras
        </Link>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">{detalle.nombre}</h1>
          <p className="text-xs text-slate-400 font-mono">{detalle.codigo}</p>
        </div>
        {enLinea ? (
          <span className="inline-block px-3 py-1 rounded-full text-xs font-semibold bg-emerald-100 text-emerald-700">
            En línea
            {vivo.fps_analisis != null ? ` · ${vivo.fps_analisis.toFixed(1)} fps` : ''}
            {vivo.latencia_ms != null ? ` · ${Math.round(vivo.latencia_ms)} ms` : ''}
          </span>
        ) : (
          <span className="inline-block px-3 py-1 rounded-full text-xs font-semibold bg-slate-200 text-slate-600">
            Sin señal · {formatearHace(vivo?.edad_s)}
          </span>
        )}
      </div>

      {aviso && (
        <p className={`text-sm ${aviso.tipo === 'ok' ? 'text-emerald-700' : 'text-red-600'}`} role="status">
          {aviso.texto}
        </p>
      )}

      <div className="flex flex-col xl:flex-row gap-6">
        <div className="flex-1 min-w-0 space-y-3">
          <div
            ref={contenedor}
            onClick={clicEnImagen}
            className={`relative bg-slate-900 rounded-lg overflow-hidden select-none ${
              modo === 'dibujar' && !cerrada ? 'cursor-crosshair' : ''
            }`}
          >
            {transmitiendo || imagenSrc ? (
              <img
                src={transmitiendo ? api.urlStreamCamara(id) : imagenSrc}
                onError={() => transmitiendo && setStreamFalla(true)}
                alt={`Imagen de ${detalle.nombre}`}
                draggable={false}
                className="block w-full h-auto"
              />
            ) : (
              <div className="aspect-video flex flex-col items-center justify-center gap-3 text-center px-6">
                <p className="text-sm text-slate-300">Esta cámara todavía no tiene imagen.</p>
                <p className="text-xs text-slate-400">
                  Sube una imagen de referencia para dibujar las zonas, o inicia el pipeline para ver la cámara en vivo.
                </p>
              </div>
            )}

            {/* Zonas, personas y poligono en edicion: coordenadas normalizadas 0..1 sobre la imagen. */}
            <svg viewBox="0 0 100 100" preserveAspectRatio="none" className="absolute inset-0 w-full h-full pointer-events-none">
              {conZona.map((maquina) => {
                if (modo === 'editar' && equipoDestino?.equipo_id === maquina.equipo_id) return null
                const estado = vivoPorEquipo.get(maquina.equipo_id)?.estado || 'libre'
                const estilo = ESTADOS_VIVO[estado] || ESTADOS_VIVO.libre
                return (
                  <polygon
                    key={maquina.equipo_id}
                    points={maquina.roi.map(([x, y]) => `${x * 100},${y * 100}`).join(' ')}
                    fill={estilo.relleno}
                    stroke={estilo.borde}
                    strokeWidth="2"
                    vectorEffect="non-scaling-stroke"
                  />
                )
              })}

              {!editando &&
                (vivo?.personas || []).map((persona, i) => {
                  const [x1, y1, x2, y2] = persona.caja
                  return (
                    <rect
                      key={`${persona.track_id ?? 'p'}-${i}`}
                      x={x1 * 100}
                      y={y1 * 100}
                      width={(x2 - x1) * 100}
                      height={(y2 - y1) * 100}
                      fill="none"
                      stroke={persona.equipo_id ? '#f8fafc' : '#94a3b8'}
                      strokeWidth="1.5"
                      strokeDasharray={persona.equipo_id ? undefined : '4 3'}
                      vectorEffect="non-scaling-stroke"
                    />
                  )
                })}

              {editando && puntos.length >= 2 && (
                <>
                  {cerrada && puntos.length >= 3 ? (
                    <polygon
                      points={puntos.map(([x, y]) => `${x * 100},${y * 100}`).join(' ')}
                      fill="rgba(16,185,129,0.25)"
                      stroke="#10b981"
                      strokeWidth="2"
                      vectorEffect="non-scaling-stroke"
                    />
                  ) : (
                    <polyline
                      points={puntos.map(([x, y]) => `${x * 100},${y * 100}`).join(' ')}
                      fill="none"
                      stroke="#10b981"
                      strokeWidth="2"
                      strokeDasharray="5 4"
                      vectorEffect="non-scaling-stroke"
                    />
                  )}
                </>
              )}
            </svg>

            {/* Rotulos y cronometros (HTML, para que el texto no se deforme con la imagen). */}
            {!editando &&
              conZona.map((maquina) => {
                const [cx, cy] = centro(maquina.roi)
                const estadoVivo = vivoPorEquipo.get(maquina.equipo_id)
                const texto = estadoVivo && estadoVivo.estado !== 'libre' ? textoEstadoVivo(estadoVivo) : null
                return (
                  <div
                    key={maquina.equipo_id}
                    className="absolute -translate-x-1/2 -translate-y-1/2 pointer-events-none text-center leading-tight max-w-[40%]"
                    style={{ left: `${cx * 100}%`, top: `${cy * 100}%` }}
                  >
                    <span className="inline-block bg-slate-900/75 text-white text-[10px] sm:text-xs font-medium rounded px-1.5 py-0.5">
                      {abreviar(maquina.nombre)}
                    </span>
                    {texto && (
                      <span className="block mt-0.5 bg-white/90 text-slate-900 text-[10px] sm:text-xs font-semibold rounded px-1.5 py-0.5">
                        {texto}
                      </span>
                    )}
                  </div>
                )
              })}

            {/* Puntos del poligono en edicion. Al editar se arrastran; al dibujar solo se muestran. */}
            {editando &&
              puntos.map(([x, y], i) => (
                <div
                  key={i}
                  onClick={(e) => e.stopPropagation()}
                  onPointerDown={(e) => {
                    if (modo !== 'editar') return
                    e.stopPropagation()
                    e.currentTarget.setPointerCapture(e.pointerId)
                    setArrastre(i)
                  }}
                  onPointerMove={(e) => {
                    if (arrastre !== i) return
                    const nuevo = puntoDesdeEvento(e)
                    setPuntos((lista) => lista.map((p, j) => (j === i ? nuevo : p)))
                  }}
                  onPointerUp={(e) => {
                    if (arrastre !== i) return
                    e.currentTarget.releasePointerCapture(e.pointerId)
                    setArrastre(null)
                  }}
                  onDoubleClick={() => {
                    if (modo === 'editar' && puntos.length > 3) setPuntos((lista) => lista.filter((_, j) => j !== i))
                  }}
                  style={{ left: `${x * 100}%`, top: `${y * 100}%`, touchAction: 'none' }}
                  className={`absolute w-4 h-4 -ml-2 -mt-2 rounded-full border-2 border-emerald-600 ${
                    i === 0 ? 'bg-emerald-300' : 'bg-white'
                  } ${modo === 'editar' ? 'cursor-move' : 'pointer-events-none'}`}
                />
              ))}
          </div>

          {/* Barra de acciones de edicion */}
          {editando && (
            <div className="bg-white rounded-lg border border-slate-200 shadow-sm p-4 space-y-3">
              {modo === 'dibujar' && !cerrada && (
                <>
                  <p className="text-sm text-slate-600">
                    Haz clic en la imagen para marcar los puntos de la zona (donde apoya los pies quien usa la máquina).
                    Se cierra al volver a hacer clic en el primer punto (verde) o con el botón. Puntos: {puntos.length}
                  </p>
                  <div className="flex flex-wrap gap-2">
                    <button
                      type="button"
                      onClick={cerrarPoligono}
                      disabled={puntos.length < 3}
                      className="bg-emerald-600 hover:bg-emerald-700 text-white text-sm font-medium rounded-md px-4 py-1.5 disabled:opacity-50"
                    >
                      Cerrar zona
                    </button>
                    <button
                      type="button"
                      onClick={() => setPuntos((lista) => lista.slice(0, -1))}
                      disabled={puntos.length === 0}
                      className="text-sm font-medium border border-slate-300 rounded-md px-3 py-1.5 hover:bg-slate-50 disabled:opacity-50"
                    >
                      Deshacer último punto
                    </button>
                    <button type="button" onClick={cancelarEdicion} className="text-sm font-medium text-slate-500 underline px-2">
                      Cancelar
                    </button>
                  </div>
                </>
              )}

              {cerrada && (
                <>
                  {modo === 'editar' && (
                    <p className="text-sm text-slate-600">
                      Editando la zona de <strong>{equipoDestino?.nombre}</strong>. Arrastra los puntos para ajustarla; doble clic en un punto lo quita.
                    </p>
                  )}

                  {modo === 'dibujar' && !equipoDestino && (
                    <div className="space-y-3">
                      <p className="text-sm text-slate-600">¿A qué máquina corresponde esta zona?</p>
                      <div className="flex gap-4 text-sm">
                        <label className="flex items-center gap-1.5">
                          <input
                            type="radio"
                            name="tipo-asignacion"
                            checked={asignacion.tipo === 'existente'}
                            onChange={() => setAsignacion({ ...asignacion, tipo: 'existente' })}
                          />
                          Una máquina existente
                        </label>
                        <label className="flex items-center gap-1.5">
                          <input
                            type="radio"
                            name="tipo-asignacion"
                            checked={asignacion.tipo === 'nueva'}
                            onChange={() => setAsignacion({ ...asignacion, tipo: 'nueva' })}
                          />
                          Crear una máquina nueva
                        </label>
                      </div>

                      {asignacion.tipo === 'existente' ? (
                        <select
                          id="zona-equipo"
                          value={asignacion.equipoId}
                          onChange={(e) => setAsignacion({ ...asignacion, equipoId: e.target.value })}
                          className="border border-slate-300 rounded-md text-sm px-2.5 py-1.5 w-full sm:w-auto"
                        >
                          <option value="">Elegir máquina...</option>
                          {equiposDisponibles.map((eq) => (
                            <option key={eq.id} value={eq.id}>
                              {eq.nombre} ({eq.codigo_activo})
                            </option>
                          ))}
                        </select>
                      ) : (
                        <div className="grid gap-2 sm:grid-cols-3">
                          <input
                            id="zona-nombre"
                            value={asignacion.nombre}
                            onChange={(e) => setAsignacion({ ...asignacion, nombre: e.target.value })}
                            placeholder="Nombre (Trotadora 02)"
                            className="border border-slate-300 rounded-md px-3 py-1.5 text-sm"
                          />
                          <input
                            id="zona-codigo"
                            value={asignacion.codigo}
                            onChange={(e) => setAsignacion({ ...asignacion, codigo: e.target.value })}
                            placeholder="Código de activo (EQ-0010)"
                            className="border border-slate-300 rounded-md px-3 py-1.5 text-sm"
                          />
                          <select
                            id="zona-categoria"
                            value={asignacion.categoria}
                            onChange={(e) => setAsignacion({ ...asignacion, categoria: e.target.value })}
                            className="border border-slate-300 rounded-md text-sm px-2.5 py-1.5"
                          >
                            <option value="">Categoría...</option>
                            {CATEGORIAS_EQUIPO.map((c) => (
                              <option key={c.valor} value={c.valor}>
                                {c.etiqueta}
                              </option>
                            ))}
                          </select>
                        </div>
                      )}
                    </div>
                  )}

                  {modo === 'dibujar' && equipoDestino && (
                    <p className="text-sm text-slate-600">
                      Zona para <strong>{equipoDestino.nombre}</strong>. Guárdala o vuelve a dibujarla.
                    </p>
                  )}

                  <div className="flex flex-wrap gap-2">
                    <button
                      type="button"
                      onClick={guardarZona}
                      disabled={guardando}
                      className="bg-emerald-600 hover:bg-emerald-700 text-white text-sm font-medium rounded-md px-4 py-1.5 disabled:opacity-50"
                    >
                      {guardando ? 'Guardando...' : 'Guardar zona'}
                    </button>
                    {modo === 'dibujar' && (
                      <button
                        type="button"
                        onClick={() => {
                          setPuntos([])
                          setCerrada(false)
                        }}
                        className="text-sm font-medium border border-slate-300 rounded-md px-3 py-1.5 hover:bg-slate-50"
                      >
                        Volver a dibujar
                      </button>
                    )}
                    <button type="button" onClick={cancelarEdicion} className="text-sm font-medium text-slate-500 underline px-2">
                      Cancelar
                    </button>
                  </div>
                </>
              )}
            </div>
          )}

          {!enLinea && (
            <div className="bg-white rounded-lg border border-slate-200 shadow-sm p-4 space-y-2">
              <p className="text-sm text-slate-600">
                El pipeline de visión no está enviando datos de esta cámara. Para iniciarlo, desde la carpeta <code>GymKeep</code>:
              </p>
              <pre className="bg-slate-900 text-slate-100 text-xs rounded-md p-3 overflow-x-auto">{comandoPipeline}</pre>
              <p className="text-xs text-slate-400">
                Para probar sin cámara, usa un video en <code>vision/datos/</code> (ver <code>vision/INTEGRACION.md</code>).
              </p>
            </div>
          )}
        </div>

        <div className="xl:w-96 shrink-0 space-y-4">
          <div className="bg-white rounded-lg border border-slate-200 shadow-sm">
            <div className="px-5 py-4 border-b border-slate-200 flex items-center justify-between gap-2">
              <h2 className="font-semibold text-slate-800">Máquinas de esta cámara</h2>
              <button
                type="button"
                onClick={() => empezarDibujo()}
                disabled={!imagenSrc || editando}
                title={imagenSrc ? undefined : 'Primero sube una imagen de referencia.'}
                className="text-xs font-medium bg-emerald-600 hover:bg-emerald-700 text-white rounded-md px-3 py-1.5 disabled:opacity-50"
              >
                Agregar máquina
              </button>
            </div>

            <ul className="divide-y divide-slate-100">
              {maquinas.length === 0 && (
                <li className="px-5 py-4 text-sm text-slate-400">Todavía no hay máquinas en esta cámara.</li>
              )}
              {paginacionMaquinas.visibles.map((maquina) => {
                const tieneZona = maquina.roi && maquina.roi.length >= 3
                return (
                  <li key={maquina.equipo_id} className="px-5 py-3 space-y-2">
                    <div className="flex items-start justify-between gap-2">
                      <div className="min-w-0">
                        <p className="text-sm font-medium text-slate-900 truncate">{maquina.nombre}</p>
                        <p className="text-xs text-slate-400 font-mono">{maquina.codigo_activo}</p>
                      </div>
                      {tieneZona ? (
                        <EstadoVivoChip vivo={vivoPorEquipo.get(maquina.equipo_id) || { estado: 'libre' }} />
                      ) : (
                        <span className="text-xs text-amber-700 font-medium">Sin zona</span>
                      )}
                    </div>

                    <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs font-medium">
                      {tieneZona ? (
                        <button
                          type="button"
                          onClick={() => empezarEdicion(maquina)}
                          disabled={editando}
                          className="text-emerald-700 hover:underline disabled:opacity-50"
                        >
                          Editar zona
                        </button>
                      ) : (
                        <button
                          type="button"
                          onClick={() => empezarDibujo(maquina)}
                          disabled={!imagenSrc || editando}
                          className="text-emerald-700 hover:underline disabled:opacity-50"
                        >
                          Dibujar zona
                        </button>
                      )}
                      <Link to={`/uso/${maquina.equipo_id}`} className="text-slate-600 hover:underline">
                        Historial
                      </Link>
                      {confirmarQuitar === maquina.equipo_id ? (
                        <span className="flex items-center gap-2 text-slate-600">
                          ¿Quitar de esta cámara?
                          <button type="button" onClick={() => quitarZona(maquina.equipo_id)} className="text-red-600 hover:underline">
                            Sí, quitar
                          </button>
                          <button type="button" onClick={() => setConfirmarQuitar(null)} className="text-slate-500 hover:underline">
                            No
                          </button>
                        </span>
                      ) : (
                        <button
                          type="button"
                          onClick={() => setConfirmarQuitar(maquina.equipo_id)}
                          disabled={editando}
                          className="text-slate-400 hover:text-red-600 disabled:opacity-50"
                        >
                          Quitar
                        </button>
                      )}
                    </div>
                  </li>
                )
              })}
            </ul>
            <Paginacion paginacion={paginacionMaquinas} />
          </div>

          <div className="bg-white rounded-lg border border-slate-200 shadow-sm p-5 space-y-3">
            <h2 className="font-semibold text-slate-800">Imagen de referencia</h2>
            <p className="text-xs text-slate-500">
              Sirve para dibujar las zonas antes de tener el pipeline corriendo. Cuando la cámara está en línea, la imagen se
              actualiza sola.
            </p>
            <input ref={inputImagen} type="file" accept="image/jpeg,image/png" onChange={subirImagen} className="hidden" />
            <button
              type="button"
              onClick={() => inputImagen.current?.click()}
              className="text-xs font-medium border border-slate-300 rounded-md px-3 py-1.5 hover:bg-slate-50"
            >
              Subir imagen
            </button>
          </div>

          {parametros && (
            <form onSubmit={guardarParametros} className="bg-white rounded-lg border border-slate-200 shadow-sm p-5 space-y-3">
              <h2 className="font-semibold text-slate-800">Parámetros de detección</h2>
              {PARAMETROS_CAMPOS.map((p) => (
                <label key={p.campo} className="block text-sm text-slate-600">
                  {p.etiqueta}
                  <input
                    id={`parametro-${p.campo}`}
                    type="number"
                    min={p.min}
                    max={p.max}
                    step={p.paso}
                    required
                    value={parametros[p.campo]}
                    onChange={(e) => setParametros({ ...parametros, [p.campo]: e.target.value })}
                    className="mt-1 w-full border border-slate-300 rounded-md px-3 py-1.5 text-sm"
                  />
                  <span className="block text-xs text-slate-400 mt-0.5">{p.ayuda}</span>
                </label>
              ))}
              <button type="submit" className="bg-slate-900 hover:bg-slate-800 text-white text-sm font-medium rounded-md px-4 py-2">
                Guardar parámetros
              </button>
            </form>
          )}
        </div>
      </div>
    </div>
  )
}
