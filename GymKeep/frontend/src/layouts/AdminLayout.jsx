import { useEffect, useState } from 'react'
import { NavLink, Outlet } from 'react-router-dom'
import CambiarClaveDialogo from '../auth/CambiarClaveDialogo.jsx'
import { useAuth } from '../auth/AuthContext.jsx'
import AlertasGraves from '../components/AlertasGraves.jsx'
import FaqAyuda from '../components/FaqAyuda.jsx'

const ICONOS = {
  panel: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="w-5 h-5 shrink-0">
      <rect x="3" y="3" width="8" height="8" rx="1.5" />
      <rect x="13" y="3" width="8" height="5" rx="1.5" />
      <rect x="13" y="10" width="8" height="11" rx="1.5" />
      <rect x="3" y="13" width="8" height="8" rx="1.5" />
    </svg>
  ),
  equipos: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="w-5 h-5 shrink-0">
      <path d="M14.7 6.3a1 1 0 0 1 1.4 0l1.6 1.6a1 1 0 0 1 0 1.4l-8 8a1 1 0 0 1-1.4 0l-1.6-1.6a1 1 0 0 1 0-1.4l8-8Z" />
      <path d="m17.5 3.5 3 3" />
      <path d="m3.5 17.5 3 3" />
    </svg>
  ),
  incidencias: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="w-5 h-5 shrink-0">
      <path d="M12 9v4" />
      <path d="M12 17h.01" />
      <path d="M10.3 3.9 2.5 17.5a1.5 1.5 0 0 0 1.3 2.3h16.4a1.5 1.5 0 0 0 1.3-2.3L13.7 3.9a1.5 1.5 0 0 0-2.6 0Z" />
    </svg>
  ),
  costos: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="w-5 h-5 shrink-0">
      <circle cx="12" cy="12" r="9" />
      <path d="M12 7v10" />
      <path d="M14.8 9.5c0-1.1-1.25-2-2.8-2s-2.8.9-2.8 2c0 1.1 1.25 1.5 2.8 2s2.8.9 2.8 2c0 1.1-1.25 2-2.8 2s-2.8-.9-2.8-2" />
    </svg>
  ),
  informes: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="w-5 h-5 shrink-0">
      <path d="M6 3h8l4 4v14H6z" strokeLinejoin="round" />
      <path d="M14 3v4h4" strokeLinejoin="round" />
      <path d="M9 12h6M9 15h6M9 18h4" strokeLinecap="round" />
    </svg>
  ),
  uso: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="w-5 h-5 shrink-0">
      <circle cx="12" cy="13" r="8" />
      <path d="M12 9v4l2.5 2.5" />
      <path d="M9.5 2.5h5" />
    </svg>
  ),
  camaras: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="w-5 h-5 shrink-0">
      <rect x="2.5" y="6.5" width="13" height="11" rx="2" />
      <path d="m15.5 10.5 6-3.5v10l-6-3.5" />
    </svg>
  ),
  usuarios: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="w-5 h-5 shrink-0">
      <circle cx="9" cy="8" r="3.5" />
      <path d="M2.5 20c0-3.6 2.9-6 6.5-6s6.5 2.4 6.5 6" />
      <path d="M16 4.6a3.5 3.5 0 0 1 0 6.8" />
      <path d="M18 14.3c2 .7 3.5 2.5 3.5 5.7" />
    </svg>
  ),
  llave: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="w-5 h-5 shrink-0">
      <circle cx="8" cy="15" r="4.5" />
      <path d="m11.2 11.8 8.3-8.3M16.5 6.5l3 3M14 9l2.5 2.5" />
    </svg>
  ),
  salir: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="w-5 h-5 shrink-0">
      <path d="M9 21H5.5A1.5 1.5 0 0 1 4 19.5v-15A1.5 1.5 0 0 1 5.5 3H9" />
      <path d="M16 17l5-5-5-5M21 12H9" />
    </svg>
  ),
  sucursales: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="w-5 h-5 shrink-0">
      <path d="M3 21h18" />
      <path d="M5 21V7l7-4 7 4v14" />
      <path d="M9 21v-6h6v6" />
    </svg>
  ),
}

const ENLACES = [
  { to: '/', label: 'Panel', end: true, icono: ICONOS.panel },
  { to: '/equipos', label: 'Equipamiento', icono: ICONOS.equipos },
  { to: '/incidencias', label: 'Incidencias', icono: ICONOS.incidencias },
  { to: '/costos', label: 'Costos', icono: ICONOS.costos },
  { to: '/informes', label: 'Informes', icono: ICONOS.informes },
  { to: '/uso', label: 'Uso de máquinas', icono: ICONOS.uso },
  { to: '/camaras', label: 'Cámaras', icono: ICONOS.camaras },
  { to: '/sucursales', label: 'Sucursales', icono: ICONOS.sucursales },
  { to: '/usuarios', label: 'Usuarios', icono: ICONOS.usuarios, soloAdmin: true },
]

const CLAVE_COLAPSO = 'gymkeep.menuColapsado'

function leerColapsado() {
  try {
    return localStorage.getItem(CLAVE_COLAPSO) === '1'
  } catch {
    return false // sin almacenamiento: el menu arranca expandido
  }
}

function guardarColapsado(valor) {
  try {
    localStorage.setItem(CLAVE_COLAPSO, valor ? '1' : '0')
  } catch {
    // no se recuerda la preferencia, el menu sigue funcionando
  }
}

function claseEnlace(compacto) {
  return ({ isActive }) =>
    `flex items-center gap-3 rounded-lg text-sm font-semibold tracking-wide transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white ${
      compacto ? 'justify-center px-0 py-3' : 'px-4 py-3'
    } ${isActive ? 'bg-brand-600 text-white' : 'text-zinc-300 hover:bg-white/10 hover:text-white'}`
}

const ICONO_HAMBURGUESA = (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="w-6 h-6">
    <path d="M4 6h16M4 12h16M4 18h16" strokeLinecap="round" />
  </svg>
)
const ICONO_CERRAR = (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="w-6 h-6">
    <path d="M6 6l12 12M18 6 6 18" strokeLinecap="round" />
  </svg>
)

function Marca({ className = 'text-xl' }) {
  return (
    <span className={`font-display italic font-bold leading-none ${className}`}>
      <span className="text-white">Gym</span>
      <span className="text-brand-600">Keep</span>
    </span>
  )
}

const BOTON_CABECERA =
  'p-2 rounded-lg text-zinc-300 hover:bg-white/10 hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white'

/** Quien tiene la sesion abierta, con cambiar clave y cerrar sesion. */
function PieUsuario({ compacto, onCambiarClave }) {
  const { usuario, cerrarSesion } = useAuth()
  if (!usuario) return null

  if (compacto) {
    return (
      <div className="px-2 py-3 border-t border-white/10 flex flex-col items-center gap-1">
        <button type="button" onClick={onCambiarClave} title="Cambiar mi clave" aria-label="Cambiar mi clave" className={BOTON_CABECERA}>
          {ICONOS.llave}
        </button>
        <button type="button" onClick={cerrarSesion} title={`Cerrar sesión (${usuario.nombre})`} aria-label="Cerrar sesión" className={BOTON_CABECERA}>
          {ICONOS.salir}
        </button>
      </div>
    )
  }

  return (
    <div className="px-5 py-3 border-t border-white/10 space-y-2">
      <div className="min-w-0">
        <p className="text-sm font-semibold text-white truncate">{usuario.nombre}</p>
        <p className="text-xs text-zinc-500">{usuario.rol === 'admin' ? 'Administrador' : 'Técnico'}</p>
      </div>
      <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs">
        <button type="button" onClick={onCambiarClave} className="text-zinc-300 underline hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white rounded">
          Cambiar mi clave
        </button>
        <button type="button" onClick={cerrarSesion} className="text-zinc-300 underline hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white rounded">
          Cerrar sesión
        </button>
      </div>
    </div>
  )
}

/** Contenido del menu: logo, enlaces y pie. `compacto` deja solo iconos (riel angosto). */
function ContenidoMenu({ compacto = false, onNavegar, accionCabecera, onCambiarClave }) {
  const { esAdmin } = useAuth()
  const enlaces = ENLACES.filter((enlace) => !enlace.soloAdmin || esAdmin)
  return (
    <>
      <div className={`border-b border-white/10 ${compacto ? 'px-2 py-3' : 'px-4 pt-3 pb-4'}`}>
        <div className={`flex items-center ${compacto ? 'justify-center' : 'justify-between'}`}>
          {!compacto && <span className="text-[11px] uppercase tracking-[0.2em] text-zinc-500">Menú</span>}
          <button type="button" onClick={accionCabecera.onClick} aria-label={accionCabecera.etiqueta} title={accionCabecera.etiqueta} className={BOTON_CABECERA}>
            {accionCabecera.icono}
          </button>
        </div>
        <div className="mt-2 flex justify-center">
          {compacto ? (
            <img src="/icono.png" alt="GymKeep" className="w-12 h-12 rounded-lg" />
          ) : (
            <img src="/logo.png" alt="GymKeep" className="w-44 max-w-full h-auto" />
          )}
        </div>
      </div>

      <nav className={`flex-1 overflow-y-auto py-3 space-y-1 ${compacto ? 'px-2' : 'px-3'}`} aria-label="Secciones del panel">
        {enlaces.map((enlace) => (
          <NavLink
            key={enlace.to}
            to={enlace.to}
            end={enlace.end}
            className={claseEnlace(compacto)}
            onClick={onNavegar}
            title={compacto ? enlace.label : undefined}
            aria-label={compacto ? enlace.label : undefined}
          >
            {enlace.icono}
            {!compacto && enlace.label}
          </NavLink>
        ))}
      </nav>

      <PieUsuario compacto={compacto} onCambiarClave={onCambiarClave} />
      {!compacto && (
        <div className="px-5 py-2 border-t border-white/10 text-xs text-zinc-500">Fase 2 · Desarrollo del sistema</div>
      )}
    </>
  )
}

export default function AdminLayout() {
  const [menuAbierto, setMenuAbierto] = useState(false) // panel deslizante (movil)
  const [colapsado, setColapsado] = useState(leerColapsado) // riel de iconos (escritorio)
  const [cambiandoClave, setCambiandoClave] = useState(false)

  function alternarColapso() {
    setColapsado((actual) => {
      guardarColapsado(!actual)
      return !actual
    })
  }

  // Panel movil: Escape lo cierra y mientras esta abierto la pagina de fondo no se desplaza.
  useEffect(() => {
    if (!menuAbierto) return undefined
    const alTeclear = (e) => e.key === 'Escape' && setMenuAbierto(false)
    window.addEventListener('keydown', alTeclear)
    const overflowPrevio = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      window.removeEventListener('keydown', alTeclear)
      document.body.style.overflow = overflowPrevio
    }
  }, [menuAbierto])

  return (
    <div className="min-h-screen bg-slate-50">
      {/* Menu del lado izquierdo, fijo a la ventana: ocupa todo el alto y NO se mueve al hacer scroll. */}
      <aside
        className={`hidden md:flex fixed inset-y-0 left-0 z-30 flex-col bg-black border-r border-white/10 transition-[width] duration-200 ${
          colapsado ? 'w-[4.5rem]' : 'w-64'
        }`}
      >
        <ContenidoMenu
          compacto={colapsado}
          onCambiarClave={() => setCambiandoClave(true)}
          accionCabecera={{
            onClick: alternarColapso,
            etiqueta: colapsado ? 'Expandir menú' : 'Contraer menú',
            icono: ICONO_HAMBURGUESA,
          }}
        />
      </aside>

      {/* Movil: barra superior con el logo y la hamburguesa que abre el panel de la izquierda. */}
      <header className="md:hidden fixed top-0 inset-x-0 z-30 h-14 bg-black border-b border-white/10 flex items-center gap-2 px-4">
        <button type="button" onClick={() => setMenuAbierto(true)} aria-label="Abrir menú" aria-expanded={menuAbierto} className={`${BOTON_CABECERA} -ml-2`}>
          {ICONO_HAMBURGUESA}
        </button>
        <img src="/icono.png" alt="" className="w-9 h-9 rounded-md" />
        <Marca />
      </header>

      <div className={`md:hidden fixed inset-0 z-40 transition-[visibility] duration-300 ${menuAbierto ? 'visible' : 'invisible'}`}>
        <button
          type="button"
          aria-label="Cerrar menú"
          tabIndex={menuAbierto ? 0 : -1}
          onClick={() => setMenuAbierto(false)}
          className={`absolute inset-0 bg-black/70 transition-opacity duration-300 ${menuAbierto ? 'opacity-100' : 'opacity-0'}`}
        />
        <aside
          className={`absolute inset-y-0 left-0 w-72 max-w-[85vw] bg-black border-r border-white/10 shadow-2xl flex flex-col transition-transform duration-300 ${
            menuAbierto ? 'translate-x-0' : '-translate-x-full'
          }`}
        >
          <ContenidoMenu
            onNavegar={() => setMenuAbierto(false)}
            onCambiarClave={() => {
              setMenuAbierto(false)
              setCambiandoClave(true)
            }}
            accionCabecera={{ onClick: () => setMenuAbierto(false), etiqueta: 'Cerrar menú', icono: ICONO_CERRAR }}
          />
        </aside>
      </div>

      <main
        className={`min-w-0 px-4 sm:px-6 lg:px-8 py-5 md:py-6 pt-20 md:pt-6 transition-[margin] duration-200 ${
          colapsado ? 'md:ml-[4.5rem]' : 'md:ml-64'
        }`}
      >
        <Outlet />
      </main>

      <AlertasGraves />
      <FaqAyuda />
      {cambiandoClave && <CambiarClaveDialogo onCerrar={() => setCambiandoClave(false)} />}
    </div>
  )
}
