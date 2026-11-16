import { useEffect, useMemo, useRef, useState } from 'react'
import { api } from '../api/client.js'

const MESES = [
  'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
  'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre',
]
const ESTADOS = ['Operativo', 'Operativo con incidencias abiertas', 'En mantenimiento', 'Fuera de servicio', 'Retirado']
const ANIO_APERTURA = 2024 // el CAF abrió el 13 de agosto de 2024
const LOTE = 20 // filas que se cargan cada vez que se llega al final de la tabla (scroll infinito)
const CAMPOS = ['fecha', 'codigo', 'maquina', 'incidencias', 'mantenimientos', 'observaciones', 'estado']

const CAMPO =
  'w-full border border-slate-300 rounded-md px-2 py-1.5 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-brand-600 focus:border-brand-600'
const BOTON_PRIMARIO =
  'inline-flex items-center justify-center gap-2 rounded-lg bg-brand-600 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-700 disabled:opacity-60 disabled:cursor-not-allowed focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-brand-600'
const BOTON_SECUNDARIO =
  'inline-flex items-center justify-center gap-2 rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-600'

function colorEstado(estado) {
  const e = (estado || '').toLowerCase()
  if (e.includes('fuera de servicio')) return 'bg-red-50 text-red-800'
  if (e.includes('mantenimiento') || e.includes('incidencias')) return 'bg-amber-50 text-amber-800'
  if (e.includes('operativo')) return 'bg-emerald-50 text-emerald-800'
  return 'bg-slate-50 text-slate-700'
}

function nombreDeArchivo(informe) {
  const base = `informe_${informe.etiqueta || 'maquinas'}`
  return base.normalize('NFD').replace(/[̀-ͯ]/g, '').replace(/[^A-Za-z0-9_-]+/g, '_')
}

function hoyLocal() {
  const d = new Date()
  return { anio: d.getFullYear(), mes: d.getMonth() + 1 }
}

// Periodo que se propone al abrir: el ultimo mes completo.
function mesAnterior() {
  const { anio, mes } = hoyLocal()
  return mes === 1 ? { anio: anio - 1, mes: 12 } : { anio, mes: mes - 1 }
}

export default function Informes() {
  const inicial = mesAnterior()
  const [tipo, setTipo] = useState('mensual')
  const [anio, setAnio] = useState(Math.max(inicial.anio, ANIO_APERTURA))
  const [mes, setMes] = useState(inicial.mes)
  const [trimestre, setTrimestre] = useState(Math.ceil(inicial.mes / 3))

  const [informe, setInforme] = useState(null) // { gimnasio, responsable, etiqueta, desde, hasta, generado }
  const [filas, setFilas] = useState([])
  const [modificado, setModificado] = useState(false)
  const [busqueda, setBusqueda] = useState('')
  const [cargando, setCargando] = useState(false)
  const [descargando, setDescargando] = useState(false)
  const [error, setError] = useState(null)
  const [aviso, setAviso] = useState(null)
  const siguienteClave = useRef(1)
  const [cuantas, setCuantas] = useState(LOTE) // filas mostradas por ahora
  const contenedor = useRef(null)

  const anios = useMemo(() => {
    const lista = []
    for (let a = hoyLocal().anio; a >= ANIO_APERTURA; a -= 1) lista.push(a)
    return lista
  }, [])

  async function generar() {
    setCargando(true)
    setError(null)
    setAviso(null)
    try {
      const params = { tipo, anio }
      if (tipo === 'mensual') params.mes = mes
      if (tipo === 'trimestral') params.trimestre = trimestre
      const datos = await api.borradorInforme(params)
      const { filas: nuevas, ...encabezado } = datos
      setInforme(encabezado)
      setFilas(nuevas.map((f) => ({ ...f, _k: siguienteClave.current++ })))
      setModificado(false)
      setCuantas(LOTE)
      if (!nuevas.length) setAviso('No hay máquinas con datos en ese periodo (todavía no estaban instaladas o el periodo aún no empieza).')
    } catch (err) {
      setError(err.message)
    } finally {
      setCargando(false)
    }
  }

  // Al abrir la pagina se genera el ultimo mes completo, para no mostrar una tabla vacia.
  useEffect(() => {
    generar()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  function cambiarEncabezado(campo, valor) {
    setInforme((actual) => ({ ...actual, [campo]: valor }))
    setModificado(true)
  }

  function cambiarCelda(clave, campo, valor) {
    setFilas((actuales) => actuales.map((f) => (f._k === clave ? { ...f, [campo]: valor } : f)))
    setModificado(true)
  }

  function quitarFila(clave) {
    setFilas((actuales) => actuales.filter((f) => f._k !== clave))
    setModificado(true)
  }

  function agregarFila() {
    const ultima = filas[filas.length - 1]
    setFilas((actuales) => [
      ...actuales,
      {
        _k: siguienteClave.current++,
        fecha: ultima?.fecha || informe?.etiqueta || '',
        codigo: '',
        maquina: '',
        incidencias: 'Sin incidencias',
        mantenimientos: 'Sin mantenimientos',
        observaciones: '',
        estado: 'Operativo',
      },
    ])
    setModificado(true)
  }

  async function descargar() {
    if (!informe) return
    setDescargando(true)
    setError(null)
    try {
      const cuerpo = {
        gimnasio: informe.gimnasio.trim(),
        responsable: (informe.responsable || '').trim(),
        etiqueta: informe.etiqueta,
        desde: informe.desde,
        hasta: informe.hasta,
        generado: informe.generado,
        filas: filas.map((f) => Object.fromEntries(CAMPOS.map((c) => [c, f[c] ?? '']))),
        nombre_archivo: nombreDeArchivo(informe),
      }
      if (!cuerpo.gimnasio) throw new Error('Escribe el nombre del gimnasio antes de descargar.')
      const blob = await api.descargarInformeExcel(cuerpo)
      const url = URL.createObjectURL(blob)
      const enlace = document.createElement('a')
      enlace.href = url
      enlace.download = `${cuerpo.nombre_archivo}.xlsx`
      document.body.appendChild(enlace)
      enlace.click()
      enlace.remove()
      setTimeout(() => URL.revokeObjectURL(url), 10_000)
      setModificado(false)
      setAviso('Excel descargado.')
    } catch (err) {
      setError(err.message)
    } finally {
      setDescargando(false)
    }
  }

  const visibles = useMemo(() => {
    const q = busqueda.trim().toLowerCase()
    if (!q) return filas
    return filas.filter((f) => `${f.codigo} ${f.maquina} ${f.estado}`.toLowerCase().includes(q))
  }, [filas, busqueda])

  const mostradas = visibles.slice(0, cuantas)
  const hayMas = cuantas < visibles.length

  function cargarMas() {
    setCuantas((actual) => actual + LOTE)
  }

  // Scroll infinito: al acercarse al final de la tabla se suman 20 filas mas.
  function alDesplazar(e) {
    const el = e.currentTarget
    if (hayMas && el.scrollTop + el.clientHeight >= el.scrollHeight - 240) cargarMas()
  }

  // Si las filas mostradas no alcanzan a llenar el recuadro (pantalla alta), se siguen cargando.
  useEffect(() => {
    const el = contenedor.current
    if (el && hayMas && el.scrollHeight <= el.clientHeight + 8) cargarMas()
  }, [cuantas, hayMas, visibles.length])

  const conProblemas = filas.filter((f) => !/sin incidencias/i.test(f.incidencias || '')).length

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Informes de funcionamiento</h1>
        <p className="mt-1 text-sm text-slate-600 max-w-3xl">
          Elige el periodo, revisa el informe, corrige lo que haga falta directamente en la tabla y descárgalo en Excel.
          Cada fila es una máquina en un mes.
        </p>
      </div>

      <section className="bg-white rounded-lg border border-slate-200 shadow-sm p-4" aria-label="Periodo del informe">
        <div className="flex flex-wrap items-end gap-3">
          <div>
            <label htmlFor="inf-tipo" className="block text-xs font-semibold text-slate-500 mb-1">Informe</label>
            <select id="inf-tipo" value={tipo} onChange={(e) => setTipo(e.target.value)} className={CAMPO}>
              <option value="mensual">Mensual</option>
              <option value="trimestral">Trimestral</option>
              <option value="anual">Anual</option>
            </select>
          </div>
          {tipo === 'mensual' && (
            <div>
              <label htmlFor="inf-mes" className="block text-xs font-semibold text-slate-500 mb-1">Mes</label>
              <select id="inf-mes" value={mes} onChange={(e) => setMes(Number(e.target.value))} className={CAMPO}>
                {MESES.map((nombre, i) => (
                  <option key={nombre} value={i + 1}>{nombre}</option>
                ))}
              </select>
            </div>
          )}
          {tipo === 'trimestral' && (
            <div>
              <label htmlFor="inf-trim" className="block text-xs font-semibold text-slate-500 mb-1">Trimestre</label>
              <select id="inf-trim" value={trimestre} onChange={(e) => setTrimestre(Number(e.target.value))} className={CAMPO}>
                <option value={1}>1.º (ene – mar)</option>
                <option value={2}>2.º (abr – jun)</option>
                <option value={3}>3.º (jul – sep)</option>
                <option value={4}>4.º (oct – dic)</option>
              </select>
            </div>
          )}
          <div>
            <label htmlFor="inf-anio" className="block text-xs font-semibold text-slate-500 mb-1">Año</label>
            <select id="inf-anio" value={anio} onChange={(e) => setAnio(Number(e.target.value))} className={CAMPO}>
              {anios.map((a) => (
                <option key={a} value={a}>{a}</option>
              ))}
            </select>
          </div>
          <button type="button" onClick={generar} disabled={cargando} className={BOTON_PRIMARIO}>
            {cargando ? 'Generando…' : informe ? 'Generar de nuevo' : 'Generar informe'}
          </button>
        </div>
        {modificado && (
          <p className="mt-3 text-xs text-amber-700">
            Tienes cambios sin descargar. Si generas de nuevo, el informe se reemplaza con los datos del sistema.
          </p>
        )}
      </section>

      {error && (
        <p role="alert" className="text-sm text-red-700 bg-red-50 border border-red-200 rounded-md px-3 py-2">{error}</p>
      )}
      {aviso && !error && (
        <p role="status" className="text-sm text-slate-700 bg-slate-100 border border-slate-200 rounded-md px-3 py-2">{aviso}</p>
      )}

      {informe && (
        <section className="bg-white rounded-lg border border-slate-200 shadow-sm" aria-label="Informe editable">
          <div className="p-4 border-b border-slate-200 space-y-4">
            <div className="flex flex-wrap items-baseline justify-between gap-2">
              <h2 className="text-lg font-bold text-slate-900">Informe {informe.etiqueta}</h2>
              <p className="text-xs text-slate-500">
                {informe.desde} al {informe.hasta} · emitido el {informe.generado}
              </p>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3 max-w-3xl">
              <div>
                <label htmlFor="inf-gym" className="block text-xs font-semibold text-slate-500 mb-1">Gimnasio</label>
                <input id="inf-gym" type="text" value={informe.gimnasio} maxLength={200} onChange={(e) => cambiarEncabezado('gimnasio', e.target.value)} className={CAMPO} />
              </div>
              <div>
                <label htmlFor="inf-resp" className="block text-xs font-semibold text-slate-500 mb-1">Responsable a cargo</label>
                <input id="inf-resp" type="text" value={informe.responsable || ''} maxLength={150} placeholder="Nombre de la persona a cargo" onChange={(e) => cambiarEncabezado('responsable', e.target.value)} className={CAMPO} />
              </div>
            </div>
            <div className="flex flex-wrap items-center gap-3">
              <button type="button" onClick={descargar} disabled={descargando || !filas.length} className={BOTON_PRIMARIO}>
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="w-4 h-4" aria-hidden="true">
                  <path d="M12 3v12m0 0 4-4m-4 4-4-4M4 20h16" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
                {descargando ? 'Preparando…' : 'Descargar Excel'}
              </button>
              <button type="button" onClick={agregarFila} className={BOTON_SECUNDARIO}>Agregar fila</button>
              <input
                type="search"
                aria-label="Buscar máquina en el informe"
                value={busqueda}
                onChange={(e) => {
                  setBusqueda(e.target.value)
                  setCuantas(LOTE)
                  if (contenedor.current) contenedor.current.scrollTop = 0
                }}
                placeholder="Buscar máquina…"
                className={`${CAMPO} sm:max-w-xs`}
              />
              <p className="text-xs text-slate-500 ml-auto">
                {filas.length} fila{filas.length === 1 ? '' : 's'} · {conProblemas} con incidencias
              </p>
            </div>
          </div>

          <div
            ref={contenedor}
            onScroll={alDesplazar}
            className="overflow-auto max-h-[65vh] border-t border-slate-100"
            tabIndex={0}
            aria-label="Tabla del informe: desplázate hacia abajo para ver más filas"
          >
            <table className="w-full min-w-[1100px] text-sm">
              <thead className="sticky top-0 z-10 bg-slate-50 shadow-[0_1px_0_0_rgb(226,232,240)] text-left text-xs uppercase tracking-wide text-slate-500">
                <tr>
                  <th className="px-3 py-2 font-semibold w-36">Fecha</th>
                  <th className="px-3 py-2 font-semibold w-24">Código</th>
                  <th className="px-3 py-2 font-semibold w-52">Máquina</th>
                  <th className="px-3 py-2 font-semibold">Incidencias</th>
                  <th className="px-3 py-2 font-semibold w-60">Mantenimientos</th>
                  <th className="px-3 py-2 font-semibold">Observaciones</th>
                  <th className="px-3 py-2 font-semibold w-48">Estado de la máquina</th>
                  <th className="px-3 py-2 w-10"><span className="sr-only">Quitar</span></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {mostradas.map((f) => (
                  <tr key={f._k} className="align-top">
                    <td className="px-2 py-1.5"><input aria-label="Fecha" value={f.fecha} onChange={(e) => cambiarCelda(f._k, 'fecha', e.target.value)} className={CAMPO} /></td>
                    <td className="px-2 py-1.5"><input aria-label="Código" value={f.codigo} onChange={(e) => cambiarCelda(f._k, 'codigo', e.target.value)} className={CAMPO} /></td>
                    <td className="px-2 py-1.5"><input aria-label="Máquina" value={f.maquina} onChange={(e) => cambiarCelda(f._k, 'maquina', e.target.value)} className={CAMPO} /></td>
                    <td className="px-2 py-1.5"><textarea aria-label="Incidencias" rows={2} value={f.incidencias} onChange={(e) => cambiarCelda(f._k, 'incidencias', e.target.value)} className={CAMPO} /></td>
                    <td className="px-2 py-1.5"><textarea aria-label="Mantenimientos" rows={2} value={f.mantenimientos} onChange={(e) => cambiarCelda(f._k, 'mantenimientos', e.target.value)} className={CAMPO} /></td>
                    <td className="px-2 py-1.5"><textarea aria-label="Observaciones" rows={2} value={f.observaciones} onChange={(e) => cambiarCelda(f._k, 'observaciones', e.target.value)} className={CAMPO} /></td>
                    <td className="px-2 py-1.5">
                      <input
                        aria-label="Estado de la máquina"
                        list="inf-estados"
                        value={f.estado}
                        onChange={(e) => cambiarCelda(f._k, 'estado', e.target.value)}
                        className={`${CAMPO} font-semibold ${colorEstado(f.estado)}`}
                      />
                    </td>
                    <td className="px-1 py-1.5 text-center">
                      <button
                        type="button"
                        onClick={() => quitarFila(f._k)}
                        aria-label={`Quitar la fila de ${f.maquina || 'esta máquina'}`}
                        title="Quitar fila"
                        className="h-8 w-8 rounded-md text-slate-400 hover:bg-red-50 hover:text-red-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-600"
                      >
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="w-4 h-4 mx-auto" aria-hidden="true">
                          <path d="M6 6l12 12M18 6 6 18" strokeLinecap="round" />
                        </svg>
                      </button>
                    </td>
                  </tr>
                ))}
                {!visibles.length && (
                  <tr>
                    <td colSpan={8} className="px-3 py-8 text-center text-slate-500">
                      {filas.length ? 'Ninguna fila coincide con la búsqueda.' : 'No hay filas en este informe.'}
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
            <div className="sticky left-0 px-4 py-3 text-center text-xs text-slate-500" aria-live="polite">
              {hayMas ? (
                <button type="button" onClick={cargarMas} className="font-semibold text-brand-700 underline">
                  Mostrando {mostradas.length} de {visibles.length} · cargar más
                </button>
              ) : (
                visibles.length > 0 && `Fin del informe · ${visibles.length} fila${visibles.length === 1 ? '' : 's'}`
              )}
            </div>
            <datalist id="inf-estados">
              {ESTADOS.map((e) => (
                <option key={e} value={e} />
              ))}
            </datalist>
          </div>
        </section>
      )}
    </div>
  )
}
