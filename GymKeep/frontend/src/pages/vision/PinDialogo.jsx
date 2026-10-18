import { useEffect, useRef, useState } from 'react'
import { registrarPedirPin } from '../../api/vision.js'

// Dialogo del PIN de edicion. Aparece solo cuando la API lo pide (VISION_PIN configurado) al
// guardar o quitar una zona o guardar parametros; el PIN se recuerda hasta cerrar la pestana.
export default function PinDialogo() {
  const [pedido, setPedido] = useState(null) // { error, resolver }
  const [pin, setPin] = useState('')
  const entrada = useRef(null)

  useEffect(() => {
    registrarPedirPin((error) => new Promise((resolver) => setPedido({ error, resolver })))
    return () => registrarPedirPin(async () => null)
  }, [])

  useEffect(() => {
    if (pedido) {
      setPin('')
      entrada.current?.focus()
    }
  }, [pedido])

  if (!pedido) return null

  function responder(valor) {
    pedido.resolver(valor)
    setPedido(null)
  }

  const valido = /^\d{4,6}$/.test(pin)

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 px-4"
      onKeyDown={(e) => e.key === 'Escape' && responder(null)}
    >
      <form
        role="dialog"
        aria-modal="true"
        aria-labelledby="pin-titulo"
        onSubmit={(e) => {
          e.preventDefault()
          if (valido) responder(pin)
        }}
        className="w-full max-w-xs rounded-xl bg-white p-5 shadow-xl space-y-3"
      >
        <div>
          <h2 id="pin-titulo" className="font-semibold text-slate-900">
            PIN de edición
          </h2>
          <p className="text-xs text-slate-500">Editar zonas y parámetros requiere el PIN de la plataforma.</p>
        </div>
        <input
          ref={entrada}
          type="password"
          inputMode="numeric"
          autoComplete="off"
          maxLength={6}
          value={pin}
          onChange={(e) => setPin(e.target.value.replace(/\D/g, ''))}
          aria-label="PIN de 4 a 6 dígitos"
          aria-invalid={Boolean(pedido.error)}
          className="w-full rounded-lg border border-slate-300 px-3 py-2 text-center text-lg tracking-[0.5em]"
        />
        {pedido.error && (
          <p role="alert" className="text-xs text-red-600">
            {pedido.error}
          </p>
        )}
        <div className="flex gap-2">
          <button
            type="button"
            onClick={() => responder(null)}
            className="flex-1 px-3 py-2 rounded-lg border border-slate-300 text-sm text-slate-700 hover:bg-slate-50"
          >
            Cancelar
          </button>
          <button
            type="submit"
            disabled={!valido}
            className="flex-1 px-3 py-2 rounded-lg bg-slate-800 text-white text-sm font-medium hover:bg-slate-900 disabled:opacity-40"
          >
            Continuar
          </button>
        </div>
      </form>
    </div>
  )
}
