import { useEffect, useState } from 'react'
import { api } from '../api/client.js'

/**
 * Foto del dano adjuntada por quien reporto por QR. Muestra una miniatura con el texto
 * "Ver foto"; al hacer clic se abre en grande (cierra con la X, Escape o clic afuera).
 * Se intenta cargar tambien en los reportes por QR que no marcan `tiene_foto`, y si la imagen
 * no existe (404) la celda queda en "—".
 */
export default function FotoIncidencia({ incidencia }) {
  const [fallo, setFallo] = useState(false)
  const [abierta, setAbierta] = useState(false)
  const url = api.urlFotoIncidencia(incidencia.id)
  const puede = incidencia.tiene_foto || incidencia.origen === 'qr'

  useEffect(() => {
    if (!abierta) return undefined
    const alTeclear = (e) => e.key === 'Escape' && setAbierta(false)
    window.addEventListener('keydown', alTeclear)
    return () => window.removeEventListener('keydown', alTeclear)
  }, [abierta])

  if (!puede || fallo) return <span className="text-slate-300">—</span>

  return (
    <>
      <button
        type="button"
        onClick={() => setAbierta(true)}
        title="Ver foto del daño"
        className="group flex flex-col items-center gap-0.5"
      >
        <img
          src={url}
          alt={`Foto del reporte #${incidencia.id}`}
          loading="lazy"
          onError={() => setFallo(true)}
          className="w-12 h-12 object-cover rounded border border-slate-200 group-hover:border-brand-600"
        />
        <span className="text-[10px] font-medium text-brand-700 underline">Ver foto</span>
      </button>

      {abierta && (
        <div
          role="dialog"
          aria-modal="true"
          aria-label={`Foto del reporte #${incidencia.id}`}
          className="fixed inset-0 z-50 bg-black/80 flex items-center justify-center p-4"
          onClick={() => setAbierta(false)}
        >
          <div className="relative max-w-3xl w-full" onClick={(e) => e.stopPropagation()}>
            <img src={url} alt={`Foto del reporte #${incidencia.id}`} className="w-full max-h-[80vh] object-contain rounded-lg bg-black" />
            <div className="mt-3 flex items-center justify-between text-sm text-white">
              <span>
                Reporte #{incidencia.id}
                {incidencia.reportado_por ? ` · ${incidencia.reportado_por}` : ''}
              </span>
              <span className="flex items-center gap-4">
                <a href={url} target="_blank" rel="noreferrer" className="underline">
                  Abrir en otra pestaña
                </a>
                <button
                  type="button"
                  onClick={() => setAbierta(false)}
                  className="bg-white text-slate-900 rounded-md px-3 py-1 font-medium"
                >
                  Cerrar
                </button>
              </span>
            </div>
          </div>
        </div>
      )}
    </>
  )
}
