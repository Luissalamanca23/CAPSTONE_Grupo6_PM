import { useEffect, useState } from 'react'
import { visionApi } from '../api/vision.js'
import PinDialogo from '../pages/vision/PinDialogo.jsx'

const LADO_MAXIMO = 1280
const TIPOS = 'image/jpeg,image/png,image/webp'

// Las fotos de celular suelen pesar varios MB y la API rechaza mas de 5 MB: se achican en el
// navegador (lado mayor 1280 px, JPEG) antes de subirlas. Si el navegador no puede leer el
// formato, se envia el archivo original y la API responde con un mensaje claro.
export async function reducirImagen(archivo) {
  try {
    const bitmap = await createImageBitmap(archivo)
    const escala = Math.min(1, LADO_MAXIMO / Math.max(bitmap.width, bitmap.height))
    const lienzo = document.createElement('canvas')
    lienzo.width = Math.round(bitmap.width * escala)
    lienzo.height = Math.round(bitmap.height * escala)
    lienzo.getContext('2d').drawImage(bitmap, 0, 0, lienzo.width, lienzo.height)
    const blob = await new Promise((resolver) => lienzo.toBlob(resolver, 'image/jpeg', 0.85))
    return blob || archivo
  } catch {
    return archivo
  }
}

function IconoCamara({ className = 'w-8 h-8' }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className={className} aria-hidden="true">
      <path d="M3 7h3l2-3h8l2 3h3v13H3z" />
      <circle cx="12" cy="13" r="4" />
    </svg>
  )
}

/** Miniatura de la foto de referencia en listados. `tiene` evita pedir fotos que no existen. */
export function Miniatura({ equipoId, nombre, tiene, version = '', className = 'w-12 h-12' }) {
  const [fallo, setFallo] = useState(false)
  if (!tiene || fallo) {
    return (
      <div className={`${className} shrink-0 rounded-md bg-slate-100 text-slate-300 flex items-center justify-center`} title="Sin foto de referencia">
        <IconoCamara className="w-5 h-5" />
      </div>
    )
  }
  return (
    <img
      src={visionApi.urlFoto(equipoId, version)}
      alt={`Foto de ${nombre}`}
      onError={() => setFallo(true)}
      loading="lazy"
      className={`${className} shrink-0 rounded-md object-cover bg-slate-100 border border-slate-200`}
    />
  )
}

/** Campo del formulario "Nueva máquina": elegir o tomar una foto, con vista previa. */
export function CampoFoto({ archivo, onChange, className = '' }) {
  const [vista, setVista] = useState(null)

  useEffect(() => {
    if (!archivo) {
      setVista(null)
      return undefined
    }
    const url = URL.createObjectURL(archivo)
    setVista(url)
    return () => URL.revokeObjectURL(url)
  }, [archivo])

  return (
    <div className={`text-xs text-slate-500 flex flex-col gap-1 ${className}`}>
      <span>Foto de referencia (opcional)</span>
      <div className="flex items-center gap-3">
        {vista ? (
          <img src={vista} alt="Vista previa" className="w-16 h-16 rounded-md object-cover border border-slate-200" />
        ) : (
          <div className="w-16 h-16 rounded-md bg-slate-100 text-slate-300 flex items-center justify-center">
            <IconoCamara />
          </div>
        )}
        <div className="flex flex-col gap-1">
          <label className="cursor-pointer self-start px-3 py-1.5 rounded-md border border-slate-300 text-slate-700 text-xs font-medium hover:bg-slate-50">
            {archivo ? 'Cambiar foto' : 'Elegir o tomar foto'}
            <input
              type="file"
              accept={TIPOS}
              capture="environment"
              className="sr-only"
              onChange={(e) => {
                onChange(e.target.files?.[0] || null)
                e.target.value = ''
              }}
            />
          </label>
          {archivo && (
            <button type="button" onClick={() => onChange(null)} className="self-start text-xs text-slate-500 underline hover:text-red-600">
              Quitar
            </button>
          )}
          <span className="text-slate-400">JPG, PNG o WebP. Se achica sola si es muy grande.</span>
        </div>
      </div>
    </div>
  )
}

/** Foto grande del detalle de una máquina, con botón para subir o reemplazar. */
export function FotoEditable({ equipoId, nombre }) {
  const [version, setVersion] = useState(Date.now())
  const [hayFoto, setHayFoto] = useState(true) // se confirma al cargar la imagen
  const [subiendo, setSubiendo] = useState(false)
  const [error, setError] = useState(null)

  async function subir(archivo) {
    setSubiendo(true)
    setError(null)
    try {
      await visionApi.subirFoto(equipoId, await reducirImagen(archivo))
      setHayFoto(true)
      setVersion(Date.now())
    } catch (err) {
      setError(err.message)
    } finally {
      setSubiendo(false)
    }
  }

  return (
    <div className="space-y-2">
      <PinDialogo />
      {hayFoto ? (
        <img
          key={version}
          src={visionApi.urlFoto(equipoId, version)}
          alt={`Foto de ${nombre}`}
          onError={() => setHayFoto(false)}
          className="w-full aspect-[4/3] rounded-md object-cover bg-slate-100 border border-slate-200"
        />
      ) : (
        <div className="w-full aspect-[4/3] rounded-md bg-slate-100 text-slate-400 flex flex-col items-center justify-center">
          <IconoCamara className="w-10 h-10" />
          <span className="text-xs mt-1">Sin foto de referencia</span>
        </div>
      )}
      <label
        className={`block text-center cursor-pointer px-3 py-1.5 rounded-md border border-slate-300 text-xs font-medium text-slate-700 hover:bg-slate-50 ${
          subiendo ? 'opacity-50 pointer-events-none' : ''
        }`}
      >
        {subiendo ? 'Subiendo…' : hayFoto ? 'Cambiar foto' : 'Subir foto'}
        <input
          type="file"
          accept={TIPOS}
          capture="environment"
          className="sr-only"
          onChange={(e) => {
            const archivo = e.target.files?.[0]
            e.target.value = ''
            if (archivo) subir(archivo)
          }}
        />
      </label>
      {error && <p className="text-xs text-red-600">{error}</p>}
    </div>
  )
}
