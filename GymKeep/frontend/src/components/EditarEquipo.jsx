import { useEffect, useState } from 'react'
import { api } from '../api/client.js'
import { CATEGORIAS_EQUIPO, ETIQUETA_CATEGORIA_EQUIPO, esCategoriaVigente } from './CategoriaEquipoBadge.jsx'

const CAMPO = 'border border-slate-300 rounded-md px-2 py-1.5 text-sm text-slate-900 w-full'

function aFormulario(equipo) {
  return {
    codigo_activo: equipo.codigo_activo ?? '',
    nombre: equipo.nombre ?? '',
    // Una categoria antigua (p. ej. "fuerza") no es elegible: se parte en blanco para que el
    // usuario escoja una del esquema nuevo.
    categoria: esCategoriaVigente(equipo.categoria) ? equipo.categoria : '',
    zona_id: equipo.zona_id ? String(equipo.zona_id) : '',
    marca: equipo.marca ?? '',
    modelo: equipo.modelo ?? '',
    numero_serie: equipo.numero_serie ?? '',
    fecha_adquisicion: equipo.fecha_adquisicion ?? '',
    fecha_instalacion: equipo.fecha_instalacion ?? '',
    vida_util_meses: equipo.vida_util_meses ? String(equipo.vida_util_meses) : '',
    observaciones: equipo.observaciones ?? '',
  }
}

// Convierte el valor del formulario al que entiende la API ('' -> null, numeros como numero).
function aApi(campo, valor) {
  if (campo === 'zona_id' || campo === 'vida_util_meses') return valor === '' ? null : Number(valor)
  if (valor === '') return null
  return typeof valor === 'string' ? valor.trim() : valor
}

function Campo({ etiqueta, children, className = '' }) {
  return (
    <label className={`text-xs text-slate-500 flex flex-col gap-1 ${className}`}>
      {etiqueta}
      {children}
    </label>
  )
}

/**
 * Boton "Editar" + dialogo para modificar los datos de una maquina (PATCH /equipamiento/{id}).
 * Solo envia los campos que cambiaron. `onGuardado` recibe el equipo ya actualizado.
 */
export default function EditarEquipo({
  equipo,
  onGuardado,
  etiqueta = 'Editar',
  className = 'text-xs font-medium text-brand-700 underline hover:text-brand-800',
}) {
  const [abierto, setAbierto] = useState(false)
  const [form, setForm] = useState(() => aFormulario(equipo))
  const [zonas, setZonas] = useState([])
  const [guardando, setGuardando] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    if (!abierto) return undefined
    setForm(aFormulario(equipo))
    setError(null)
    let vigente = true
    api
      .listarZonas(equipo.sucursal_id)
      .then((z) => vigente && setZonas(z))
      .catch(() => {}) // sin zonas el selector queda solo con "Sin zona"
    const alTeclear = (e) => e.key === 'Escape' && !guardando && setAbierto(false)
    window.addEventListener('keydown', alTeclear)
    return () => {
      vigente = false
      window.removeEventListener('keydown', alTeclear)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [abierto])

  const cambiar = (campo) => (e) => setForm((f) => ({ ...f, [campo]: e.target.value }))

  async function guardar(evento) {
    evento.preventDefault()
    const original = aFormulario(equipo)
    const cambios = {}
    for (const campo of Object.keys(form)) {
      if (form[campo] !== original[campo]) cambios[campo] = aApi(campo, form[campo])
    }
    if (Object.keys(cambios).length === 0) {
      setAbierto(false)
      return
    }
    setGuardando(true)
    setError(null)
    try {
      const actualizado = await api.actualizarEquipo(equipo.id, cambios)
      setAbierto(false)
      onGuardado?.(actualizado)
    } catch (err) {
      setError(err.message)
    } finally {
      setGuardando(false)
    }
  }

  const categoriaAntigua = equipo.categoria && !esCategoriaVigente(equipo.categoria)

  return (
    <>
      <button type="button" onClick={() => setAbierto(true)} className={className}>
        {etiqueta}
      </button>

      {abierto && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 p-4"
          role="dialog"
          aria-modal="true"
          aria-labelledby="titulo-editar-equipo"
          onClick={() => !guardando && setAbierto(false)}
        >
          <form
            onSubmit={guardar}
            onClick={(e) => e.stopPropagation()}
            className="w-full max-w-2xl max-h-[90vh] overflow-y-auto rounded-lg bg-white shadow-xl border border-slate-200 p-5 space-y-4"
          >
            <div>
              <h2 id="titulo-editar-equipo" className="text-lg font-semibold text-slate-900">
                Editar máquina
              </h2>
              <p className="text-xs text-slate-400">El código QR no cambia al editar.</p>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <Campo etiqueta="Nombre">
                <input type="text" required value={form.nombre} onChange={cambiar('nombre')} className={CAMPO} />
              </Campo>
              <Campo etiqueta="Código de activo">
                <input type="text" required value={form.codigo_activo} onChange={cambiar('codigo_activo')} className={`${CAMPO} font-mono`} />
              </Campo>

              <Campo etiqueta="Categoría" className="sm:col-span-2">
                <select value={form.categoria} onChange={cambiar('categoria')} className={CAMPO}>
                  <option value="">{categoriaAntigua ? 'Elegir categoría…' : 'Sin categoría'}</option>
                  {CATEGORIAS_EQUIPO.map((c) => (
                    <option key={c.valor} value={c.valor}>
                      {c.etiqueta}
                    </option>
                  ))}
                </select>
                {categoriaAntigua && (
                  <span className="text-amber-700">
                    Categoría anterior: {ETIQUETA_CATEGORIA_EQUIPO[equipo.categoria] || equipo.categoria}. Elige una del esquema nuevo.
                  </span>
                )}
                {CATEGORIAS_EQUIPO.find((c) => c.valor === form.categoria)?.descripcion && (
                  <span className="text-slate-400">{CATEGORIAS_EQUIPO.find((c) => c.valor === form.categoria).descripcion}</span>
                )}
              </Campo>

              <Campo etiqueta="Zona">
                <select value={form.zona_id} onChange={cambiar('zona_id')} className={CAMPO}>
                  <option value="">Sin zona</option>
                  {zonas.map((z) => (
                    <option key={z.id} value={z.id}>
                      {z.nombre}
                    </option>
                  ))}
                </select>
              </Campo>
              <Campo etiqueta="Número de serie">
                <input type="text" value={form.numero_serie} onChange={cambiar('numero_serie')} className={CAMPO} />
              </Campo>

              <Campo etiqueta="Marca">
                <input type="text" value={form.marca} onChange={cambiar('marca')} className={CAMPO} />
              </Campo>
              <Campo etiqueta="Modelo">
                <input type="text" value={form.modelo} onChange={cambiar('modelo')} className={CAMPO} />
              </Campo>

              <Campo etiqueta="Fecha de adquisición">
                <input type="date" value={form.fecha_adquisicion} onChange={cambiar('fecha_adquisicion')} className={CAMPO} />
              </Campo>
              <Campo etiqueta="Fecha de instalación">
                <input type="date" value={form.fecha_instalacion} onChange={cambiar('fecha_instalacion')} className={CAMPO} />
              </Campo>

              <Campo etiqueta="Vida útil (meses)">
                <input type="number" min="1" value={form.vida_util_meses} onChange={cambiar('vida_util_meses')} className={CAMPO} />
              </Campo>
              <Campo etiqueta="Observaciones" className="sm:col-span-2">
                <textarea rows={2} value={form.observaciones} onChange={cambiar('observaciones')} className={CAMPO} />
              </Campo>
            </div>

            {error && <p className="text-sm text-red-600">{error}</p>}

            <div className="flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setAbierto(false)}
                disabled={guardando}
                className="px-3 py-1.5 rounded-md border border-slate-300 text-sm text-slate-700 hover:bg-slate-50 disabled:opacity-50"
              >
                Cancelar
              </button>
              <button
                type="submit"
                disabled={guardando}
                className="px-4 py-1.5 rounded-md bg-brand-600 text-white text-sm font-medium hover:bg-brand-700 disabled:opacity-50"
              >
                {guardando ? 'Guardando…' : 'Guardar cambios'}
              </button>
            </div>
          </form>
        </div>
      )}
    </>
  )
}
