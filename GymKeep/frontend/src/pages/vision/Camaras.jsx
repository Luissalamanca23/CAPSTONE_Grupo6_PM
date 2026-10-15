import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../../api/client.js'
import { visionApi } from '../../api/vision.js'
import { haceCuanto } from './uso.js'

export function ChipSenal({ camara }) {
  if (camara.en_linea) {
    return (
      <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-700">
        <span className="relative flex w-2 h-2">
          <span className="absolute inline-flex h-full w-full rounded-full bg-emerald-500 opacity-60 animate-ping" />
          <span className="relative inline-flex rounded-full w-2 h-2 bg-emerald-500" />
        </span>
        En línea
      </span>
    )
  }
  return (
    <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-slate-100 text-slate-600">
      <span className="w-2 h-2 rounded-full bg-slate-400" />
      Sin señal{camara.ultima_conexion ? ` · ${haceCuanto(camara.ultima_conexion)}` : ''}
    </span>
  )
}

function TarjetaCamara({ camara, marca }) {
  return (
    <Link
      to={`/camaras/${camara.id}`}
      className="group bg-white rounded-lg border border-slate-200 shadow-sm overflow-hidden hover:border-emerald-400 hover:shadow transition"
    >
      <div className="relative bg-slate-900 aspect-video">
        {camara.tiene_cuadro ? (
          <img
            src={visionApi.urlCuadro(camara.id, marca)}
            alt={`Imagen de ${camara.nombre}`}
            className="w-full h-full object-cover"
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center text-xs text-slate-400">Sin imagen todavía</div>
        )}
        <div className="absolute top-2 left-2">
          <ChipSenal camara={camara} />
        </div>
      </div>
      <div className="p-4">
        <p className="font-semibold text-slate-900 group-hover:text-emerald-700">{camara.nombre}</p>
        <p className="text-xs text-slate-500 mt-0.5">
          {camara.codigo} · {camara.maquinas} máquina{camara.maquinas === 1 ? '' : 's'} con zona
        </p>
      </div>
    </Link>
  )
}

function FormularioCamara({ onCreada }) {
  const [sucursales, setSucursales] = useState([])
  const [zonas, setZonas] = useState([])
  const [datos, setDatos] = useState({ codigo: '', nombre: '', sucursal_id: '', zona_id: '', rtsp_url: '' })
  const [error, setError] = useState(null)

  useEffect(() => {
    api.listarSucursales().then((lista) => {
      setSucursales(lista)
      if (lista.length === 1) setDatos((d) => ({ ...d, sucursal_id: String(lista[0].id) }))
    })
  }, [])
  useEffect(() => {
    if (datos.sucursal_id) api.listarZonas(datos.sucursal_id).then(setZonas)
  }, [datos.sucursal_id])

  const campo = (clave) => ({ value: datos[clave], onChange: (e) => setDatos({ ...datos, [clave]: e.target.value }) })

  async function guardar(e) {
    e.preventDefault()
    setError(null)
    try {
      await visionApi.crearCamara({
        codigo: datos.codigo.trim(),
        nombre: datos.nombre.trim(),
        sucursal_id: Number(datos.sucursal_id),
        zona_id: datos.zona_id ? Number(datos.zona_id) : null,
        rtsp_url: datos.rtsp_url.trim() || null,
      })
      onCreada()
    } catch (err) {
      setError(err.message)
    }
  }

  const estiloCampo = 'w-full rounded-lg border border-slate-300 px-3 py-2 text-sm'
  return (
    <form onSubmit={guardar} className="bg-white rounded-lg border border-slate-200 shadow-sm p-5 grid sm:grid-cols-2 lg:grid-cols-5 gap-3 items-end">
      <label className="text-sm text-slate-600">
        Código
        <input required placeholder="CAM-02" className={estiloCampo} {...campo('codigo')} />
      </label>
      <label className="text-sm text-slate-600">
        Nombre
        <input required placeholder="Cámara zona fuerza" className={estiloCampo} {...campo('nombre')} />
      </label>
      <label className="text-sm text-slate-600">
        Sucursal
        <select required className={estiloCampo} {...campo('sucursal_id')}>
          <option value="">Elegir…</option>
          {sucursales.map((s) => (
            <option key={s.id} value={s.id}>
              {s.nombre}
            </option>
          ))}
        </select>
      </label>
      <label className="text-sm text-slate-600">
        Zona
        <select className={estiloCampo} {...campo('zona_id')}>
          <option value="">Sin zona</option>
          {zonas.map((z) => (
            <option key={z.id} value={z.id}>
              {z.nombre}
            </option>
          ))}
        </select>
      </label>
      <label className="text-sm text-slate-600">
        URL RTSP (opcional)
        <input placeholder="rtsp://…" className={estiloCampo} {...campo('rtsp_url')} />
      </label>
      <div className="sm:col-span-2 lg:col-span-5 flex items-center gap-3">
        <button type="submit" className="px-4 py-2 rounded-lg bg-emerald-600 text-white text-sm font-medium hover:bg-emerald-700">
          Guardar cámara
        </button>
        {error && <p className="text-sm text-red-600">{error}</p>}
      </div>
    </form>
  )
}

export default function Camaras() {
  const [camaras, setCamaras] = useState(null)
  const [error, setError] = useState(null)
  const [creando, setCreando] = useState(false)
  const [marca, setMarca] = useState(Date.now())

  function cargar() {
    return visionApi
      .listarCamaras()
      .then((lista) => (setCamaras(lista), setMarca(Date.now()), setError(null)))
      .catch((err) => setError(err.message))
  }

  useEffect(() => {
    cargar()
    const temporizador = setInterval(cargar, 5000)
    return () => clearInterval(temporizador)
  }, [])

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Cámaras</h1>
          <p className="text-sm text-slate-500">
            Señal en vivo de cada cámara y las zonas donde están las máquinas que mide.
          </p>
        </div>
        <button
          type="button"
          onClick={() => setCreando(!creando)}
          className="self-start px-4 py-2 rounded-lg bg-emerald-600 text-white text-sm font-medium hover:bg-emerald-700"
        >
          {creando ? 'Cancelar' : 'Agregar cámara'}
        </button>
      </div>

      {creando && <FormularioCamara onCreada={() => (setCreando(false), cargar())} />}
      {error && <p className="text-sm text-red-600">No se pudieron cargar las cámaras: {error}</p>}
      {camaras === null && !error && <p className="text-sm text-slate-500">Cargando…</p>}
      {camaras && camaras.length === 0 && <p className="text-sm text-slate-500">Todavía no hay cámaras registradas.</p>}

      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">
        {(camaras || []).map((c) => (
          <TarjetaCamara key={c.id} camara={c} marca={marca} />
        ))}
      </div>
    </div>
  )
}
