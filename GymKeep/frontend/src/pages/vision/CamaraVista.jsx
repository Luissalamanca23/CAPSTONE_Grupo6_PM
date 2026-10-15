import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '../../api/client.js'
import { visionApi } from '../../api/vision.js'
import { CATEGORIAS_EQUIPO } from '../../components/CategoriaEquipoBadge.jsx'
import { ChipSenal } from './Camaras.jsx'
import PinDialogo from './PinDialogo.jsx'
import { ESTADOS_VIVO, textoEstadoVivo } from './uso.js'

const COLOR_SIN_DATO = '#94a3b8'
const COLOR_EDICION = '#f97316'

// Ultimo cuadro de la camara, precargado antes de mostrarlo (asi no parpadea al refrescar).
function useCuadro(camaraId, enVivo, version) {
  const [url, setUrl] = useState(null)
  useEffect(() => {
    let vigente = true
    const cargar = () => {
      const siguiente = visionApi.urlCuadro(camaraId)
      const imagen = new Image()
      imagen.onload = () => vigente && setUrl(siguiente)
      imagen.src = siguiente
    }
    cargar()
    const temporizador = enVivo ? setInterval(cargar, 1500) : null
    return () => {
      vigente = false
      if (temporizador) clearInterval(temporizador)
    }
  }, [camaraId, enVivo, version])
  return url
}

const aPuntos = (puntos) => puntos.map(([x, y]) => `${x * 100},${y * 100}`).join(' ')

// 'Trotadora 03' -> 'Trot. 03' cuando hay muchas zonas juntas (el nombre completo va en la lista).
function nombreCorto(nombre, abreviar) {
  const partes = nombre.split(' ')
  const ultima = partes[partes.length - 1]
  return abreviar && partes.length > 1 && /^\d+$/.test(ultima) ? `${partes[0].slice(0, 4)}. ${ultima}` : nombre
}

// Rotulo pegado a la esquina superior de la zona, sin salirse de la imagen.
function posicionRotulo(roi) {
  const xs = roi.map((p) => p[0])
  const ys = roi.map((p) => p[1])
  const estilo = {}
  if (Math.min(...xs) > 0.6) estilo.right = `${(1 - Math.max(...xs)) * 100}%`
  else estilo.left = `${Math.min(...xs) * 100}%`
  const arriba = Math.min(...ys)
  estilo.top = `${arriba * 100}%`
  return { estilo, adentro: arriba < 0.08 }
}

function Escenario({ url, maquinas, personas, vivoPorEquipo, modo, puntos, setPuntos, editando, onCerrarPoligono }) {
  const ref = useRef(null)
  const [arrastrando, setArrastrando] = useState(null)

  const posicion = (e) => {
    const caja = ref.current.getBoundingClientRect()
    const limitar = (v) => Math.min(1, Math.max(0, v))
    return [limitar((e.clientX - caja.left) / caja.width), limitar((e.clientY - caja.top) / caja.height)]
  }

  function alHacerClic(e) {
    if (modo !== 'dibujar' || arrastrando !== null) return
    const [x, y] = posicion(e)
    if (puntos.length >= 3) {
      const caja = ref.current.getBoundingClientRect()
      const [x0, y0] = puntos[0]
      if (Math.hypot((x - x0) * caja.width, (y - y0) * caja.height) < 12) return onCerrarPoligono()
    }
    setPuntos([...puntos, [x, y]])
  }

  function alMover(e) {
    if (arrastrando === null) return
    const nuevo = [...puntos]
    nuevo[arrastrando] = posicion(e)
    setPuntos(nuevo)
  }

  const editable = modo === 'dibujar' || modo === 'editar'
  return (
    <div
      ref={ref}
      onClick={alHacerClic}
      onPointerMove={alMover}
      onPointerUp={() => setTimeout(() => setArrastrando(null), 0)}
      className={`relative select-none rounded-lg overflow-hidden bg-slate-900 ${modo === 'dibujar' ? 'cursor-crosshair' : ''}`}
    >
      {url ? (
        <img src={url} alt="Imagen de la cámara" draggable={false} className="w-full h-auto block" />
      ) : (
        <div className="aspect-video flex items-center justify-center text-sm text-slate-400 px-6 text-center">
          Esta cámara todavía no tiene imagen. Inicia el pipeline de visión o sube una imagen de referencia.
        </div>
      )}

      <svg className="absolute inset-0 w-full h-full pointer-events-none" viewBox="0 0 100 100" preserveAspectRatio="none">
        {maquinas
          .filter((m) => m.roi && m.equipo_id !== editando)
          .map((m) => {
            const color = ESTADOS_VIVO[vivoPorEquipo[m.equipo_id]?.estado]?.relleno || COLOR_SIN_DATO
            return (
              <polygon
                key={m.equipo_id}
                points={aPuntos(m.roi)}
                fill={color}
                fillOpacity="0.22"
                stroke={color}
                strokeWidth="2"
                vectorEffect="non-scaling-stroke"
              />
            )
          })}
        {personas.map((p, i) => (
          <rect
            key={i}
            x={p.caja[0] * 100}
            y={p.caja[1] * 100}
            width={(p.caja[2] - p.caja[0]) * 100}
            height={(p.caja[3] - p.caja[1]) * 100}
            fill="none"
            stroke={p.equipo_id ? '#ffffff' : '#cbd5e1'}
            strokeWidth={p.equipo_id ? 2 : 1}
            strokeDasharray={p.equipo_id ? '' : '4 3'}
            vectorEffect="non-scaling-stroke"
          />
        ))}
        {editable && puntos.length > 0 && (
          <polygon
            points={aPuntos(puntos)}
            fill={COLOR_EDICION}
            fillOpacity={puntos.length >= 3 ? 0.25 : 0}
            stroke={COLOR_EDICION}
            strokeWidth="2"
            strokeDasharray={modo === 'dibujar' ? '6 4' : ''}
            vectorEffect="non-scaling-stroke"
          />
        )}
      </svg>

      {/* Rotulos de cada zona con el estado en vivo (HTML: se leen bien a cualquier tamano). */}
      {maquinas
        .filter((m) => m.roi && m.equipo_id !== editando)
        .map((m, _, conZona) => {
          const vivo = vivoPorEquipo[m.equipo_id]
          const { estilo, adentro } = posicionRotulo(m.roi)
          return (
            <div
              key={m.equipo_id}
              title={m.nombre}
              className={`absolute pointer-events-none px-1.5 py-0.5 rounded text-[11px] font-semibold text-white whitespace-nowrap shadow ${
                adentro ? '' : '-translate-y-full'
              }`}
              style={{ ...estilo, backgroundColor: ESTADOS_VIVO[vivo?.estado]?.relleno || COLOR_SIN_DATO }}
            >
              {nombreCorto(m.nombre, conZona.length > 2)}
              {vivo && ` · ${textoEstadoVivo(vivo)}`}
            </div>
          )
        })}

      {editable &&
        puntos.map(([x, y], i) => (
          <div
            key={i}
            onPointerDown={(e) => {
              e.stopPropagation()
              ref.current.setPointerCapture(e.pointerId)
              setArrastrando(i)
            }}
            onClick={(e) => {
              e.stopPropagation()
              if (modo === 'dibujar' && i === 0 && puntos.length >= 3) onCerrarPoligono()
            }}
            className={`absolute w-3.5 h-3.5 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-white shadow cursor-move ${
              i === 0 && modo === 'dibujar' ? 'bg-emerald-500' : 'bg-orange-500'
            }`}
            style={{ left: `${x * 100}%`, top: `${y * 100}%` }}
          />
        ))}
    </div>
  )
}

function Parametros({ camara, onGuardado }) {
  const [valores, setValores] = useState(camara.parametros)
  const [mensaje, setMensaje] = useState(null)
  useEffect(() => setValores(camara.parametros), [camara.parametros])

  const campos = [
    ['t_on_s', 'T_on (s)', 'Presencia continua para abrir una sesión.', 1],
    ['t_off_s', 'T_off (s)', 'Ausencia continua para cerrarla (mayor al descanso entre series).', 1],
    ['confianza_min', 'Confianza mínima', 'Bajarla solo en cámaras de baja resolución.', 0.05],
    ['gracia_s', 'Gracia (s)', 'Huecos de detección que no cuentan como ausencia.', 1],
    ['escala_tiempo', 'Escala de tiempo', 'Segundos reales por segundo de video (1 en vivo).', 0.001],
  ]

  async function guardar(e) {
    e.preventDefault()
    try {
      const numeros = Object.fromEntries(Object.entries(valores).map(([k, v]) => [k, Number(v)]))
      await visionApi.guardarParametros(camara.id, numeros)
      setMensaje({ ok: true, texto: 'Guardado. El pipeline lo aplica en unos segundos.' })
      onGuardado()
    } catch (err) {
      setMensaje({ ok: false, texto: err.message })
    }
  }

  return (
    <form onSubmit={guardar} className="space-y-3">
      {campos.map(([clave, etiqueta, ayuda, paso]) => (
        <label key={clave} className="block text-sm">
          <span className="flex items-center justify-between text-slate-700">
            {etiqueta}
            <input
              type="number"
              step={paso}
              value={valores[clave]}
              onChange={(e) => setValores({ ...valores, [clave]: e.target.value })}
              className="w-24 rounded-md border border-slate-300 px-2 py-1 text-sm text-right"
            />
          </span>
          <span className="text-xs text-slate-400">{ayuda}</span>
        </label>
      ))}
      <button type="submit" className="w-full px-3 py-2 rounded-lg bg-slate-800 text-white text-sm font-medium hover:bg-slate-900">
        Guardar parámetros
      </button>
      {mensaje && <p className={`text-xs ${mensaje.ok ? 'text-emerald-700' : 'text-red-600'}`}>{mensaje.texto}</p>}
    </form>
  )
}

function AsignarZona({ camara, equipos, onCancelar, onAsignar }) {
  const ocupados = new Set(camara.lista_maquinas.filter((m) => m.roi).map((m) => m.equipo_id))
  const disponibles = equipos.filter((e) => !ocupados.has(e.id))
  const [opcion, setOpcion] = useState(disponibles.length ? 'existente' : 'nueva')
  const [equipoId, setEquipoId] = useState(disponibles[0]?.id || '')
  const [nueva, setNueva] = useState({ nombre: '', codigo_activo: '', categoria: 'cardio' })
  const [error, setError] = useState(null)
  // Si la zona no se guarda (ej. PIN cancelado), al reintentar se usa la maquina ya creada.
  const [creadoId, setCreadoId] = useState(null)

  async function guardar(e) {
    e.preventDefault()
    setError(null)
    try {
      let id = Number(equipoId)
      if (opcion === 'nueva' && creadoId) id = creadoId
      else if (opcion === 'nueva') {
        const creado = await api.crearEquipo({
          ...nueva,
          sucursal_id: camara.sucursal_id,
          zona_id: camara.zona_id,
        })
        id = creado.id
        setCreadoId(id)
      }
      await onAsignar(id)
    } catch (err) {
      setError(err.message)
    }
  }

  const estiloCampo = 'w-full rounded-md border border-slate-300 px-2.5 py-1.5 text-sm'
  return (
    <form onSubmit={guardar} className="space-y-3 rounded-lg border border-orange-200 bg-orange-50 p-4">
      <p className="text-sm font-semibold text-slate-800">¿De qué máquina es esta zona?</p>
      <div className="flex gap-4 text-sm">
        <label className="inline-flex items-center gap-1.5">
          <input type="radio" checked={opcion === 'existente'} disabled={!disponibles.length} onChange={() => setOpcion('existente')} />
          Una existente
        </label>
        <label className="inline-flex items-center gap-1.5">
          <input type="radio" checked={opcion === 'nueva'} onChange={() => setOpcion('nueva')} />
          Máquina nueva
        </label>
      </div>
      {opcion === 'existente' ? (
        <select value={equipoId} onChange={(e) => setEquipoId(e.target.value)} className={estiloCampo}>
          {disponibles.map((e) => (
            <option key={e.id} value={e.id}>
              {e.nombre} ({e.codigo_activo})
            </option>
          ))}
        </select>
      ) : (
        <div className="space-y-2">
          <input required placeholder="Nombre (ej. Bicicleta 02)" value={nueva.nombre} onChange={(e) => setNueva({ ...nueva, nombre: e.target.value })} className={estiloCampo} />
          <input required placeholder="Código de activo (ej. EQ-0042)" value={nueva.codigo_activo} onChange={(e) => setNueva({ ...nueva, codigo_activo: e.target.value })} className={estiloCampo} />
          <select value={nueva.categoria} onChange={(e) => setNueva({ ...nueva, categoria: e.target.value })} className={estiloCampo}>
            {CATEGORIAS_EQUIPO.map((c) => (
              <option key={c.valor} value={c.valor}>
                {c.etiqueta}
              </option>
            ))}
          </select>
        </div>
      )}
      <div className="flex gap-2">
        <button type="submit" className="flex-1 px-3 py-2 rounded-lg bg-emerald-600 text-white text-sm font-medium hover:bg-emerald-700">
          Guardar zona
        </button>
        <button type="button" onClick={onCancelar} className="px-3 py-2 rounded-lg border border-slate-300 bg-white text-sm">
          Cancelar
        </button>
      </div>
      {error && <p className="text-xs text-red-600">{error}</p>}
    </form>
  )
}

export default function CamaraVista() {
  const { id } = useParams()
  const camaraId = Number(id)
  const [camara, setCamara] = useState(null)
  const [vivo, setVivo] = useState(null)
  const [equipos, setEquipos] = useState([])
  const [error, setError] = useState(null)
  const [versionCuadro, setVersionCuadro] = useState(0)

  // Edicion de zonas: 'ver' | 'dibujar' | 'asignar' | 'editar'
  const [modo, setModo] = useState('ver')
  const [puntos, setPuntos] = useState([])
  const [objetivo, setObjetivo] = useState(null) // equipo_id cuya zona se dibuja/edita
  const [confirmarQuitar, setConfirmarQuitar] = useState(false)
  const [aviso, setAviso] = useState(null)

  const cargarCamara = useCallback(
    () =>
      visionApi
        .obtenerCamara(camaraId)
        .then((c) => (setCamara(c), setError(null)))
        .catch((err) => setError(err.message)),
    [camaraId],
  )

  useEffect(() => {
    cargarCamara()
    const temporizador = setInterval(cargarCamara, 15000)
    return () => clearInterval(temporizador)
  }, [cargarCamara])

  useEffect(() => {
    if (camara?.sucursal_id) api.listarEquipos(camara.sucursal_id).then(setEquipos)
  }, [camara?.sucursal_id])

  const enLinea = Boolean(vivo?.en_linea)
  useEffect(() => {
    let vigente = true
    const cargar = () => visionApi.obtenerVivo(camaraId).then((v) => vigente && setVivo(v)).catch(() => {})
    cargar()
    const temporizador = setInterval(cargar, enLinea ? 1000 : 4000)
    return () => {
      vigente = false
      clearInterval(temporizador)
    }
  }, [camaraId, enLinea])

  const url = useCuadro(camaraId, enLinea, versionCuadro)
  const vivoPorEquipo = useMemo(
    () => (enLinea ? Object.fromEntries((vivo.maquinas || []).map((m) => [m.equipo_id, m])) : {}),
    [vivo, enLinea],
  )

  function empezarDibujo(equipoId = null) {
    setObjetivo(equipoId)
    setPuntos([])
    setModo('dibujar')
    setAviso(null)
  }

  function editarZona(maquina) {
    setObjetivo(maquina.equipo_id)
    setPuntos(maquina.roi.map((p) => [...p]))
    setModo('editar')
    setConfirmarQuitar(false)
    setAviso(null)
  }

  function cancelar() {
    setModo('ver')
    setPuntos([])
    setObjetivo(null)
    setConfirmarQuitar(false)
  }

  async function guardarZona(equipoId) {
    await visionApi.guardarZona(camaraId, equipoId, puntos)
    cancelar()
    setAviso('Zona guardada. Si el pipeline está corriendo, la aplica en unos segundos.')
    await cargarCamara()
    api.listarEquipos(camara.sucursal_id).then(setEquipos)
  }

  async function quitar() {
    await visionApi.quitarZona(camaraId, objetivo)
    cancelar()
    setAviso('La máquina se quitó de esta cámara (sigue en el inventario).')
    cargarCamara()
  }

  function cerrarPoligono() {
    if (puntos.length < 3) return
    if (objetivo) guardarZona(objetivo).catch((err) => setAviso(err.message))
    else setModo('asignar')
  }

  async function subirReferencia(archivo) {
    try {
      await visionApi.subirCuadro(camaraId, archivo)
      setVersionCuadro(Date.now())
      cargarCamara()
    } catch (err) {
      setAviso(err.message)
    }
  }

  if (error && !camara) return <p className="text-sm text-red-600">No se pudo cargar la cámara: {error}</p>
  if (!camara) return <p className="text-sm text-slate-500">Cargando…</p>

  const enEdicion = modo !== 'ver'
  const maquinaObjetivo = camara.lista_maquinas.find((m) => m.equipo_id === objetivo)

  return (
    <div className="space-y-5">
      <PinDialogo />
      <Link to="/camaras" className="text-sm text-emerald-700 hover:underline">
        ← Cámaras
      </Link>
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">{camara.nombre}</h1>
          <p className="text-sm text-slate-500">
            {camara.codigo}
            {camara.ancho_px && ` · ${camara.ancho_px}×${camara.alto_px}`}
            {enLinea && vivo.fps_analisis != null && ` · ${vivo.fps_analisis} análisis/s · ${vivo.latencia_ms} ms por cuadro`}
          </p>
        </div>
        <ChipSenal camara={{ ...camara, en_linea: enLinea, ultima_conexion: camara.ultima_conexion }} />
      </div>

      <div className="grid lg:grid-cols-3 gap-5 items-start">
        <div className="lg:col-span-2 space-y-3">
          <Escenario
            url={url}
            maquinas={camara.lista_maquinas}
            personas={enLinea && modo === 'ver' ? vivo.personas || [] : []}
            vivoPorEquipo={vivoPorEquipo}
            modo={modo === 'asignar' ? 'editar' : modo}
            puntos={puntos}
            setPuntos={setPuntos}
            editando={modo === 'editar' ? objetivo : null}
            onCerrarPoligono={cerrarPoligono}
          />
          {modo === 'dibujar' && (
            <div className="flex flex-wrap items-center gap-3 text-sm bg-orange-50 border border-orange-200 rounded-lg px-4 py-3">
              <p className="flex-1 text-slate-700">
                {maquinaObjetivo ? `Zona de ${maquinaObjetivo.nombre}: haz` : 'Haz'} clic en la imagen para marcar las
                esquinas donde se apoya quien usa la máquina. Cierra la zona haciendo clic en el primer punto (verde).
              </p>
              <button type="button" disabled={puntos.length < 3} onClick={cerrarPoligono} className="px-3 py-1.5 rounded-md bg-emerald-600 text-white disabled:opacity-40">
                Terminar ({puntos.length} puntos)
              </button>
              <button type="button" onClick={() => setPuntos(puntos.slice(0, -1))} disabled={!puntos.length} className="px-3 py-1.5 rounded-md border border-slate-300 bg-white disabled:opacity-40">
                Deshacer punto
              </button>
              <button type="button" onClick={cancelar} className="px-3 py-1.5 rounded-md border border-slate-300 bg-white">
                Cancelar
              </button>
            </div>
          )}
          {modo === 'editar' && maquinaObjetivo && (
            <div className="flex flex-wrap items-center gap-3 text-sm bg-orange-50 border border-orange-200 rounded-lg px-4 py-3">
              <p className="flex-1 text-slate-700">
                Editando la zona de <span className="font-semibold">{maquinaObjetivo.nombre}</span>: arrastra los puntos.
              </p>
              <button type="button" onClick={() => guardarZona(objetivo).catch((err) => setAviso(err.message))} className="px-3 py-1.5 rounded-md bg-emerald-600 text-white">
                Guardar zona
              </button>
              <button type="button" onClick={() => empezarDibujo(objetivo)} className="px-3 py-1.5 rounded-md border border-slate-300 bg-white">
                Redibujar
              </button>
              {confirmarQuitar ? (
                <span className="inline-flex items-center gap-2">
                  ¿Quitar de la cámara?
                  <button type="button" onClick={() => quitar().catch((err) => setAviso(err.message))} className="px-2.5 py-1 rounded-md bg-red-600 text-white">Sí, quitar</button>
                  <button type="button" onClick={() => setConfirmarQuitar(false)} className="px-2.5 py-1 rounded-md border border-slate-300 bg-white">No</button>
                </span>
              ) : (
                <button type="button" onClick={() => setConfirmarQuitar(true)} className="px-3 py-1.5 rounded-md border border-red-200 text-red-700 bg-white">
                  Quitar de la cámara
                </button>
              )}
              <button type="button" onClick={cancelar} className="px-3 py-1.5 rounded-md border border-slate-300 bg-white">
                Cancelar
              </button>
            </div>
          )}
          {modo === 'asignar' && (
            <AsignarZona camara={camara} equipos={equipos} onCancelar={cancelar} onAsignar={guardarZona} />
          )}
          {aviso && <p className="text-sm text-emerald-700">{aviso}</p>}
          <p className="text-xs text-slate-400">
            Las cabezas llegan difuminadas desde el pipeline: el sistema mide uso de máquinas, no identifica personas.
            Caja blanca: persona sobre una máquina; punteada: persona que no está usando ninguna.
          </p>
        </div>

        <div className="space-y-4">
          <div className="bg-white rounded-lg border border-slate-200 shadow-sm">
            <div className="flex items-center justify-between px-4 py-3 border-b border-slate-100">
              <h2 className="font-semibold text-slate-900">Máquinas en esta cámara</h2>
              <button
                type="button"
                disabled={enEdicion || !url}
                onClick={() => empezarDibujo()}
                className="text-xs font-medium px-2.5 py-1.5 rounded-md bg-emerald-600 text-white hover:bg-emerald-700 disabled:opacity-40"
              >
                + Agregar máquina
              </button>
            </div>
            {camara.lista_maquinas.length === 0 && (
              <p className="px-4 py-4 text-sm text-slate-500">Todavía no hay máquinas. Agrega una dibujando su zona sobre la imagen.</p>
            )}
            <ul className="divide-y divide-slate-100">
              {camara.lista_maquinas.map((m) => {
                const estado = vivoPorEquipo[m.equipo_id]
                return (
                  <li key={m.equipo_id} className={`px-4 py-3 ${objetivo === m.equipo_id ? 'bg-orange-50' : ''}`}>
                    <div className="flex items-start gap-2.5">
                      <span
                        className="mt-1.5 w-2.5 h-2.5 rounded-full shrink-0"
                        style={{ backgroundColor: ESTADOS_VIVO[estado?.estado]?.relleno || COLOR_SIN_DATO }}
                      />
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium text-slate-900 truncate">{m.nombre}</p>
                        <p className="text-xs text-slate-500">
                          {m.roi ? (estado ? textoEstadoVivo(estado) : 'Sin dato en vivo') : 'Sin zona dibujada'}
                        </p>
                      </div>
                      <div className="flex flex-col items-end gap-1">
                        <button
                          type="button"
                          disabled={enEdicion || !url}
                          onClick={() => (m.roi ? editarZona(m) : empezarDibujo(m.equipo_id))}
                          className="text-xs text-emerald-700 hover:underline disabled:opacity-40"
                        >
                          {m.roi ? 'Editar zona' : 'Dibujar zona'}
                        </button>
                        <Link to={`/uso/${m.equipo_id}`} className="text-xs text-slate-500 hover:underline">
                          Historial
                        </Link>
                      </div>
                    </div>
                  </li>
                )
              })}
            </ul>
          </div>

          <details className="bg-white rounded-lg border border-slate-200 shadow-sm">
            <summary className="px-4 py-3 font-semibold text-slate-900 cursor-pointer">Parámetros de detección</summary>
            <div className="px-4 pb-4">
              <Parametros camara={camara} onGuardado={cargarCamara} />
            </div>
          </details>

          <div className="bg-white rounded-lg border border-slate-200 shadow-sm p-4 space-y-3 text-sm">
            <h2 className="font-semibold text-slate-900">Imagen de la cámara</h2>
            {!enLinea && (
              <div className="space-y-2">
                <p className="text-slate-600">Para verla en vivo, inicia el pipeline de visión para esta cámara:</p>
                <pre className="text-xs bg-slate-900 text-slate-100 rounded-md p-3 overflow-x-auto whitespace-pre-wrap">
                  {`python -m gymkeep_vision procesar <video o rtsp://...> \\\n  --api http://localhost:8000 --camara ${camara.codigo}`}
                </pre>
              </div>
            )}
            <label className="inline-block cursor-pointer text-xs font-medium px-3 py-1.5 rounded-md border border-slate-300 bg-white hover:bg-slate-50">
              Subir imagen de referencia
              <input type="file" accept="image/*" className="hidden" onChange={(e) => e.target.files[0] && subirReferencia(e.target.files[0])} />
            </label>
            <p className="text-xs text-slate-400">Sirve para dibujar las zonas antes de tener el pipeline corriendo.</p>
          </div>
        </div>
      </div>
    </div>
  )
}
