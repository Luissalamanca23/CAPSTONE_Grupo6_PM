import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api/client.js'
import EstadoBadge from '../components/EstadoBadge.jsx'

const ESTADOS_EQUIPO = ['operativo', 'en_mantenimiento', 'fuera_de_servicio']
const FORM_INICIAL = { codigo_qr: '', nombre: '', marca: '', modelo: '', ubicacion: '' }

function Campo({ etiqueta, valor, onChange, requerido }) {
  return (
    <label className="text-xs text-slate-500 flex flex-col gap-1">
      {etiqueta}
      <input
        type="text"
        value={valor}
        required={requerido}
        onChange={(e) => onChange(e.target.value)}
        className="border border-slate-300 rounded-md px-2 py-1.5 text-sm text-slate-900"
      />
    </label>
  )
}

export default function Equipos() {
  const [equipos, setEquipos] = useState([])
  const [cargando, setCargando] = useState(true)
  const [error, setError] = useState(null)
  const [form, setForm] = useState(FORM_INICIAL)
  const [enviando, setEnviando] = useState(false)
  const [mostrarFormulario, setMostrarFormulario] = useState(false)

  function cargarEquipos() {
    setCargando(true)
    api
      .listarEquipos()
      .then(setEquipos)
      .catch((err) => setError(err.message))
      .finally(() => setCargando(false))
  }

  useEffect(cargarEquipos, [])

  async function manejarEnvio(evento) {
    evento.preventDefault()
    setEnviando(true)
    setError(null)
    try {
      await api.crearEquipo(form)
      setForm(FORM_INICIAL)
      setMostrarFormulario(false)
      cargarEquipos()
    } catch (err) {
      setError(err.message)
    } finally {
      setEnviando(false)
    }
  }

  async function cambiarEstado(equipo, nuevoEstado) {
    try {
      await api.actualizarEquipo(equipo.id, { estado: nuevoEstado })
      cargarEquipos()
    } catch (err) {
      setError(err.message)
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-slate-900">Equipamiento</h1>
        <button
          onClick={() => setMostrarFormulario((v) => !v)}
          className="bg-emerald-600 text-white rounded-md px-4 py-2 text-sm font-medium hover:bg-emerald-700"
        >
          {mostrarFormulario ? 'Cancelar' : '+ Registrar equipo'}
        </button>
      </div>

      {mostrarFormulario && (
        <form
          onSubmit={manejarEnvio}
          className="bg-white rounded-lg border border-slate-200 shadow-sm p-5 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3 items-end"
        >
          <Campo etiqueta="Código QR" valor={form.codigo_qr} onChange={(v) => setForm({ ...form, codigo_qr: v })} requerido />
          <Campo etiqueta="Nombre" valor={form.nombre} onChange={(v) => setForm({ ...form, nombre: v })} requerido />
          <Campo etiqueta="Marca" valor={form.marca} onChange={(v) => setForm({ ...form, marca: v })} />
          <Campo etiqueta="Modelo" valor={form.modelo} onChange={(v) => setForm({ ...form, modelo: v })} />
          <Campo etiqueta="Ubicación" valor={form.ubicacion} onChange={(v) => setForm({ ...form, ubicacion: v })} />
          <button
            type="submit"
            disabled={enviando}
            className="bg-emerald-600 text-white rounded-md px-4 py-2 text-sm font-medium hover:bg-emerald-700 disabled:opacity-50 sm:col-span-2 lg:col-span-1"
          >
            {enviando ? 'Guardando...' : 'Guardar'}
          </button>
        </form>
      )}

      {error && <p className="text-red-600 text-sm">{error}</p>}

      <div className="bg-white rounded-lg border border-slate-200 shadow-sm overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="text-left text-slate-500 bg-slate-50">
            <tr>
              <th className="px-5 py-2">QR</th>
              <th className="px-5 py-2">Nombre</th>
              <th className="px-5 py-2">Ubicación</th>
              <th className="px-5 py-2">Estado</th>
              <th className="px-5 py-2">Cambiar estado</th>
              <th className="px-5 py-2"></th>
            </tr>
          </thead>
          <tbody>
            {cargando && (
              <tr>
                <td className="px-5 py-4 text-slate-400" colSpan={6}>Cargando...</td>
              </tr>
            )}
            {!cargando && equipos.length === 0 && (
              <tr>
                <td className="px-5 py-4 text-slate-400" colSpan={6}>
                  Todavía no hay equipos registrados.
                </td>
              </tr>
            )}
            {equipos.map((equipo) => (
              <tr key={equipo.id} className="border-t border-slate-100">
                <td className="px-5 py-2">
                  <img src={api.urlCodigoQr(equipo.id)} alt="QR" className="w-10 h-10 border border-slate-200 rounded" />
                </td>
                <td className="px-5 py-2">
                  <Link to={`/equipos/${equipo.id}`} className="font-medium text-slate-900 hover:text-emerald-700">
                    {equipo.nombre}
                  </Link>
                  <p className="text-xs text-slate-400 font-mono">{equipo.codigo_qr}</p>
                </td>
                <td className="px-5 py-2">{equipo.ubicacion || '—'}</td>
                <td className="px-5 py-2">
                  <EstadoBadge estado={equipo.estado} />
                </td>
                <td className="px-5 py-2">
                  <select
                    value={equipo.estado}
                    onChange={(e) => cambiarEstado(equipo, e.target.value)}
                    className="border border-slate-300 rounded-md text-xs px-2 py-1"
                  >
                    {ESTADOS_EQUIPO.map((estado) => (
                      <option key={estado} value={estado}>
                        {estado}
                      </option>
                    ))}
                  </select>
                </td>
                <td className="px-5 py-2">
                  <Link to={`/equipos/${equipo.id}`} className="text-xs font-medium text-emerald-700 underline">
                    Ver detalle
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
