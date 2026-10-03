import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api/client.js'
import EstadoBadge from '../components/EstadoBadge.jsx'
import CategoriaEquipoBadge, { CATEGORIAS_EQUIPO } from '../components/CategoriaEquipoBadge.jsx'
import { getSaludEquipo } from '../utils/saludEquipo.js'

const ESTADOS_EQUIPO = ['operativo', 'en_mantenimiento', 'fuera_de_servicio', 'retirado']
const FORM_INICIAL = {
  sucursal_id: '',
  zona_id: '',
  codigo_activo: '',
  nombre: '',
  categoria: '',
  marca: '',
  modelo: '',
}

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

function SaludChip({ equipo }) {
  const salud = getSaludEquipo(equipo)
  const abiertas = equipo?.incidencias_abiertas ?? 0
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full px-2 py-1 text-xs font-medium ${salud.chip}`}>
      <span className={`w-1.5 h-1.5 rounded-full ${salud.punto}`} />
      {salud.etiqueta}
      {salud.clave !== 'negro' && abiertas > 0 && <span className="opacity-70">({abiertas})</span>}
    </span>
  )
}

export default function Equipos() {
  const [equipos, setEquipos] = useState([])
  const [sucursales, setSucursales] = useState([])
  const [zonas, setZonas] = useState([])
  const [cargando, setCargando] = useState(true)
  const [error, setError] = useState(null)
  const [form, setForm] = useState(FORM_INICIAL)
  const [enviando, setEnviando] = useState(false)
  const [mostrarFormulario, setMostrarFormulario] = useState(false)
  const [busqueda, setBusqueda] = useState('')
  const [filtroEstado, setFiltroEstado] = useState('')
  const [filtroCategoria, setFiltroCategoria] = useState('')

  function cargarEquipos() {
    setCargando(true)
    api
      .listarEquipos()
      .then(setEquipos)
      .catch((err) => setError(err.message))
      .finally(() => setCargando(false))
  }

  useEffect(cargarEquipos, [])

  useEffect(() => {
    api
      .listarSucursales()
      .then((datos) => {
        setSucursales(datos)
        // Si solo hay una sucursal (caso tipico del Capstone), se preselecciona.
        if (datos.length > 0) {
          setForm((f) => (f.sucursal_id ? f : { ...f, sucursal_id: String(datos[0].id) }))
        }
      })
      .catch((err) => setError(err.message))
  }, [])

  useEffect(() => {
    if (!form.sucursal_id) {
      setZonas([])
      return
    }
    api
      .listarZonas(form.sucursal_id)
      .then(setZonas)
      .catch((err) => setError(err.message))
  }, [form.sucursal_id])

  const equiposFiltrados = useMemo(() => {
    const texto = busqueda.trim().toLowerCase()
    return equipos.filter((equipo) => {
      if (filtroEstado && equipo.estado !== filtroEstado) return false
      if (filtroCategoria && equipo.categoria !== filtroCategoria) return false
      if (!texto) return true
      const campos = [equipo.nombre, equipo.codigo_activo, equipo.marca, equipo.modelo, equipo.sucursal?.nombre, equipo.zona?.nombre]
      return campos.some((campo) => campo && campo.toLowerCase().includes(texto))
    })
  }, [equipos, busqueda, filtroEstado, filtroCategoria])

  async function manejarEnvio(evento) {
    evento.preventDefault()
    setEnviando(true)
    setError(null)
    try {
      await api.crearEquipo({
        ...form,
        sucursal_id: Number(form.sucursal_id),
        zona_id: form.zona_id ? Number(form.zona_id) : null,
      })
      setForm((f) => ({ ...FORM_INICIAL, sucursal_id: f.sucursal_id }))
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
          disabled={sucursales.length === 0}
          className="bg-emerald-600 text-white rounded-md px-4 py-2 text-sm font-medium hover:bg-emerald-700 disabled:opacity-50"
        >
          {mostrarFormulario ? 'Cancelar' : '+ Registrar equipo'}
        </button>
      </div>

      {sucursales.length === 0 && !cargando && (
        <p className="text-sm text-amber-700 bg-amber-50 border border-amber-200 rounded-md px-4 py-3">
          Todavía no hay ninguna sucursal registrada. Crea una en{' '}
          <Link to="/sucursales" className="underline font-medium">
            Sucursales
          </Link>{' '}
          antes de registrar equipos.
        </p>
      )}

      {mostrarFormulario && (
        <form
          onSubmit={manejarEnvio}
          className="bg-white rounded-lg border border-slate-200 shadow-sm p-5 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-6 gap-3 items-end"
        >
          <label className="text-xs text-slate-500 flex flex-col gap-1">
            Sucursal
            <select
              value={form.sucursal_id}
              required
              onChange={(e) => setForm({ ...form, sucursal_id: e.target.value, zona_id: '' })}
              className="border border-slate-300 rounded-md px-2 py-1.5 text-sm text-slate-900"
            >
              {sucursales.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.nombre}
                </option>
              ))}
            </select>
          </label>
          <label className="text-xs text-slate-500 flex flex-col gap-1">
            Zona (opcional)
            <select
              value={form.zona_id}
              onChange={(e) => setForm({ ...form, zona_id: e.target.value })}
              className="border border-slate-300 rounded-md px-2 py-1.5 text-sm text-slate-900"
            >
              <option value="">Sin zona</option>
              {zonas.map((z) => (
                <option key={z.id} value={z.id}>
                  {z.nombre}
                </option>
              ))}
            </select>
          </label>
          <Campo
            etiqueta="Código de activo"
            valor={form.codigo_activo}
            onChange={(v) => setForm({ ...form, codigo_activo: v })}
            requerido
          />
          <Campo etiqueta="Nombre" valor={form.nombre} onChange={(v) => setForm({ ...form, nombre: v })} requerido />
          <label className="text-xs text-slate-500 flex flex-col gap-1">
            Categoría
            <select
              value={form.categoria}
              onChange={(e) => setForm({ ...form, categoria: e.target.value })}
              className="border border-slate-300 rounded-md px-2 py-1.5 text-sm text-slate-900"
            >
              <option value="">Sin categoría</option>
              {CATEGORIAS_EQUIPO.map((c) => (
                <option key={c.valor} value={c.valor}>
                  {c.etiqueta}
                </option>
              ))}
            </select>
          </label>
          <Campo etiqueta="Marca" valor={form.marca} onChange={(v) => setForm({ ...form, marca: v })} />
          <Campo etiqueta="Modelo" valor={form.modelo} onChange={(v) => setForm({ ...form, modelo: v })} />
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

      <div className="bg-white rounded-lg border border-slate-200 shadow-sm p-4 flex flex-wrap gap-2 items-center">
        <input
          type="text"
          value={busqueda}
          onChange={(e) => setBusqueda(e.target.value)}
          placeholder="Buscar por nombre, código, marca, sucursal..."
          className="flex-1 min-w-[200px] border border-slate-300 rounded-md px-3 py-1.5 text-sm"
        />
        <select
          value={filtroEstado}
          onChange={(e) => setFiltroEstado(e.target.value)}
          className="border border-slate-300 rounded-md text-sm px-2.5 py-1.5"
        >
          <option value="">Todo estado</option>
          {ESTADOS_EQUIPO.map((estado) => (
            <option key={estado} value={estado}>
              {estado}
            </option>
          ))}
        </select>
        <select
          value={filtroCategoria}
          onChange={(e) => setFiltroCategoria(e.target.value)}
          className="border border-slate-300 rounded-md text-sm px-2.5 py-1.5"
        >
          <option value="">Toda categoría</option>
          {CATEGORIAS_EQUIPO.map((c) => (
            <option key={c.valor} value={c.valor}>
              {c.etiqueta}
            </option>
          ))}
        </select>
        {(busqueda || filtroEstado || filtroCategoria) && (
          <button
            type="button"
            onClick={() => {
              setBusqueda('')
              setFiltroEstado('')
              setFiltroCategoria('')
            }}
            className="text-xs font-medium text-slate-500 underline hover:text-slate-700"
          >
            Limpiar
          </button>
        )}
      </div>

      <div className="bg-white rounded-lg border border-slate-200 shadow-sm overflow-hidden">
        <div className="overflow-auto max-h-[65vh]">
        <table className="w-full text-sm">
          <thead className="text-left text-slate-500 bg-slate-50 sticky top-0 z-10">
            <tr>
              <th className="px-5 py-2">QR</th>
              <th className="px-5 py-2">Nombre</th>
              <th className="px-5 py-2">Categoría</th>
              <th className="px-5 py-2">Sucursal / zona</th>
              <th className="px-5 py-2">Salud</th>
              <th className="px-5 py-2">Estado</th>
              <th className="px-5 py-2">Cambiar estado</th>
              <th className="px-5 py-2"></th>
            </tr>
          </thead>
          <tbody>
            {cargando && (
              <tr>
                <td className="px-5 py-4 text-slate-400" colSpan={8}>Cargando...</td>
              </tr>
            )}
            {!cargando && equiposFiltrados.length === 0 && (
              <tr>
                <td className="px-5 py-4 text-slate-400" colSpan={8}>
                  {equipos.length === 0
                    ? 'Todavía no hay equipos registrados.'
                    : 'Ningún equipo coincide con esta búsqueda.'}
                </td>
              </tr>
            )}
            {equiposFiltrados.map((equipo) => {
              const salud = getSaludEquipo(equipo)
              return (
                <tr key={equipo.id} className={`border-t border-slate-100 border-l-4 ${salud.borde} ${salud.fila}`}>
                  <td className="px-5 py-2">
                    <img src={api.urlCodigoQr(equipo.id)} alt="QR" className="w-10 h-10 border border-slate-200 rounded" />
                  </td>
                  <td className="px-5 py-2">
                    <Link to={`/equipos/${equipo.id}`} className="font-medium text-slate-900 hover:text-emerald-700">
                      {equipo.nombre}
                    </Link>
                    <p className="text-xs text-slate-400 font-mono">{equipo.codigo_activo}</p>
                  </td>
                  <td className="px-5 py-2">
                    <CategoriaEquipoBadge categoria={equipo.categoria} />
                  </td>
                  <td className="px-5 py-2">
                    {equipo.sucursal?.nombre || '—'}
                    {equipo.zona?.nombre ? ` · ${equipo.zona.nombre}` : ''}
                  </td>
                  <td className="px-5 py-2">
                    <SaludChip equipo={equipo} />
                  </td>
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
                    <div className="flex items-center gap-3">
                      <Link to={`/equipos/${equipo.id}`} className="text-xs font-medium text-emerald-700 underline">
                        Ver detalle
                      </Link>
                      {(equipo.incidencias_abiertas ?? 0) > 0 && (
                        <Link
                          to={`/equipos/${equipo.id}?mantenimiento=1`}
                          className="text-xs font-medium text-slate-500 underline hover:text-slate-700"
                          title="Abre el detalle con el formulario de mantenimiento ya desplegado."
                        >
                          Resolver ({equipo.incidencias_abiertas})
                        </Link>
                      )}
                    </div>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
        </div>
      </div>
    </div>
  )
}
