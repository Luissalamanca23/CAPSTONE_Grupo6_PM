import { useState } from 'react'
import { NavLink, Outlet } from 'react-router-dom'
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
  { to: '/sucursales', label: 'Sucursales', icono: ICONOS.sucursales },
]

function claseEnlace({ isActive }) {
  return `flex items-center gap-3 px-4 py-2.5 rounded-lg text-sm font-medium transition-colors ${
    isActive ? 'bg-emerald-600 text-white' : 'text-slate-600 hover:bg-slate-100'
  }`
}

function ContenidoMenu({ onNavegar }) {
  return (
    <>
      <div className="px-5 py-4 border-b border-slate-100">
        <p className="text-lg font-bold text-emerald-700">GymKeep</p>
        <p className="text-xs text-slate-400">Panel de gestión</p>
      </div>
      <nav className="flex-1 px-3 py-3 space-y-1">
        {ENLACES.map((enlace) => (
          <NavLink key={enlace.to} to={enlace.to} end={enlace.end} className={claseEnlace} onClick={onNavegar}>
            {enlace.icono}
            {enlace.label}
          </NavLink>
        ))}
      </nav>
      <div className="px-5 py-3 border-t border-slate-100 text-xs text-slate-400">
        Fase 2 · Desarrollo del sistema
      </div>
    </>
  )
}

export default function AdminLayout() {
  const [menuAbierto, setMenuAbierto] = useState(false)

  return (
    <div className="min-h-screen flex bg-slate-50">
      {/* Menu lateral fijo en pantallas medianas o mas grandes */}
      <aside className="hidden md:flex flex-col w-56 shrink-0 bg-white border-r border-slate-200">
        <ContenidoMenu />
      </aside>

      {/* En movil no hay espacio para un menu lateral fijo: una barra superior angosta
          con boton hamburguesa abre el mismo menu como panel deslizante. */}
      <div className="md:hidden fixed top-0 inset-x-0 z-30 bg-white border-b border-slate-200 flex items-center justify-between px-4 py-3">
        <p className="font-bold text-emerald-700">GymKeep</p>
        <button
          type="button"
          onClick={() => setMenuAbierto(true)}
          aria-label="Abrir menú"
          className="p-1.5 -mr-1.5 text-slate-600"
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="w-6 h-6">
            <path d="M4 6h16M4 12h16M4 18h16" strokeLinecap="round" />
          </svg>
        </button>
      </div>

      {menuAbierto && (
        <div className="md:hidden fixed inset-0 z-40 flex">
          <button
            type="button"
            aria-label="Cerrar menú"
            onClick={() => setMenuAbierto(false)}
            className="absolute inset-0 bg-slate-900/30"
          />
          <aside className="relative w-64 h-full bg-white shadow-xl flex flex-col">
            <ContenidoMenu onNavegar={() => setMenuAbierto(false)} />
          </aside>
        </div>
      )}

      <main className="flex-1 min-w-0 px-4 sm:px-6 lg:px-8 py-5 md:py-6 pt-20 md:pt-6 w-full">
        <Outlet />
      </main>

      <FaqAyuda />
    </div>
  )
}
