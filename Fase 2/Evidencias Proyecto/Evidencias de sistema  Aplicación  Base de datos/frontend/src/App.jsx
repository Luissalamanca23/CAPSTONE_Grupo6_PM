import { Route, Routes } from 'react-router-dom'
import AdminLayout from './layouts/AdminLayout.jsx'
import Dashboard from './pages/Dashboard.jsx'
import EquipoDetalle from './pages/EquipoDetalle.jsx'
import Equipos from './pages/Equipos.jsx'
import Incidencias from './pages/Incidencias.jsx'
import Reportar from './pages/Reportar.jsx'

export default function App() {
  return (
    <Routes>
      {/* Pagina publica: a esta ruta apunta el codigo QR pegado en cada maquina. */}
      <Route path="/reportar/:codigoQr" element={<Reportar />} />

      {/* Panel de administracion, con menu lateral. */}
      <Route element={<AdminLayout />}>
        <Route path="/" element={<Dashboard />} />
        <Route path="/equipos" element={<Equipos />} />
        <Route path="/equipos/:id" element={<EquipoDetalle />} />
        <Route path="/incidencias" element={<Incidencias />} />
      </Route>
    </Routes>
  )
}
