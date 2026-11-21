import { useEffect, useMemo, useState } from 'react'
import { useParams } from 'react-router-dom'
import { api } from '../api/client.js'
import { reducirFoto } from '../utils/imagen.js'
import { OPCIONES_USO, datosDeUso } from '../utils/usoReporte.js'

const CATEGORIAS = [
  { clave: 'mecanica', etiqueta: 'Mecánica', ayuda: 'Piezas, ruidos, desgaste' },
  { clave: 'electrica', etiqueta: 'Eléctrica', ayuda: 'No enciende, pantalla, cables' },
  { clave: 'otro', etiqueta: 'Otro', ayuda: 'No estoy seguro' },
]

export default function Reportar() {
  const { token } = useParams()

  const [equipo, setEquipo] = useState(null)
  const [tiposFalla, setTiposFalla] = useState([])
  const [cargando, setCargando] = useState(true)
  const [errorCarga, setErrorCarga] = useState(null)

  const [categoria, setCategoria] = useState(null)
  const [tipoFallaSeleccionado, setTipoFallaSeleccionado] = useState(null)
  const [descripcionLibre, setDescripcionLibre] = useState('') // solo para categoria "otro"
  const [uso, setUso] = useState(null) // 'funciona' | 'riesgo' | 'detenida' | null (sin responder)
  const [foto, setFoto] = useState(null) // { base64, vistaPrevia } | null (opcional)
  const [errorFoto, setErrorFoto] = useState(null)
  const [procesandoFoto, setProcesandoFoto] = useState(false)
  const [nombre, setNombre] = useState('')

  const [enviando, setEnviando] = useState(false)
  const [errorEnvio, setErrorEnvio] = useState(null)
  const [enviado, setEnviado] = useState(null) // guarda la respuesta del servidor al enviar

  // Pagina publica (la abre cualquiera desde el QR): titulo propio y sin indexar en buscadores.
  // No tiene enlaces al panel ni da acceso a el: para eso hay que iniciar sesion en /login.
  useEffect(() => {
    const tituloAnterior = document.title
    document.title = 'Reportar una falla · GymKeep'
    const meta = document.createElement('meta')
    meta.name = 'robots'
    meta.content = 'noindex, nofollow'
    document.head.appendChild(meta)
    return () => {
      document.title = tituloAnterior
      meta.remove()
    }
  }, [])

  useEffect(() => {
    // solo_reporte_qr=true: no muestra fallas que solo puede detectar la IA
    // (ej. movimiento anómalo), esas no tienen sentido en una encuesta manual.
    Promise.all([api.obtenerEquipoPorQr(token), api.listarTiposFalla(true)])
      .then(([equipoData, tiposData]) => {
        setEquipo(equipoData)
        setTiposFalla(tiposData)
      })
      .catch((err) => setErrorCarga(err.message))
      .finally(() => setCargando(false))
  }, [token])

  const categoriasDisponibles = useMemo(() => {
    const presentes = new Set(tiposFalla.map((t) => t.categoria))
    return CATEGORIAS.filter((c) => presentes.has(c.clave))
  }, [tiposFalla])

  const tiposDeLaCategoria = useMemo(
    () => tiposFalla.filter((t) => t.categoria === categoria),
    [tiposFalla, categoria]
  )

  const esCategoriaOtro = categoria === 'otro'

  function elegirCategoria(clave) {
    setCategoria(clave)
    setDescripcionLibre('')
    if (clave === 'otro') {
      // No hay un tipo de falla especifico que elegir: se usa el unico codigo "otro" del
      // catalogo y en vez de botones se le pide al usuario que escriba que pasa.
      const tipoOtro = tiposFalla.find((t) => t.categoria === 'otro')
      setTipoFallaSeleccionado(tipoOtro ? tipoOtro.codigo : null)
    } else {
      setTipoFallaSeleccionado(null) // las opciones del siguiente paso cambian
    }
  }

  // En "mecanica"/"electrica" el paso 2 se completa eligiendo un tipo de falla; en "otro" se
  // completa escribiendo la descripcion (el tipo de falla ya quedo fijo en elegirCategoria).
  const pasoDosCompleto = esCategoriaOtro ? Boolean(descripcionLibre.trim()) : Boolean(tipoFallaSeleccionado)

  const listo = Boolean(categoria && pasoDosCompleto && uso && nombre.trim())

  async function elegirFoto(evento) {
    const archivo = evento.target.files?.[0]
    evento.target.value = '' // permite volver a elegir la misma foto
    if (!archivo) return
    setErrorFoto(null)
    setProcesandoFoto(true)
    try {
      setFoto(await reducirFoto(archivo))
    } catch (err) {
      setFoto(null)
      setErrorFoto(err.message)
    } finally {
      setProcesandoFoto(false)
    }
  }

  async function manejarEnvio(evento) {
    evento.preventDefault()
    if (!listo) return
    const { gravedad, funcional } = datosDeUso(uso)

    setEnviando(true)
    setErrorEnvio(null)
    try {
      const resultado = await api.crearIncidenciaPorQr({
        token,
        tipo_falla_codigo: tipoFallaSeleccionado,
        gravedad,
        funcional,
        reportado_por: nombre.trim(),
        ...(foto ? { foto: foto.base64 } : {}),
        ...(esCategoriaOtro ? { descripcion: descripcionLibre.trim() } : {}),
      })
      setEnviado(resultado)
    } catch (err) {
      setErrorEnvio(err.message)
    } finally {
      setEnviando(false)
    }
  }

  function reiniciar() {
    setCategoria(null)
    setTipoFallaSeleccionado(null)
    setDescripcionLibre('')
    setUso(null)
    setNombre('')
    setFoto(null)
    setErrorFoto(null)
    setEnviado(null)
    setErrorEnvio(null)
  }

  return (
    <div className="min-h-screen bg-slate-50 flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        <div className="text-center mb-6">
          <div className="bg-black rounded-xl py-4">
            <img src="/logo.png" alt="GymKeep" width="416" height="340" className="mx-auto w-40 h-auto" />
          </div>
          <p className="text-sm text-slate-500 mt-3">Reporte de falla de equipamiento</p>
        </div>

        <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6">
          {cargando && <p className="text-slate-500 text-center">Cargando...</p>}

          {!cargando && errorCarga && (
            <div className="text-center space-y-2">
              <p className="text-red-600 font-medium">Código QR no válido</p>
              <p className="text-sm text-slate-500">
                No encontramos una máquina activa con este código. Pide ayuda al personal del gimnasio.
              </p>
            </div>
          )}

          {!cargando && !errorCarga && !enviado && equipo.estado === 'fuera_de_servicio' && (
            <div className="text-center space-y-2 py-4">
              <p className="text-red-600 font-semibold text-lg">Máquina fuera de servicio</p>
              <p className="text-sm text-slate-500">
                <strong>{equipo.nombre}</strong> ya fue reportada y está fuera de servicio. No se reciben más
                reportes hasta que el personal la habilite de nuevo.
              </p>
            </div>
          )}

          {!cargando && !errorCarga && enviado && (
            <div className="text-center space-y-2 py-4">
              <p className="text-brand-600 font-semibold text-lg">¡Gracias por tu reporte!</p>
              <p className="text-sm text-slate-500">
                Registramos la falla en <strong>{equipo.nombre}</strong>.{' '}
                {uso === 'detenida'
                  ? 'Lo marcamos como urgente para que el equipo de mantenimiento lo revise. Si otra persona confirma la falla, quedará fuera de servicio.'
                  : 'El equipo de mantenimiento la revisará pronto.'}
              </p>
              <button
                onClick={reiniciar}
                className="mt-3 text-sm text-brand-700 font-medium underline"
              >
                Enviar otro reporte
              </button>
            </div>
          )}

          {!cargando && !errorCarga && !enviado && equipo.estado !== 'fuera_de_servicio' && (
            <form onSubmit={manejarEnvio} className="space-y-6">
              <div className="text-center">
                <p className="text-sm text-slate-500">Estás reportando una falla en:</p>
                <p className="font-semibold text-slate-900">{equipo.nombre}</p>
                {equipo.zona?.nombre && <p className="text-xs text-slate-400">{equipo.zona.nombre}</p>}
              </div>

              {/* Paso 1: categoria general */}
              <div>
                <p className="text-sm font-medium text-slate-700 mb-2">1. ¿De qué tipo es el problema?</p>
                <div className="grid grid-cols-3 gap-2">
                  {categoriasDisponibles.map((c) => {
                    const seleccionado = categoria === c.clave
                    return (
                      <button
                        type="button"
                        key={c.clave}
                        onClick={() => elegirCategoria(c.clave)}
                        className={`px-2 py-3 rounded-lg text-xs font-medium border-2 transition-colors ${
                          seleccionado
                            ? 'border-brand-600 bg-brand-50 text-brand-700'
                            : 'border-slate-200 text-slate-600 hover:border-slate-300'
                        }`}
                      >
                        <span className="block font-semibold">{c.etiqueta}</span>
                        <span className="block text-[10px] text-slate-400 mt-0.5">{c.ayuda}</span>
                      </button>
                    )
                  })}
                </div>
              </div>

              {/* Paso 2: falla especifica (mecanica/electrica) o descripcion libre (otro) */}
              {categoria && !esCategoriaOtro && (
                <div>
                  <p className="text-sm font-medium text-slate-700 mb-2">2. ¿Qué le pasa exactamente?</p>
                  <div className="grid grid-cols-2 gap-2">
                    {tiposDeLaCategoria.map((tipo) => {
                      const seleccionado = tipoFallaSeleccionado === tipo.codigo
                      return (
                        <button
                          type="button"
                          key={tipo.codigo}
                          onClick={() => setTipoFallaSeleccionado(tipo.codigo)}
                          className={`px-3 py-3 rounded-lg text-sm font-medium border-2 transition-colors ${
                            seleccionado
                              ? 'border-brand-600 bg-brand-50 text-brand-700'
                              : 'border-slate-200 text-slate-600 hover:border-slate-300'
                          }`}
                        >
                          {tipo.nombre}
                        </button>
                      )
                    })}
                  </div>
                </div>
              )}

              {esCategoriaOtro && (
                <div>
                  <label className="text-sm font-medium text-slate-700 block mb-2">
                    2. Cuéntanos qué pasa
                  </label>
                  <textarea
                    value={descripcionLibre}
                    onChange={(e) => setDescripcionLibre(e.target.value)}
                    placeholder="Describe brevemente el problema..."
                    required
                    rows={3}
                    className="w-full border border-slate-300 rounded-md px-3 py-2 text-sm resize-none"
                  />
                </div>
              )}

              {/* Paso 3: se puede seguir usando (una sola respuesta; define la prioridad) */}
              {pasoDosCompleto && (
                <div>
                  <p className="text-sm font-medium text-slate-700 mb-2">3. ¿Se puede seguir usando la máquina?</p>
                  <div className="grid gap-2">
                    {OPCIONES_USO.map((o) => {
                      const seleccionado = uso === o.valor
                      const detenida = o.valor === 'detenida'
                      return (
                        <button
                          type="button"
                          key={o.valor}
                          onClick={() => setUso(o.valor)}
                          className={`px-3 py-3 rounded-lg text-sm font-medium border-2 text-left transition-colors ${
                            seleccionado
                              ? detenida
                                ? 'border-red-600 bg-red-50 text-red-700'
                                : 'border-brand-600 bg-brand-50 text-brand-700'
                              : 'border-slate-200 text-slate-600 hover:border-slate-300'
                          }`}
                        >
                          <span className="block font-semibold">{o.etiqueta}</span>
                          <span className="block text-[11px] text-slate-400 mt-0.5">{o.ayuda}</span>
                        </button>
                      )
                    })}
                  </div>
                  {uso === 'detenida' && (
                    <p className="text-xs text-red-600 mt-2">
                      La marcaremos como urgente; si otra persona confirma la falla, quedará fuera de servicio.
                    </p>
                  )}
                </div>
              )}

              {/* Paso 4: foto del dano o la falla (OPCIONAL, va antes del nombre) */}
              {uso !== null && (
                <div>
                  <p className="text-sm font-medium text-slate-700 mb-1">
                    4. Foto del daño o la falla <span className="font-normal text-slate-400">(opcional)</span>
                  </p>
                  {foto ? (
                    <div className="relative">
                      <img
                        src={foto.vistaPrevia}
                        alt="Foto adjunta del daño"
                        className="w-full max-h-56 object-cover rounded-lg border border-slate-200"
                      />
                      <button
                        type="button"
                        onClick={() => setFoto(null)}
                        className="mt-2 text-xs text-red-600 font-medium underline"
                      >
                        Quitar foto
                      </button>
                    </div>
                  ) : (
                    <label
                      htmlFor="foto-dano"
                      className="flex flex-col items-center justify-center gap-1 border-2 border-dashed border-slate-300 rounded-lg px-3 py-5 text-sm text-slate-600 cursor-pointer hover:border-slate-400"
                    >
                      <span className="font-medium">
                        {procesandoFoto ? 'Preparando foto...' : 'Tomar o elegir una foto'}
                      </span>
                      <span className="text-[11px] text-slate-400">Ayuda al técnico a ver qué pasó. Puedes omitirla.</span>
                    </label>
                  )}
                  <input
                    id="foto-dano"
                    type="file"
                    accept="image/*"
                    onChange={elegirFoto}
                    className="sr-only"
                  />
                  {errorFoto && <p className="text-xs text-red-600 mt-1">{errorFoto}</p>}
                </div>
              )}

              {/* Paso 5: nombre (unico campo de texto libre obligatorio ademas de la descripcion de "otro") */}
              {uso !== null && (
                <div>
                  <label className="text-sm font-medium text-slate-700 block mb-1">5. Tu nombre</label>
                  <input
                    type="text"
                    value={nombre}
                    onChange={(e) => setNombre(e.target.value)}
                    placeholder="Escribe tu nombre"
                    required
                    className="w-full border border-slate-300 rounded-md px-3 py-2 text-sm"
                  />
                </div>
              )}

              {errorEnvio && <p className="text-red-600 text-sm">{errorEnvio}</p>}

              <button
                type="submit"
                disabled={enviando || !listo}
                className="w-full bg-brand-600 text-white rounded-md px-4 py-2.5 text-sm font-semibold hover:bg-brand-700 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {enviando ? 'Enviando...' : 'Enviar reporte'}
              </button>
            </form>
          )}
        </div>
      </div>
    </div>
  )
}
