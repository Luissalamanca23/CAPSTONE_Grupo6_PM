import { useEffect, useState } from 'react'

// Lo que devuelve /…/resumen-eliminacion, en palabras del panel. `borra: false` son cosas que
// se CONSERVAN (solo pierden un vinculo): se muestran distinto y no exigen escribir ELIMINAR.
const ETIQUETAS = {
  zonas: { texto: 'zonas', borra: true },
  maquinas: { texto: 'máquinas', borra: true },
  camaras: { texto: 'cámaras', borra: true },
  incidencias: { texto: 'reportes de falla', borra: true },
  mantenimientos: { texto: 'mantenimientos', borra: true },
  sesiones_uso: { texto: 'sesiones de uso', borra: true },
  eventos_ia: { texto: 'eventos de IA', borra: true },
  codigos_qr: { texto: 'códigos QR', borra: true },
  maquinas_sin_zona: { texto: 'máquinas quedarán sin zona (no se borran)', borra: false },
  camaras_sin_zona: { texto: 'cámaras quedarán sin zona (no se borran)', borra: false },
  maquinas_vinculadas: { texto: 'máquinas vinculadas (no se borran)', borra: false },
  sesiones_uso_desvinculadas: { texto: 'sesiones de uso se conservan sin cámara', borra: false },
  mantenimientos_desvinculados: { texto: 'mantenimientos se conservan sin ese reporte', borra: false },
}

const PALABRA = 'ELIMINAR'

/**
 * Boton "Eliminar" + dialogo de confirmacion reutilizable.
 *
 * - `cargarResumen` (opcional): async () => { conteos } con lo que se llevaria el borrado; se
 *   pide al abrir el dialogo y se lista antes de confirmar.
 * - `onConfirmar`: async () => borra de verdad (llamada DELETE de la API).
 * - `onEliminado`: se ejecuta tras borrar (recargar la lista, navegar, etc.).
 * Si el borrado arrastra datos (reportes, mantenimientos, máquinas…) pide escribir ELIMINAR.
 */
export default function ConfirmarEliminar({
  titulo,
  nombre,
  cargarResumen,
  onConfirmar,
  onEliminado,
  etiqueta = 'Eliminar',
  aviso,
  className = 'text-xs font-medium text-red-600 underline hover:text-red-700',
}) {
  const [abierto, setAbierto] = useState(false)
  const [resumen, setResumen] = useState(null)
  const [cargando, setCargando] = useState(false)
  const [borrando, setBorrando] = useState(false)
  const [error, setError] = useState(null)
  const [texto, setTexto] = useState('')

  useEffect(() => {
    if (!abierto) return undefined
    let vigente = true
    setResumen(null)
    setError(null)
    setTexto('')
    if (cargarResumen) {
      setCargando(true)
      cargarResumen()
        .then((r) => vigente && setResumen(r))
        .catch((err) => vigente && setError(err.message))
        .finally(() => vigente && setCargando(false))
    }
    const alTeclear = (e) => e.key === 'Escape' && !borrando && setAbierto(false)
    window.addEventListener('keydown', alTeclear)
    return () => {
      vigente = false
      window.removeEventListener('keydown', alTeclear)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [abierto])

  const filas = Object.entries(resumen?.conteos || {})
    .filter(([, n]) => n > 0)
    .map(([clave, n]) => ({ clave, n, ...(ETIQUETAS[clave] || { texto: clave, borra: true }) }))
  const hayQueBorrar = filas.some((f) => f.borra)
  const exigeTexto = hayQueBorrar
  const confirmado = !exigeTexto || texto.trim().toUpperCase() === PALABRA
  const listo = !cargando && (!cargarResumen || resumen !== null)

  async function confirmar() {
    setBorrando(true)
    setError(null)
    try {
      await onConfirmar()
      setAbierto(false)
      onEliminado?.()
    } catch (err) {
      setError(err.message)
    } finally {
      setBorrando(false)
    }
  }

  return (
    <>
      <button type="button" onClick={() => setAbierto(true)} className={className}>
        {etiqueta}
      </button>

      {abierto && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 p-4"
          role="dialog"
          aria-modal="true"
          aria-labelledby="titulo-eliminar"
          onClick={() => !borrando && setAbierto(false)}
        >
          <div
            className="w-full max-w-md rounded-lg bg-white shadow-xl border border-slate-200 p-5 space-y-4"
            onClick={(e) => e.stopPropagation()}
          >
            <div>
              <h2 id="titulo-eliminar" className="text-lg font-semibold text-slate-900">
                {titulo}
              </h2>
              {nombre && <p className="text-sm text-slate-600 mt-0.5">«{nombre}»</p>}
            </div>

            {cargando && <p className="text-sm text-slate-500">Calculando qué se va a borrar…</p>}

            {listo && filas.length > 0 && (
              <div className="rounded-md border border-red-200 bg-red-50 p-3 text-sm space-y-1.5">
                {hayQueBorrar && <p className="font-medium text-red-800">También se borrará:</p>}
                <ul className="space-y-0.5 text-red-900">
                  {filas
                    .filter((f) => f.borra)
                    .map((f) => (
                      <li key={f.clave}>
                        <span className="font-semibold tabular-nums">{f.n}</span> {f.texto}
                      </li>
                    ))}
                </ul>
                {filas.some((f) => !f.borra) && (
                  <ul className="space-y-0.5 text-slate-600 pt-1">
                    {filas
                      .filter((f) => !f.borra)
                      .map((f) => (
                        <li key={f.clave}>
                          <span className="font-semibold tabular-nums">{f.n}</span> {f.texto}
                        </li>
                      ))}
                  </ul>
                )}
              </div>
            )}

            {listo && filas.length === 0 && cargarResumen && (
              <p className="text-sm text-slate-600">No tiene datos asociados.</p>
            )}

            {aviso && <p className="text-xs text-slate-500">{aviso}</p>}
            <p className="text-xs font-medium text-red-700">Esta acción no se puede deshacer.</p>

            {exigeTexto && (
              <label className="block text-xs text-slate-500">
                Escribe <span className="font-mono font-semibold text-slate-700">{PALABRA}</span> para confirmar
                <input
                  type="text"
                  value={texto}
                  onChange={(e) => setTexto(e.target.value)}
                  autoFocus
                  className="mt-1 block w-full border border-slate-300 rounded-md px-2 py-1.5 text-sm text-slate-900"
                />
              </label>
            )}

            {error && <p className="text-sm text-red-600">{error}</p>}

            <div className="flex justify-end gap-2 pt-1">
              <button
                type="button"
                onClick={() => setAbierto(false)}
                disabled={borrando}
                className="px-3 py-1.5 rounded-md border border-slate-300 text-sm text-slate-700 hover:bg-slate-50 disabled:opacity-50"
              >
                Cancelar
              </button>
              <button
                type="button"
                onClick={confirmar}
                disabled={borrando || !listo || !confirmado}
                className="px-3 py-1.5 rounded-md bg-red-600 text-white text-sm font-medium hover:bg-red-700 disabled:opacity-40"
              >
                {borrando ? 'Eliminando…' : 'Eliminar definitivamente'}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  )
}
