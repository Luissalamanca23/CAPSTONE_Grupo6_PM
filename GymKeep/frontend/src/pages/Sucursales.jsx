import { useEffect, useState } from 'react'
import { api } from '../api/client.js'

const EMPRESA_INICIAL = { razon_social: '' }
const SUCURSAL_INICIAL = { codigo: '', nombre: '', ciudad: '' }
const ZONA_INICIAL = { nombre: '', descripcion: '' }

/** Gestion de la jerarquia empresa → sucursal → zona (ver GymKeep_BDD_Completa). El
 * equipamiento y las camaras siempre se registran dentro de una sucursal/zona, asi que
 * esta pagina debe tener al menos una de cada antes de poder registrar equipos. */
export default function Sucursales() {
  const [empresas, setEmpresas] = useState([])
  const [sucursales, setSucursales] = useState([])
  const [zonasPorSucursal, setZonasPorSucursal] = useState({})
  const [cargando, setCargando] = useState(true)
  const [error, setError] = useState(null)

  const [formEmpresa, setFormEmpresa] = useState(EMPRESA_INICIAL)
  const [formSucursal, setFormSucursal] = useState(SUCURSAL_INICIAL)
  const [formsZona, setFormsZona] = useState({})

  const empresa = empresas[0] || null

  function cargarTodo() {
    setCargando(true)
    api
      .listarEmpresas()
      .then(async (listaEmpresas) => {
        setEmpresas(listaEmpresas)
        if (listaEmpresas.length === 0) {
          setSucursales([])
          return
        }
        const listaSucursales = await api.listarSucursales(listaEmpresas[0].id)
        setSucursales(listaSucursales)
        const zonasEntries = await Promise.all(
          listaSucursales.map((s) => api.listarZonas(s.id).then((zonas) => [s.id, zonas]))
        )
        setZonasPorSucursal(Object.fromEntries(zonasEntries))
      })
      .catch((err) => setError(err.message))
      .finally(() => setCargando(false))
  }

  useEffect(cargarTodo, [])

  async function crearEmpresa(evento) {
    evento.preventDefault()
    setError(null)
    try {
      await api.crearEmpresa(formEmpresa)
      setFormEmpresa(EMPRESA_INICIAL)
      cargarTodo()
    } catch (err) {
      setError(err.message)
    }
  }

  async function crearSucursal(evento) {
    evento.preventDefault()
    setError(null)
    try {
      await api.crearSucursal({ ...formSucursal, empresa_id: empresa.id })
      setFormSucursal(SUCURSAL_INICIAL)
      cargarTodo()
    } catch (err) {
      setError(err.message)
    }
  }

  async function crearZona(sucursalId, evento) {
    evento.preventDefault()
    setError(null)
    const datos = formsZona[sucursalId] || ZONA_INICIAL
    try {
      await api.crearZona({ ...datos, sucursal_id: sucursalId })
      setFormsZona((f) => ({ ...f, [sucursalId]: ZONA_INICIAL }))
      cargarTodo()
    } catch (err) {
      setError(err.message)
    }
  }

  if (cargando) return <p className="text-slate-500">Cargando...</p>

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-slate-900">Sucursales y zonas</h1>
      {error && <p className="text-red-600 text-sm">{error}</p>}

      {!empresa && (
        <div className="bg-white rounded-lg border border-slate-200 shadow-sm p-5 space-y-3 max-w-md">
          <p className="text-sm text-slate-600">
            Todavía no hay ninguna empresa registrada. Crea la primera para poder registrar
            sucursales y equipamiento.
          </p>
          <form onSubmit={crearEmpresa} className="flex gap-2">
            <input
              type="text"
              required
              placeholder="Nombre de la empresa/gimnasio"
              value={formEmpresa.razon_social}
              onChange={(e) => setFormEmpresa({ razon_social: e.target.value })}
              className="flex-1 border border-slate-300 rounded-md px-3 py-1.5 text-sm"
            />
            <button className="bg-emerald-600 text-white rounded-md px-4 py-1.5 text-sm font-medium hover:bg-emerald-700">
              Crear
            </button>
          </form>
        </div>
      )}

      {empresa && (
        <>
          <div className="bg-white rounded-lg border border-slate-200 shadow-sm p-5 space-y-3">
            <h2 className="font-semibold text-slate-800">Nueva sucursal de {empresa.nombre_fantasia || empresa.razon_social}</h2>
            <form onSubmit={crearSucursal} className="grid grid-cols-1 sm:grid-cols-4 gap-3 items-end">
              <label className="text-xs text-slate-500 flex flex-col gap-1">
                Código
                <input
                  type="text"
                  required
                  value={formSucursal.codigo}
                  onChange={(e) => setFormSucursal({ ...formSucursal, codigo: e.target.value })}
                  className="border border-slate-300 rounded-md px-2 py-1.5 text-sm"
                />
              </label>
              <label className="text-xs text-slate-500 flex flex-col gap-1">
                Nombre
                <input
                  type="text"
                  required
                  value={formSucursal.nombre}
                  onChange={(e) => setFormSucursal({ ...formSucursal, nombre: e.target.value })}
                  className="border border-slate-300 rounded-md px-2 py-1.5 text-sm"
                />
              </label>
              <label className="text-xs text-slate-500 flex flex-col gap-1">
                Ciudad
                <input
                  type="text"
                  value={formSucursal.ciudad}
                  onChange={(e) => setFormSucursal({ ...formSucursal, ciudad: e.target.value })}
                  className="border border-slate-300 rounded-md px-2 py-1.5 text-sm"
                />
              </label>
              <button className="bg-emerald-600 text-white rounded-md px-4 py-2 text-sm font-medium hover:bg-emerald-700">
                + Agregar sucursal
              </button>
            </form>
          </div>

          <div className="space-y-4">
            {sucursales.length === 0 && (
              <p className="text-sm text-slate-400">Todavía no hay sucursales registradas.</p>
            )}
            {sucursales.map((sucursal) => (
              <div key={sucursal.id} className="bg-white rounded-lg border border-slate-200 shadow-sm">
                <div className="px-5 py-3 border-b border-slate-100 flex items-center justify-between">
                  <div>
                    <p className="font-semibold text-slate-900">{sucursal.nombre}</p>
                    <p className="text-xs text-slate-400 font-mono">{sucursal.codigo}</p>
                  </div>
                  <span className="text-xs text-slate-400">{sucursal.ciudad}</span>
                </div>
                <div className="px-5 py-3 space-y-3">
                  <p className="text-xs font-medium text-slate-500">Zonas</p>
                  <div className="flex flex-wrap gap-2">
                    {(zonasPorSucursal[sucursal.id] || []).map((zona) => (
                      <span
                        key={zona.id}
                        className="inline-block px-2.5 py-1 rounded-full text-xs font-medium bg-slate-100 text-slate-600"
                      >
                        {zona.nombre}
                      </span>
                    ))}
                    {(zonasPorSucursal[sucursal.id] || []).length === 0 && (
                      <span className="text-xs text-slate-400">Sin zonas todavía.</span>
                    )}
                  </div>
                  <form
                    onSubmit={(e) => crearZona(sucursal.id, e)}
                    className="flex gap-2 max-w-sm"
                  >
                    <input
                      type="text"
                      required
                      placeholder="Nueva zona (ej. Cardio)"
                      value={formsZona[sucursal.id]?.nombre || ''}
                      onChange={(e) =>
                        setFormsZona((f) => ({
                          ...f,
                          [sucursal.id]: { ...(f[sucursal.id] || ZONA_INICIAL), nombre: e.target.value },
                        }))
                      }
                      className="flex-1 border border-slate-300 rounded-md px-2 py-1.5 text-xs"
                    />
                    <button className="text-xs font-medium text-emerald-700 border border-emerald-200 rounded-md px-3 py-1.5 hover:bg-emerald-50">
                      + Zona
                    </button>
                  </form>
                </div>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  )
}
