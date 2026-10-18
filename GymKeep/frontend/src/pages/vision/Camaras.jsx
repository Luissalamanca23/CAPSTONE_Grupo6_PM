import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../../api/client.js'
import { visionApi } from '../../api/vision.js'
import ConfirmarEliminar from '../../components/ConfirmarEliminar.jsx'
import { haceCuanto } from './uso.js'
import usePolling from './usePolling.js'

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
  // Solo las camaras con senal refrescan su imagen; sin senal se deja la ultima ya cargada.
  const [marcaImagen, setMarcaImagen] = useState(marca)
  const [falloImagen, setFalloImagen] = useState(false)
  useEffect(() => {
    if (camara.en_linea) {
      setMarcaImagen(marca)
      setFalloImagen(false)
    }
  }, [marca, camara.en_linea])

  return (
    <Link
      to={`/camaras/${camara.id}`}
      className="group bg-white rounded-lg border border-slate-200 shadow-sm overflow-hidden hover:border-brand-400 hover:shadow transition"
    >
      <div className="relative bg-slate-900 aspect-video">
        {camara.tiene_cuadro && !falloImagen ? (
          <img
            src={visionApi.urlCuadro(camara.id, marcaImagen)}
            alt={`Imagen de ${camara.nombre}`}
            onError={() => setFalloImagen(true)}
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
        <p className="font-semibold text-slate-900 group-hover:text-brand-700">{camara.nombre}</p>
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
  const [errorCarga, setErrorCarga] = useState(null)

  useEffect(() => {
    api
      .listarSucursales()
      .then((lista) => {
        setSucursales(lista)
        if (lista.length === 1) setDatos((d) => ({ ...d, sucursal_id: String(lista[0].id) }))
      })
      .catch((err) => setErrorCarga(`No se pudieron cargar las sucursales: ${err.message}`))
  }, [])
  useEffect(() => {
    if (!datos.sucursal_id) return
    api
      .listarZonas(datos.sucursal_id)
      .then((lista) => (setZonas(lista), setErrorCarga(null)))
      .catch((err) => setErrorCarga(`No se pudieron cargar las zonas: ${err.message}`))
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
        <button type="submit" className="px-4 py-2 rounded-lg bg-brand-600 text-white text-sm font-medium hover:bg-brand-700">
          Guardar cámara
        </button>
        {(error || errorCarga) && <p className="text-sm text-red-600">{error || errorCarga}</p>}
      </div>
    </form>
  )
}

export default function Camaras() {
  const [camaras, setCamaras] = useState(null)
  const [error, setError] = useState(null)
  const [creando, setCreando] = useState(false)
  const [marca, setMarca] = useState(Date.now())

  const cargar = (vigente = () => true) =>
    visionApi
      .listarCamaras()
      .then((lista) => vigente() && (setCamaras(lista), setMarca(Date.now()), setError(null)))
      .catch((err) => vigente() && setError(err.message))

  usePolling(cargar, 5000)

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
          className="self-start px-4 py-2 rounded-lg bg-brand-600 text-white text-sm font-medium hover:bg-brand-700"
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
          <div key={c.id} className="relative">
            <TarjetaCamara camara={c} marca={marca} />
            <div className="absolute top-2 right-2">
              <ConfirmarEliminar
                titulo="Eliminar cámara"
                nombre={c.nombre}
                aviso="Las zonas dibujadas se borran con la cámara. Si el módulo de visión sigue enviando datos con este código, deténlo o la cámara no volverá a aparecer."
                cargarResumen={() => api.resumenEliminacion('camaras', c.id)}
                onConfirmar={() => api.eliminarCamara(c.id)}
                onEliminado={() => cargar()}
                className="px-2 py-1 rounded-md bg-white/90 text-xs font-medium text-red-600 shadow hover:bg-white"
              />
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
