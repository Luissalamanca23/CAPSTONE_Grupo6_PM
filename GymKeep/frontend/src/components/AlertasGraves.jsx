import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api/client.js'
import usePolling from '../pages/vision/usePolling.js'
import { PLAZO_VENCIDA_HORAS, calcularAvisos, textoAntiguedad } from '../utils/avisos.js'

// Avisos emergentes para el personal de mantencion (RF-15). Aparecen arriba a la derecha en
// cualquier pagina del panel, sin que nadie tenga que abrir la lista de incidencias:
//   - "urgente": se reporto una maquina que NO se puede ocupar (prioridad urgente).
//   - "nueva":   se reporto cualquier otra incidencia.
//   - "vencidas": hay incidencias abiertas (pendiente o en proceso) hace mas de 48 horas.
// La consulta se repite cada 15 s (un aviso llega en menos de 1 minuto). Cada aviso dura 30 s o
// hasta que se cierre con la X. La logica de que avisar y cuando esta en utils/avisos.js.
const DURACION_MS = 30_000
const CADA_MS = 15_000
const MAXIMO_VISIBLES = 4
const MAXIMO_INDIVIDUALES = 3 // si llegan mas nuevas de golpe, el resto se agrupa en un solo aviso
const CLAVE_VISTAS = 'gymkeep.alertasVistas'
const CLAVE_VENCIDAS = 'gymkeep.alertasVencidas'

const ESTILOS = {
  urgente: {
    titulo: 'Máquina sin poder ocuparse',
    borde: 'border-red-300',
    icono: 'bg-red-100 text-red-700',
    texto: 'text-red-700',
    barraFondo: 'bg-red-100',
    barra: 'bg-red-600',
  },
  nueva: {
    titulo: 'Nueva incidencia',
    borde: 'border-amber-300',
    icono: 'bg-amber-100 text-amber-700',
    texto: 'text-amber-700',
    barraFondo: 'bg-amber-100',
    barra: 'bg-amber-500',
  },
  resumen: {
    titulo: 'Más incidencias nuevas',
    borde: 'border-amber-300',
    icono: 'bg-amber-100 text-amber-700',
    texto: 'text-amber-700',
    barraFondo: 'bg-amber-100',
    barra: 'bg-amber-500',
  },
  vencidas: {
    titulo: 'Incidencias vencidas',
    borde: 'border-orange-300',
    icono: 'bg-orange-100 text-orange-700',
    texto: 'text-orange-700',
    barraFondo: 'bg-orange-100',
    barra: 'bg-orange-500',
  },
}

function leerVistas() {
  try {
    return new Set(JSON.parse(sessionStorage.getItem(CLAVE_VISTAS) || '[]'))
  } catch {
    return new Set()
  }
}

function leerVencidas() {
  try {
    const guardado = JSON.parse(sessionStorage.getItem(CLAVE_VENCIDAS) || '{}')
    return guardado && typeof guardado === 'object' ? guardado : {}
  } catch {
    return {}
  }
}

function guardar(vistas, vencidas) {
  try {
    sessionStorage.setItem(CLAVE_VISTAS, JSON.stringify([...vistas].slice(-300)))
    sessionStorage.setItem(CLAVE_VENCIDAS, JSON.stringify(vencidas))
  } catch {
    // sin almacenamiento: al recargar la pagina podria repetirse un aviso reciente, nada mas
  }
}

function horaDe(fecha) {
  return new Date(fecha).toLocaleTimeString('es-CL', { hour: '2-digit', minute: '2-digit' })
}

function nombreEquipo(inc) {
  return inc.equipo?.nombre || `Máquina #${inc.equipo_id}`
}

/** Texto y enlace de cada tipo de aviso. */
function contenido(aviso) {
  if (aviso.tipo === 'vencidas') {
    const total = aviso.lista.length
    const visibles = aviso.lista.slice(0, 3)
    return {
      enlace: '/incidencias',
      textoEnlace: 'Ver incidencias',
      cuerpo: (
        <>
          <p className="mt-0.5 text-sm font-semibold text-slate-900">
            {total === 1 ? '1 incidencia lleva' : `${total} incidencias llevan`} más de {PLAZO_VENCIDA_HORAS} h abiertas
          </p>
          <ul className="mt-1 space-y-0.5 text-xs text-slate-600">
            {visibles.map(({ incidencia, horas }) => (
              <li key={incidencia.id} className="break-words">
                {nombreEquipo(incidencia)} · {textoAntiguedad(horas)}
              </li>
            ))}
            {total > visibles.length && <li>y {total - visibles.length} más</li>}
          </ul>
        </>
      ),
    }
  }
  if (aviso.tipo === 'resumen') {
    return {
      enlace: '/incidencias',
      textoEnlace: 'Ver incidencias',
      cuerpo: (
        <p className="mt-0.5 text-sm font-semibold text-slate-900">
          {aviso.cantidad} incidencias nuevas más en la última consulta
        </p>
      ),
    }
  }
  const inc = aviso.incidencia
  return {
    enlace: inc.equipo_id ? `/equipos/${inc.equipo_id}` : '/incidencias',
    textoEnlace: 'Ver máquina',
    cuerpo: (
      <>
        <p className="mt-0.5 text-sm font-semibold text-slate-900 break-words">{nombreEquipo(inc)}</p>
        <p className="mt-0.5 text-xs text-slate-600 break-words">
          {inc.tipo_falla?.nombre || 'Falla reportada'} · reportó {inc.reportado_por || 'un usuario'} a las {horaDe(inc.fecha_reporte)}
        </p>
      </>
    ),
  }
}

function Alerta({ aviso, onCerrar }) {
  const [visible, setVisible] = useState(false)
  const estilo = ESTILOS[aviso.tipo]
  const { enlace, textoEnlace, cuerpo } = contenido(aviso)

  useEffect(() => {
    const entrada = requestAnimationFrame(() => setVisible(true))
    const salida = setTimeout(() => onCerrar(aviso.id), DURACION_MS)
    return () => {
      cancelAnimationFrame(entrada)
      clearTimeout(salida)
    }
  }, [aviso.id, onCerrar])

  return (
    <div
      role="alert"
      className={`pointer-events-auto w-full overflow-hidden rounded-lg border ${estilo.borde} bg-white shadow-xl transition-all duration-300 motion-reduce:transition-none ${
        visible ? 'translate-x-0 opacity-100' : 'translate-x-6 opacity-0'
      }`}
    >
      <div className="flex gap-3 p-4">
        <span className={`mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-full ${estilo.icono}`} aria-hidden="true">
          {aviso.tipo === 'vencidas' ? (
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="h-5 w-5">
              <circle cx="12" cy="12" r="9" />
              <path d="M12 7v5l3 2" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          ) : (
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="h-5 w-5">
              <path d="M12 9v4M12 17h.01" strokeLinecap="round" />
              <path d="M10.3 3.9 2.5 17.5a1.5 1.5 0 0 0 1.3 2.3h16.4a1.5 1.5 0 0 0 1.3-2.3L13.7 3.9a1.5 1.5 0 0 0-2.6 0Z" />
            </svg>
          )}
        </span>
        <div className="min-w-0 flex-1">
          <p className={`text-sm font-bold ${estilo.texto}`}>{estilo.titulo}</p>
          {cuerpo}
          <Link
            to={enlace}
            onClick={() => onCerrar(aviso.id)}
            className="mt-2 inline-block text-xs font-semibold text-brand-700 underline hover:text-brand-600 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-600 rounded"
          >
            {textoEnlace}
          </Link>
        </div>
        <button
          type="button"
          onClick={() => onCerrar(aviso.id)}
          aria-label="Cerrar aviso"
          title="Cerrar"
          className="-mr-1 -mt-1 h-8 w-8 shrink-0 rounded-md text-slate-500 hover:bg-slate-100 hover:text-slate-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-600 flex items-center justify-center"
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="h-4 w-4" aria-hidden="true">
            <path d="M6 6l12 12M18 6 6 18" strokeLinecap="round" />
          </svg>
        </button>
      </div>
      {/* Barra que se vacia en 30 s: muestra cuanto falta para que el aviso se cierre solo. */}
      <div className={`h-1 ${estilo.barraFondo}`} aria-hidden="true">
        <div
          className={`h-full ${estilo.barra}`}
          style={{ width: visible ? '0%' : '100%', transition: `width ${DURACION_MS}ms linear` }}
        />
      </div>
    </div>
  )
}

export default function AlertasGraves() {
  const [avisos, setAvisos] = useState([])
  const vistas = useRef(leerVistas())
  const vencidasAvisadas = useRef(leerVencidas())
  const primeraConsulta = useRef(true)

  function cerrar(id) {
    setAvisos((actuales) => actuales.filter((a) => a.id !== id))
  }
  // `cerrar` se usa dentro de efectos de cada aviso: una referencia estable evita reiniciar su temporizador.
  const cerrarRef = useRef(cerrar)
  cerrarRef.current = cerrar
  const cerrarEstable = useRef((id) => cerrarRef.current(id)).current

  usePolling(async (vigente) => {
    const [pendientes, enProceso] = await Promise.all([
      api.listarIncidencias({ estado: 'pendiente', limit: 200 }),
      api.listarIncidencias({ estado: 'en_proceso', limit: 200 }),
    ])
    if (!vigente()) return
    const ahora = Date.now()
    const r = calcularAvisos({
      pendientes,
      enProceso,
      ahora,
      vistas: vistas.current,
      vencidasAvisadas: vencidasAvisadas.current,
      primeraConsulta: primeraConsulta.current,
    })
    primeraConsulta.current = false
    vistas.current = r.vistas
    vencidasAvisadas.current = r.vencidasAvisadas
    guardar(vistas.current, vencidasAvisadas.current)

    const nuevos = []
    // Las urgentes primero; despues el resto de las nuevas.
    const urgentes = r.nuevas.filter((i) => i.prioridad === 'urgente')
    const otras = r.nuevas.filter((i) => i.prioridad !== 'urgente')
    const ordenadas = [...urgentes, ...otras]
    for (const inc of ordenadas.slice(0, MAXIMO_INDIVIDUALES)) {
      nuevos.push({ id: `inc-${inc.id}`, tipo: inc.prioridad === 'urgente' ? 'urgente' : 'nueva', incidencia: inc })
    }
    if (ordenadas.length > MAXIMO_INDIVIDUALES) {
      nuevos.push({ id: `resumen-${ahora}`, tipo: 'resumen', cantidad: ordenadas.length - MAXIMO_INDIVIDUALES })
    }
    if (r.vencidas.length) {
      nuevos.push({ id: `vencidas-${ahora}`, tipo: 'vencidas', lista: r.vencidas })
    }
    if (nuevos.length) {
      setAvisos((actuales) => [...nuevos, ...actuales].slice(0, MAXIMO_VISIBLES))
    }
  }, CADA_MS)

  if (!avisos.length) return null
  return (
    <div className="pointer-events-none fixed right-4 top-16 md:top-4 z-50 flex w-[min(24rem,calc(100vw-2rem))] flex-col gap-3">
      {avisos.map((aviso) => (
        <Alerta key={aviso.id} aviso={aviso} onCerrar={cerrarEstable} />
      ))}
    </div>
  )
}
