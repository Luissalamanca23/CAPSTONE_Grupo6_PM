import { useEffect, useRef, useState } from 'react'
import { Navigate, useLocation, useNavigate } from 'react-router-dom'
import { api } from '../api/client.js'
import { useAuth } from '../auth/AuthContext.jsx'
import { formatearRun, runCanonico } from '../utils/run.js'

const CAMPO =
  'mt-1 block w-full rounded-lg border border-zinc-600 bg-zinc-900 px-3 py-2.5 text-white placeholder-zinc-500 focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-600'

export default function Login() {
  const { usuario, iniciarSesion } = useAuth()
  const ubicacion = useLocation()
  const navegar = useNavigate()
  const destino = ubicacion.state?.desde || '/'

  const [run, setRun] = useState('')
  const [clave, setClave] = useState('')
  const [verClave, setVerClave] = useState(false)
  const [error, setError] = useState(null)
  const [enviando, setEnviando] = useState(false)
  const [hayUsuarios, setHayUsuarios] = useState(true)
  const campoRun = useRef(null)
  const campoClave = useRef(null)

  useEffect(() => {
    campoRun.current?.focus()
    api.estadoAuth().then((r) => setHayUsuarios(r.hay_usuarios)).catch(() => {})
  }, [])

  if (usuario) return <Navigate to={destino} replace />

  async function enviar(e) {
    e.preventDefault()
    setError(null)
    const canonico = runCanonico(run)
    if (!canonico) {
      setError('El RUN no es válido. Revisa el número y el dígito verificador.')
      campoRun.current?.focus()
      return
    }
    if (!/^\d{4,8}$/.test(clave)) {
      setError('La clave son solo números, de 4 a 8 dígitos.')
      campoClave.current?.focus()
      return
    }
    setEnviando(true)
    try {
      await iniciarSesion(canonico, clave)
      navegar(destino, { replace: true })
    } catch (err) {
      setClave('')
      setError(err.status ? err.message : 'No se pudo conectar con el servidor. Intenta de nuevo.')
      campoClave.current?.focus()
    } finally {
      setEnviando(false)
    }
  }

  return (
    <main className="min-h-screen bg-black flex flex-col items-center justify-center px-4 py-10">
      <img src="/logo.png" alt="GymKeep" className="w-52 max-w-full h-auto" />

      <form onSubmit={enviar} noValidate className="mt-8 w-full max-w-sm rounded-2xl border border-white/10 bg-zinc-950 p-6 space-y-4">
        <div>
          <h1 className="text-3xl text-white">Iniciar sesión</h1>
          <p className="mt-1 text-sm text-zinc-400">Ingresa con tu RUN y tu clave numérica.</p>
        </div>

        {!hayUsuarios && (
          <p role="status" className="rounded-lg border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-sm text-amber-200">
            Todavía no hay cuentas creadas. Crea la primera ejecutando <strong>crear-admin.bat</strong> en la carpeta del proyecto.
          </p>
        )}

        <div>
          <label htmlFor="login-run" className="block text-sm font-medium text-zinc-200">
            RUN
          </label>
          <input
            id="login-run"
            ref={campoRun}
            type="text"
            inputMode="text"
            autoComplete="username"
            autoCapitalize="characters"
            spellCheck={false}
            placeholder="12.345.678-5"
            value={run}
            onChange={(e) => setRun(formatearRun(e.target.value))}
            aria-describedby={error ? 'login-error' : undefined}
            className={CAMPO}
          />
        </div>

        <div>
          <label htmlFor="login-clave" className="block text-sm font-medium text-zinc-200">
            Clave
          </label>
          <div className="relative">
            <input
              id="login-clave"
              ref={campoClave}
              type={verClave ? 'text' : 'password'}
              inputMode="numeric"
              autoComplete="current-password"
              maxLength={8}
              placeholder="4 a 8 números"
              value={clave}
              onChange={(e) => setClave(e.target.value.replace(/\D/g, ''))}
              aria-describedby={error ? 'login-error' : undefined}
              className={`${CAMPO} pr-20`}
            />
            <button
              type="button"
              onClick={() => setVerClave((v) => !v)}
              aria-pressed={verClave}
              className="absolute inset-y-0 right-0 mt-1 mb-0 px-3 text-xs font-semibold text-zinc-400 hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-600 rounded-r-lg"
            >
              {verClave ? 'Ocultar' : 'Mostrar'}
            </button>
          </div>
        </div>

        {error && (
          <p id="login-error" role="alert" className="rounded-lg border border-red-500/40 bg-red-500/10 px-3 py-2 text-sm text-red-200">
            {error}
          </p>
        )}

        <button
          type="submit"
          disabled={enviando}
          className="w-full rounded-lg bg-brand-600 px-4 py-3 text-sm font-bold uppercase tracking-wide text-white hover:bg-brand-700 disabled:opacity-60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white focus-visible:ring-offset-2 focus-visible:ring-offset-zinc-950"
        >
          {enviando ? 'Ingresando…' : 'Ingresar'}
        </button>

        <p className="text-xs text-zinc-500">¿No tienes cuenta o olvidaste tu clave? Pídele a un administrador que la cree o la restablezca.</p>
      </form>
    </main>
  )
}
