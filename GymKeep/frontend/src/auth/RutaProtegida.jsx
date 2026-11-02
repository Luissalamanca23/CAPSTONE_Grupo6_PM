import { Navigate, Outlet, useLocation } from 'react-router-dom'
import { useAuth } from './AuthContext.jsx'

function Pantalla({ children }) {
  return <div className="min-h-screen bg-slate-50 flex items-center justify-center px-4">{children}</div>
}

/**
 * Envuelve las rutas que exigen sesion. Sin sesion lleva al login y, al entrar, vuelve a la
 * pagina que se queria abrir. `soloAdmin` deja pasar solo a administradores.
 * (La API vuelve a comprobar todo: esto solo evita mostrar pantallas que no se podrian usar.)
 */
export default function RutaProtegida({ soloAdmin = false }) {
  const { usuario, estado, esAdmin, reintentar } = useAuth()
  const ubicacion = useLocation()

  if (estado === 'cargando') {
    return (
      <Pantalla>
        <p role="status" className="text-sm text-slate-500">
          Comprobando sesión…
        </p>
      </Pantalla>
    )
  }

  if (estado === 'sin-conexion') {
    return (
      <Pantalla>
        <div role="alert" className="max-w-sm text-center space-y-3">
          <p className="text-sm text-slate-700">No se pudo conectar con el servidor.</p>
          <button
            type="button"
            onClick={reintentar}
            className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-600 focus-visible:ring-offset-2"
          >
            Reintentar
          </button>
        </div>
      </Pantalla>
    )
  }

  if (!usuario) return <Navigate to="/login" replace state={{ desde: ubicacion.pathname + ubicacion.search }} />

  if (soloAdmin && !esAdmin) {
    return (
      <Pantalla>
        <div role="alert" className="max-w-sm text-center space-y-2">
          <h1 className="text-2xl">Acceso restringido</h1>
          <p className="text-sm text-slate-600">Esta sección es solo para administradores.</p>
        </div>
      </Pantalla>
    )
  }

  return <Outlet />
}
