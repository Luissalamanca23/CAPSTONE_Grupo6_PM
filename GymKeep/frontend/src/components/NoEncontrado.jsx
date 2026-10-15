import { Link } from 'react-router-dom'

// Pagina para rutas que no existen (se muestra dentro del panel, con el menu lateral).
export default function NoEncontrado() {
  return (
    <div className="max-w-md mx-auto text-center space-y-3 py-16">
      <p className="text-5xl font-bold text-slate-300">404</p>
      <h1 className="text-xl font-bold text-slate-900">Página no encontrada</h1>
      <p className="text-sm text-slate-500">La dirección que abriste no existe o fue movida.</p>
      <Link to="/" className="inline-block px-4 py-2 rounded-lg bg-emerald-600 text-white text-sm font-medium hover:bg-emerald-700">
        Volver al inicio
      </Link>
    </div>
  )
}
