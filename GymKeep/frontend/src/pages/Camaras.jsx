import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api/client.js'
import Paginacion from '../components/Paginacion.jsx'
import { formatearFechaHora } from '../utils/formato.js'
import { usePaginacion } from '../utils/paginacion.js'

const FORM_INICIAL = { codigo: '', nombre: '', sucursal_id: '' }

function EstadoConexion({ camara }) {
  if (camara.en_linea) {
    return <span className="inline-block px-2.5 py-1 rounded-full text-xs font-semibold bg-emerald-100 text-emerald-700">En línea</span>
  }
  return (
    <span className="inline-block px-2.5 py-1 rounded-full text-xs font-semibold bg-slate-200 text-slate-600">
      {camara.ultima_conexion ? `Sin señal · ${formatearFechaHora(camara.ultima_conexion)}` : 'Sin señal'}
    </span>
  )
}

function TarjetaCamara({ camara, marca }) {
  const [imagenFallo, setImagenFallo] = useState(false)

  return (
    <Link
      to={`/camaras/${camara.id}`}
      className="bg-white rounded-lg border border-slate-200 shadow-sm overflow-hidden hover:border-emerald-400 transition-colors flex flex-col"
    >
      <div className="aspect-video bg-slate-900 flex items-center justify-center">
        {camara.tiene_cuadro && !imagenFallo ? (
          <img
            src={api.urlCuadroCamara(camara.id, marca)}
            alt={`Imagen de ${camara.nombre}`}
            onError={() => setImagenFallo(true)}
            className="w-full h-full object-cover"
          />
        ) : (
          <p className="text-xs text-slate-400 px-4 text-center">Sin imagen todavía</p>
        )}
      </div>
      <div className="p-4 space-y-2">
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0">
            <h2 className="font-semibold text-slate-900 truncate">{camara.nombre}</h2>
            <p className="text-xs text-slate-400 font-mono">{camara.codigo}</p>
          </div>
          <EstadoConexion camara={camara} />
        </div>
        <p className="text-sm text-slate-500">
          {camara.maquinas === 0
            ? 'Sin máquinas con zona definida'
            : `${camara.maquinas} máquina${camara.maquinas === 1 ? '' : 's'} con zona definida`}
        </p>
      </div>
    </Link>
  )
}

// Listado de camaras: ultima imagen, si el pipeline esta enviando datos y cuantas maquinas
// tienen zona. Desde cada una se editan las zonas y los parametros de deteccion.
export default function Camaras() {
  const [camaras, setCamaras] = useState([])
  const [sucursales, setSucursales] = useState([])
  const [cargando, setCargando] = useState(true)
  const [error, setError] = useState(null)
  const [marca, setMarca] = useState(() => Date.now())
  const paginacion = usePaginacion(camaras, 9)

  const [mostrarForm, setMostrarForm] = useState(false)
  const [form, setForm] = useState(FORM_INICIAL)
  const [guardando, setGuardando] = useState(false)
  const [errorForm, setErrorForm] = useState(null)

  function cargar() {
    return api
      .listarCamaras()
      .then((datos) => {
        setCamaras(datos)
        setMarca(Date.now())
        setError(null)
      })
      .catch((err) => setError(err.message))
      .finally(() => setCargando(false))
  }

  useEffect(() => {
    cargar()
    api.listarSucursales().then(setSucursales).catch(() => {})
    // Refresca el estado "En línea" y las miniaturas cada 10 s.
    const temporizador = setInterval(cargar, 10000)
    return () => clearInterval(temporizador)
  }, [])

  async function crear(evento) {
    evento.preventDefault()
    setGuardando(true)
    setErrorForm(null)
    try {
      await api.crearCamara({
        codigo: form.codigo.trim(),
        nombre: form.nombre.trim(),
        sucursal_id: Number(form.sucursal_id),
      })
      setForm(FORM_INICIAL)
      setMostrarForm(false)
      await cargar()
    } catch (err) {
      setErrorForm(err.message)
    } finally {
      setGuardando(false)
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-2">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Cámaras</h1>
          <p className="text-sm text-slate-500">Imagen en vivo, zonas de cada máquina y parámetros de detección.</p>
        </div>
        <button
          type="button"
          onClick={() => setMostrarForm((visible) => !visible)}
          className="bg-emerald-600 hover:bg-emerald-700 text-white text-sm font-medium rounded-md px-4 py-2"
        >
          {mostrarForm ? 'Cancelar' : 'Agregar cámara'}
        </button>
      </div>

      {mostrarForm && (
        <form onSubmit={crear} className="bg-white rounded-lg border border-slate-200 shadow-sm p-5 grid gap-3 sm:grid-cols-4 items-end">
          <label className="text-sm text-slate-600 flex flex-col gap-1">
            Código
            <input
              id="camara-codigo"
              required
              value={form.codigo}
              onChange={(e) => setForm({ ...form, codigo: e.target.value })}
              placeholder="CAM-02"
              className="border border-slate-300 rounded-md px-3 py-1.5 text-sm"
            />
          </label>
          <label className="text-sm text-slate-600 flex flex-col gap-1">
            Nombre
            <input
              id="camara-nombre"
              required
              value={form.nombre}
              onChange={(e) => setForm({ ...form, nombre: e.target.value })}
              placeholder="Cámara zona cardio"
              className="border border-slate-300 rounded-md px-3 py-1.5 text-sm"
            />
          </label>
          <label className="text-sm text-slate-600 flex flex-col gap-1">
            Sucursal
            <select
              id="camara-sucursal"
              required
              value={form.sucursal_id}
              onChange={(e) => setForm({ ...form, sucursal_id: e.target.value })}
              className="border border-slate-300 rounded-md px-2.5 py-1.5 text-sm"
            >
              <option value="">Elegir...</option>
              {sucursales.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.nombre}
                </option>
              ))}
            </select>
          </label>
          <button
            type="submit"
            disabled={guardando}
            className="bg-slate-900 hover:bg-slate-800 text-white text-sm font-medium rounded-md px-4 py-2 disabled:opacity-50"
          >
            {guardando ? 'Guardando...' : 'Crear cámara'}
          </button>
          {errorForm && <p className="text-red-600 text-sm sm:col-span-4">{errorForm}</p>}
        </form>
      )}

      {error && <p className="text-red-600 text-sm">{error}</p>}
      {cargando && <p className="text-slate-500">Cargando...</p>}
      {!cargando && camaras.length === 0 && (
        <p className="text-slate-400 text-sm">Todavía no hay cámaras registradas. Agrega una para empezar.</p>
      )}

      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">
        {paginacion.visibles.map((camara) => (
          <TarjetaCamara key={camara.id} camara={camara} marca={marca} />
        ))}
      </div>

      {paginacion.total > paginacion.porPagina && (
        <div className="bg-white rounded-lg border border-slate-200 shadow-sm">
          <Paginacion paginacion={paginacion} />
        </div>
      )}
    </div>
  )
}
