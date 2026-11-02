import { useEffect, useRef, useState } from 'react'
import { api } from '../api/client.js'

const CAMPO = 'mt-1 block w-full rounded-md border border-slate-300 px-3 py-2 text-sm'

/** Dialogo para que cada persona cambie su propia clave. Cierra sus otras sesiones abiertas. */
export default function CambiarClaveDialogo({ onCerrar }) {
  const [actual, setActual] = useState('')
  const [nueva, setNueva] = useState('')
  const [repetida, setRepetida] = useState('')
  const [error, setError] = useState(null)
  const [listo, setListo] = useState(false)
  const [enviando, setEnviando] = useState(false)
  const primero = useRef(null)

  useEffect(() => {
    primero.current?.focus()
  }, [])

  async function enviar(e) {
    e.preventDefault()
    setError(null)
    if (!/^\d{4,8}$/.test(nueva)) return setError('La clave nueva son solo números, de 4 a 8 dígitos.')
    if (nueva !== repetida) return setError('Las dos claves nuevas no coinciden.')
    setEnviando(true)
    try {
      await api.cambiarClave(actual, nueva)
      setListo(true)
    } catch (err) {
      setError(err.message)
    } finally {
      setEnviando(false)
    }
  }

  const soloNumeros = (setter) => (e) => setter(e.target.value.replace(/\D/g, ''))

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 px-4" onKeyDown={(e) => e.key === 'Escape' && onCerrar()}>
      <form
        role="dialog"
        aria-modal="true"
        aria-labelledby="cc-titulo"
        onSubmit={enviar}
        noValidate
        className="w-full max-w-sm rounded-xl bg-white p-5 shadow-xl space-y-3 text-slate-900"
      >
        <h2 id="cc-titulo" className="font-semibold">
          Cambiar mi clave
        </h2>

        {listo ? (
          <>
            <p role="status" className="text-sm text-green-800">
              Listo. Tu clave se cambió y las demás sesiones abiertas se cerraron.
            </p>
            <button type="button" onClick={onCerrar} className="w-full rounded-md bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700">
              Cerrar
            </button>
          </>
        ) : (
          <>
            <label htmlFor="cc-actual" className="block text-xs text-slate-500">
              Clave actual
              <input id="cc-actual" ref={primero} type="password" inputMode="numeric" autoComplete="current-password" maxLength={8} value={actual} onChange={soloNumeros(setActual)} className={CAMPO} />
            </label>
            <label htmlFor="cc-nueva" className="block text-xs text-slate-500">
              Clave nueva (4 a 8 números)
              <input id="cc-nueva" type="password" inputMode="numeric" autoComplete="new-password" maxLength={8} value={nueva} onChange={soloNumeros(setNueva)} className={CAMPO} />
            </label>
            <label htmlFor="cc-repetida" className="block text-xs text-slate-500">
              Repite la clave nueva
              <input id="cc-repetida" type="password" inputMode="numeric" autoComplete="new-password" maxLength={8} value={repetida} onChange={soloNumeros(setRepetida)} className={CAMPO} />
            </label>
            {error && (
              <p role="alert" className="text-sm text-red-700">
                {error}
              </p>
            )}
            <div className="flex justify-end gap-2 pt-1">
              <button type="button" onClick={onCerrar} className="rounded-md px-4 py-2 text-sm text-slate-600 hover:bg-slate-100">
                Cancelar
              </button>
              <button disabled={enviando} className="rounded-md bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700 disabled:opacity-60">
                {enviando ? 'Guardando…' : 'Cambiar clave'}
              </button>
            </div>
          </>
        )}
      </form>
    </div>
  )
}
