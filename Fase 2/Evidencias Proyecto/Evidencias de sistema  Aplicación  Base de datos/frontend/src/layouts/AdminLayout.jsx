import { NavLink, Outlet } from 'react-router-dom'

const ICONOS = {
  panel: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="w-5 h-5">
      <rect x="3" y="3" width="8" height="8" rx="1.5" />
      <rect x="13" y="3" width="8" height="5" rx="1.5" />
      <rect x="13" y="10" width="8" height="11" rx="1.5" />
      <rect x="3" y="13" width="8" height="8" rx="1.5" />
    </svg>
  ),
  equipos: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="w-5 h-5">
      <path d="M14.7 6.3a1 1 0 0 1 1.4 0l1.6 1.6a1 1 0 0 1 0 1.4l-8 8a1 1 0 0 1-1.4 0l-1.6-1.6a1 1 0 0 1 0-1.4l8-8Z" />
      <path d="m17.5 3.5 3 3" />
      <path d="m3.5 17.5 3 3" />
    </svg>
  ),
  incidencias: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="w-5 h-5">
      <path d="M12 9v4" />
      <path d="M12 17h.01" />
      <path d="M10.3 3.9 2.5 17.5a1.5 1.5 0 0 0 1.3 2.3h16.4a1.5 1.5 0 0 0 1.3-2.3L13.7 3.9a1.5 1.5 0 0 0-2.6 0Z" />
    </svg>
  ),
}

const ENLACES = [
  { to: '/', label: 'Panel', end: true, icono: ICONOS.panel },
  { to: '/equipos', label: 'Equipamiento', icono: ICONOS.equipos },
  { to: '/incidencias', label: 'Incidencias', icono: ICONOS.incidencias },
]

function claseEnlace({ isActive }) {
  return `flex items-center gap-3 px-4 py-2.5 rounded-lg text-sm font-medium transition-colors ${
    isActive ? 'bg-emerald-600 text-white' : 'text-slate-600 hover:bg-slate-100'
  }`
}

export default function AdminLayout() {
  return (
    <div className="min-h-screen flex bg-slate-50">
      <aside className="w-60 shrink-0 bg-white border-r border-slate-200 flex flex-col">
        <div className="px-5 py-5 border-b border-slate-100">
          <p className="text-lg font-bold text-emerald-700">GymKeep</p>
          <p className="text-xs text-slate-400">Panel de gestión</p>
        </div>
        <nav className="flex-1 px-3 py-4 space-y-1">
          {ENLACES.map((enlace) => (
            <NavLink key={enlace.to} to={enlace.to} end={enlace.end} className={claseEnlace}>
              {enlace.icono}
              {enlace.label}
            </NavLink>
          ))}
        </nav>
        <div className="px-5 py-4 border-t border-slate-100 text-xs text-slate-400">
          Fase 2 · Desarrollo del sistema
        </div>
      </aside>
      <main className="flex-1 px-6 py-6 max-w-5xl mx-auto w-full">
        <Outlet />
      </main>
    </div>
  )
}
