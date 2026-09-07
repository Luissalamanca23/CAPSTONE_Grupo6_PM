import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { api } from '../api/client.js'

export default function Reportar() {
  const { codigoQr } = useParams()

  const [equipo, setEquipo] = useState(null)
  const [tiposFalla, setTiposFalla] = useState([])
  const [cargando, setCargando] = useState(true)
  const [errorCarga, setErrorCarga] = useState(null)

  const [tipoFallaSeleccionado, setTipoFallaSeleccionado] = useState(null)
  const [nombre, setNombre] = useState('')
  const [enviando, setEnviando] = useState(false)
  const [errorEnvio, setErrorEnvio] = useState(null)
  const [enviado, setEnviado] = useState(false)

  useEffect(() => {
    Promise.all([api.obtenerEquipoPorQr(codigoQr), api.listarTiposFalla()])
      .then(([equipoData, tiposData]) => {
        setEquipo(equipoData)
        setTiposFalla(tiposData)
      })
      .catch((err) => setErrorCarga(err.message))
      .finally(() => setCargando(false))
  }, [codigoQr])

  async function manejarEnvio(evento) {
    evento.preventDefault()
    if (!tipoFallaSeleccionado || !nombre.trim()) return

    setEnviando(true)
    setErrorEnvio(null)
    try {
      await api.crearIncidenciaPorQr({
        codigo_qr: codigoQr,
        tipo_falla: tipoFallaSeleccionado,
        reportado_por: nombre.trim(),
      })
      setEnviado(true)
    } catch (err) {
      setErrorEnvio(err.message)
    } finally {
      setEnviando(false)
    }
  }

  function reiniciar() {
    setTipoFallaSeleccionado(null)
    setNombre('')
    setEnviado(false)
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
                No encontramos una máquina con este código. Pide ayuda al personal del gimnasio.
              </p>
            </div>
          )}

          {!cargando && !errorCarga && enviado && (
            <div className="text-center space-y-2 py-4">
              <p className="text-emerald-600 font-semibold text-lg">¡Gracias por tu reporte!</p>
              <p className="text-sm text-slate-500">
                Registramos la falla en <strong>{equipo.nombre}</strong>. El equipo de
                mantenimiento la revisará pronto.
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
            <form onSubmit={manejarEnvio} className="space-y-5">
              <div className="text-center">
                <p className="text-sm text-slate-500">Estás reportando una falla en:</p>
                <p className="font-semibold text-slate-900">{equipo.nombre}</p>
                {equipo.ubicacion && <p className="text-xs text-slate-400">{equipo.ubicacion}</p>}
              </div>

              <div>
                <p className="text-sm font-medium text-slate-700 mb-2">
                  ¿Qué le pasa a la máquina?
                </p>
                <div className="grid grid-cols-2 gap-2">
                  {tiposFalla.map((tipo) => {
                    const seleccionado = tipoFallaSeleccionado === tipo.valor
                    return (
                      <button
                        type="button"
                        key={tipo.valor}
                        onClick={() => setTipoFallaSeleccionado(tipo.valor)}
                        className={`px-3 py-3 rounded-lg text-sm font-medium border-2 transition-colors ${
                          seleccionado
                            ? 'border-emerald-600 bg-emerald-50 text-emerald-700'
                            : 'border-slate-200 text-slate-600 hover:border-slate-300'
                        }`}
                      >
                        {tipo.etiqueta}
                      </button>
                    )
                  })}
                </div>
              </div>

              <div>
                <label className="text-sm font-medium text-slate-700 block mb-1">Tu nombre</label>
                <input
                  type="text"
                  value={nombre}
                  onChange={(e) => setNombre(e.target.value)}
                  placeholder="Escribe tu nombre"
                  required
                  className="w-full border border-slate-300 rounded-md px-3 py-2 text-sm"
                />
              </div>

              {errorEnvio && <p className="text-red-600 text-sm">{errorEnvio}</p>}

              <button
                type="submit"
                disabled={enviando || !tipoFallaSeleccionado || !nombre.trim()}
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
