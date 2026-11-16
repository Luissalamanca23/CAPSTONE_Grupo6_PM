import { useEffect, useState } from 'react'
import { api } from '../api/client.js'
import { useAuth } from '../auth/AuthContext.jsx'
import Paginacion from '../components/Paginacion.jsx'
import { usePaginacion } from '../utils/paginacion.js'
import { formatearFechaHora } from '../utils/formato.js'
import { formatearRun, runCanonico } from '../utils/run.js'

const ROLES = { admin: 'Administrador', tecnico: 'Técnico' }
const INICIAL = { run: '', nombre: '', rol: 'tecnico', clave: '' }
const ENTRADA = 'border border-slate-300 rounded-md px-2 py-1.5 text-sm'
const BOTON_LINK = 'text-xs font-medium text-brand-700 underline hover:text-brand-800'

/** Cuentas del panel (solo administradores): crear, cambiar rol, desactivar y restablecer la clave. */
export default function Usuarios() {
  const { usuario: yo } = useAuth()
  const [lista, setLista] = useState([])
  const [cargando, setCargando] = useState(true)
  const [error, setError] = useState(null)
  const [aviso, setAviso] = useState(null)
  const [form, setForm] = useState(INICIAL)
  const [guardando, setGuardando] = useState(false)
  const [restableciendo, setRestableciendo] = useState(null) // { id, clave }
  const paginacion = usePaginacion(lista, 10)

  function cargar() {
    return api
      .listarUsuarios()
      .then(setLista)
      .catch((err) => setError(err.message))
      .finally(() => setCargando(false))
  }

  useEffect(() => {
    cargar()
  }, [])

  function mostrar(mensaje) {
    setError(null)
    setAviso(mensaje)
  }

  async function ejecutar(accion, mensajeOk) {
    setError(null)
    setAviso(null)
    try {
      await accion()
      await cargar()
      if (mensajeOk) setAviso(mensajeOk)
      return true
    } catch (err) {
      setError(err.message)
      return false
    }
  }

  async function crear(e) {
    e.preventDefault()
    const run = runCanonico(form.run)
    if (!run) return setError('El RUN no es válido. Revisa el número y el dígito verificador.')
    if (!/^\d{4,8}$/.test(form.clave)) return setError('La clave son solo números, de 4 a 8 dígitos.')
    setGuardando(true)
    const ok = await ejecutar(() => api.crearUsuario({ ...form, run }), `Cuenta creada para ${form.nombre.trim()}.`)
    setGuardando(false)
    if (ok) setForm(INICIAL)
  }

  async function restablecer(e, cuenta) {
    e.preventDefault()
    if (!/^\d{4,8}$/.test(restableciendo.clave)) return setError('La clave son solo números, de 4 a 8 dígitos.')
    const ok = await ejecutar(
      () => api.actualizarUsuario(cuenta.id, { clave: restableciendo.clave }),
      `Clave restablecida para ${cuenta.nombre}. Sus sesiones abiertas se cerraron.`,
    )
    if (ok) setRestableciendo(null)
  }

  return (
    <div className="space-y-6 max-w-5xl">
      <div>
        <h1 className="text-3xl">Usuarios</h1>
        <p className="text-sm text-slate-500">
          Quién puede entrar al panel. Los técnicos gestionan equipos, incidencias y cámaras; solo los administradores eliminan datos y administran cuentas.
        </p>
      </div>

      {error && (
        <p role="alert" className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
          {error}
        </p>
      )}
      {aviso && (
        <p role="status" className="rounded-lg border border-green-200 bg-green-50 px-3 py-2 text-sm text-green-800">
          {aviso}
        </p>
      )}

      <form onSubmit={crear} noValidate className="bg-white rounded-lg border border-slate-200 shadow-sm p-5 space-y-3">
        <h2 className="font-semibold text-slate-800">Nueva cuenta</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3 items-end">
          <label htmlFor="nu-run" className="text-xs text-slate-500 flex flex-col gap-1">
            RUN
            <input id="nu-run" type="text" required autoComplete="off" placeholder="12.345.678-5" value={form.run} onChange={(e) => setForm({ ...form, run: formatearRun(e.target.value) })} className={ENTRADA} />
          </label>
          <label htmlFor="nu-nombre" className="text-xs text-slate-500 flex flex-col gap-1 lg:col-span-2">
            Nombre completo
            <input id="nu-nombre" type="text" required autoComplete="off" value={form.nombre} onChange={(e) => setForm({ ...form, nombre: e.target.value })} className={ENTRADA} />
          </label>
          <label htmlFor="nu-rol" className="text-xs text-slate-500 flex flex-col gap-1">
            Rol
            <select id="nu-rol" value={form.rol} onChange={(e) => setForm({ ...form, rol: e.target.value })} className={ENTRADA}>
              <option value="tecnico">Técnico</option>
              <option value="admin">Administrador</option>
            </select>
          </label>
          <label htmlFor="nu-clave" className="text-xs text-slate-500 flex flex-col gap-1">
            Clave (4 a 8 números)
            <input id="nu-clave" type="password" inputMode="numeric" autoComplete="new-password" maxLength={8} value={form.clave} onChange={(e) => setForm({ ...form, clave: e.target.value.replace(/\D/g, '') })} className={ENTRADA} />
          </label>
        </div>
        <button disabled={guardando} className="bg-brand-600 text-white rounded-md px-4 py-2 text-sm font-medium hover:bg-brand-700 disabled:opacity-60">
          {guardando ? 'Creando…' : '+ Crear cuenta'}
        </button>
      </form>

      <div className="bg-white rounded-lg border border-slate-200 shadow-sm overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-xs uppercase tracking-wide text-slate-500 border-b border-slate-100">
              <th className="px-4 py-3 font-semibold">Nombre</th>
              <th className="px-4 py-3 font-semibold">RUN</th>
              <th className="px-4 py-3 font-semibold">Rol</th>
              <th className="px-4 py-3 font-semibold">Estado</th>
              <th className="px-4 py-3 font-semibold">Último acceso</th>
              <th className="px-4 py-3 font-semibold">Acciones</th>
            </tr>
          </thead>
          <tbody>
            {cargando && (
              <tr>
                <td colSpan={6} className="px-4 py-6 text-center text-slate-400">
                  Cargando…
                </td>
              </tr>
            )}
            {paginacion.visibles.map((c) => {
              const esYo = c.id === yo?.id
              return (
                <tr key={c.id} className="border-b border-slate-50 align-top">
                  <td className="px-4 py-3 font-medium text-slate-900">
                    {c.nombre}
                    {esYo && <span className="ml-2 text-xs font-normal text-slate-400">(tú)</span>}
                  </td>
                  <td className="px-4 py-3 font-mono text-slate-600">{formatearRun(c.run)}</td>
                  <td className="px-4 py-3">
                    <label htmlFor={`rol-${c.id}`} className="sr-only">
                      Rol de {c.nombre}
                    </label>
                    <select
                      id={`rol-${c.id}`}
                      value={c.rol}
                      disabled={esYo}
                      title={esYo ? 'No puedes cambiar tu propio rol' : undefined}
                      onChange={(e) => ejecutar(() => api.actualizarUsuario(c.id, { rol: e.target.value }), `Rol de ${c.nombre} actualizado.`)}
                      className="border border-slate-300 rounded-md px-2 py-1 text-xs disabled:bg-slate-50 disabled:text-slate-500"
                    >
                      {Object.entries(ROLES).map(([valor, texto]) => (
                        <option key={valor} value={valor}>
                          {texto}
                        </option>
                      ))}
                    </select>
                  </td>
                  <td className="px-4 py-3">
                    <span className={`inline-block rounded-full px-2.5 py-0.5 text-xs font-medium ${c.activo ? 'bg-green-100 text-green-800' : 'bg-slate-200 text-slate-600'}`}>
                      {c.activo ? 'Activa' : 'Desactivada'}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-xs text-slate-500">{c.ultimo_acceso ? formatearFechaHora(c.ultimo_acceso) : 'Nunca'}</td>
                  <td className="px-4 py-3">
                    <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
                      {!esYo && (
                        <button type="button" className={BOTON_LINK} onClick={() => ejecutar(() => api.actualizarUsuario(c.id, { activo: !c.activo }), c.activo ? `${c.nombre} ya no puede entrar.` : `${c.nombre} puede volver a entrar.`)}>
                          {c.activo ? 'Desactivar' : 'Activar'}
                        </button>
                      )}
                      {!esYo && (
                        <button type="button" className={BOTON_LINK} onClick={() => setRestableciendo({ id: c.id, clave: '' })}>
                          Restablecer clave
                        </button>
                      )}
                    </div>
                    {restableciendo?.id === c.id && (
                      <form onSubmit={(e) => restablecer(e, c)} className="mt-2 flex items-center gap-2">
                        <label htmlFor={`rc-${c.id}`} className="sr-only">
                          Nueva clave de {c.nombre}
                        </label>
                        <input
                          id={`rc-${c.id}`}
                          type="password"
                          inputMode="numeric"
                          autoComplete="new-password"
                          autoFocus
                          maxLength={8}
                          placeholder="Nueva clave"
                          value={restableciendo.clave}
                          onChange={(e) => setRestableciendo({ id: c.id, clave: e.target.value.replace(/\D/g, '') })}
                          className={`${ENTRADA} w-32`}
                        />
                        <button className="bg-brand-600 text-white rounded-md px-3 py-1.5 text-xs font-medium hover:bg-brand-700">Guardar</button>
                        <button type="button" className="text-xs text-slate-500 underline" onClick={() => setRestableciendo(null)}>
                          Cancelar
                        </button>
                      </form>
                    )}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
        <Paginacion paginacion={paginacion} />
      </div>
      <p className="text-xs text-slate-400">Tu propia clave se cambia desde el menú, en “Cambiar mi clave”.</p>
    </div>
  )
}
