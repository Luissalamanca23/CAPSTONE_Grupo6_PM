import { useEffect, useMemo, useState } from 'react'
import { useParams } from 'react-router-dom'
import { api } from '../api/client.js'

const CATEGORIAS = [
  { clave: 'mecanica', etiqueta: 'Mecánica', ayuda: 'Piezas, ruidos, desgaste' },
  { clave: 'electrica', etiqueta: 'Eléctrica', ayuda: 'No enciende, pantalla, cables' },
  { clave: 'otro', etiqueta: 'Otro', ayuda: 'No estoy seguro' },
]

const GRAVEDADES = [
  { valor: 'leve', etiqueta: 'Leve', ayuda: 'Se puede seguir usando con cuidado' },
  { valor: 'grave', etiqueta: 'Grave', ayuda: 'Mejor que nadie la use así' },
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
  const [gravedad, setGravedad] = useState(null)
  const [funcional, setFuncional] = useState(null) // true | false | null (sin responder)
  const [nombre, setNombre] = useState('')

  const [enviando, setEnviando] = useState(false)
  const [errorEnvio, setErrorEnvio] = useState(null)
  const [enviado, setEnviado] = useState(null) // guarda la respuesta del servidor al enviar

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

  const listo = Boolean(categoria && pasoDosCompleto && gravedad && funcional !== null && nombre.trim())

  async function manejarEnvio(evento) {
    evento.preventDefault()
    if (!listo) return

    setEnviando(true)
    setErrorEnvio(null)
    try {
      const resultado = await api.crearIncidenciaPorQr({
        token,
        tipo_falla_codigo: tipoFallaSeleccionado,
        gravedad,
        funcional,
        reportado_por: nombre.trim(),
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
    setGravedad(null)
    setFuncional(null)
    setNombre('')
    setEnviado(null)
    setErrorEnvio(null)
  }

  return (
    <div className="min-h-screen bg-slate-50 flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        <div className="text-center mb-6">
          <p className="text-2xl font-bold text-emerald-700">GymKeep</p>
          <p className="text-sm text-slate-500">Reporte de falla de equipamiento</p>
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

          {!cargando && !errorCarga && enviado && (
            <div className="text-center space-y-2 py-4">
              <p className="text-emerald-600 font-semibold text-lg">¡Gracias por tu reporte!</p>
              <p className="text-sm text-slate-500">
                Registramos la falla en <strong>{equipo.nombre}</strong>.{' '}
                {funcional === false
                  ? 'Marcamos el equipo como fuera de servicio para que nadie más lo use mientras se revisa.'
                  : 'El equipo de mantenimiento la revisará pronto.'}
              </p>
              <button
                onClick={reiniciar}
                className="mt-3 text-sm text-emerald-700 font-medium underline"
              >
                Enviar otro reporte
              </button>
            </div>
          )}

          {!cargando && !errorCarga && !enviado && (
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
                            ? 'border-emerald-600 bg-emerald-50 text-emerald-700'
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
                              ? 'border-emerald-600 bg-emerald-50 text-emerald-700'
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

              {/* Paso 3: gravedad */}
              {pasoDosCompleto && (
                <div>
                  <p className="text-sm font-medium text-slate-700 mb-2">3. ¿Qué tan grave es?</p>
                  <div className="grid grid-cols-2 gap-2">
                    {GRAVEDADES.map((g) => {
                      const seleccionado = gravedad === g.valor
                      return (
                        <button
                          type="button"
                          key={g.valor}
                          onClick={() => setGravedad(g.valor)}
                          className={`px-3 py-3 rounded-lg text-sm font-medium border-2 transition-colors ${
                            seleccionado
                              ? 'border-emerald-600 bg-emerald-50 text-emerald-700'
                              : 'border-slate-200 text-slate-600 hover:border-slate-300'
                          }`}
                        >
                          <span className="block font-semibold">{g.etiqueta}</span>
                          <span className="block text-[10px] text-slate-400 mt-0.5">{g.ayuda}</span>
                        </button>
                      )
                    })}
                  </div>
                </div>
              )}

              {/* Paso 4: sigue funcionando */}
              {gravedad && (
                <div>
                  <p className="text-sm font-medium text-slate-700 mb-2">
                    4. ¿La máquina todavía se puede usar?
                  </p>
                  <div className="grid grid-cols-2 gap-2">
                    <button
                      type="button"
                      onClick={() => setFuncional(true)}
                      className={`px-3 py-3 rounded-lg text-sm font-medium border-2 transition-colors ${
                        funcional === true
                          ? 'border-emerald-600 bg-emerald-50 text-emerald-700'
                          : 'border-slate-200 text-slate-600 hover:border-slate-300'
                      }`}
                    >
                      Sí, funciona
                    </button>
                    <button
                      type="button"
                      onClick={() => setFuncional(false)}
                      className={`px-3 py-3 rounded-lg text-sm font-medium border-2 transition-colors ${
                        funcional === false
                          ? 'border-red-600 bg-red-50 text-red-700'
                          : 'border-slate-200 text-slate-600 hover:border-slate-300'
                      }`}
                    >
                      No, está detenida
                    </button>
                  </div>
                  {funcional === false && (
                    <p className="text-xs text-red-600 mt-2">
                      La marcaremos como fuera de servicio para que nadie más la use.
                    </p>
                  )}
                </div>
              )}

              {/* Paso 5: nombre (unico campo de texto libre obligatorio ademas de la descripcion de "otro") */}
              {funcional !== null && (
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
                className="w-full bg-emerald-600 text-white rounded-md px-4 py-2.5 text-sm font-semibold hover:bg-emerald-700 disabled:opacity-50 disabled:cursor-not-allowed"
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
