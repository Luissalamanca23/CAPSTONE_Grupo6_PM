import { Route, Routes } from 'react-router-dom'
import AdminLayout from './layouts/AdminLayout.jsx'
import Costos from './pages/Costos.jsx'
import Dashboard from './pages/Dashboard.jsx'
import EquipoDetalle from './pages/EquipoDetalle.jsx'
import Equipos from './pages/Equipos.jsx'
import NoEncontrado from './components/NoEncontrado.jsx'
import Incidencias from './pages/Incidencias.jsx'
import Reportar from './pages/Reportar.jsx'
import Sucursales from './pages/Sucursales.jsx'
import CamaraVista from './pages/vision/CamaraVista.jsx'
import Camaras from './pages/vision/Camaras.jsx'
import UsoMaquinaDetalle from './pages/vision/UsoMaquinaDetalle.jsx'
import UsoMaquinas from './pages/vision/UsoMaquinas.jsx'

export default function App() {
  return (
    <Routes>
      {/* Pagina publica: a esta ruta apunta el codigo QR pegado en cada maquina (token del QR). */}
      <Route path="/reportar/:token" element={<Reportar />} />

      {/* Panel de administracion, con menu lateral. */}
      <Route element={<AdminLayout />}>
        <Route path="/" element={<Dashboard />} />
        <Route path="/equipos" element={<Equipos />} />
        <Route path="/equipos/:id" element={<EquipoDetalle />} />
        <Route path="/incidencias" element={<Incidencias />} />
        <Route path="/costos" element={<Costos />} />
        <Route path="/sucursales" element={<Sucursales />} />
        {/* Modulo de vision (ver vision/INTEGRACION.md) */}
        <Route path="/uso" element={<UsoMaquinas />} />
        <Route path="/uso/:id" element={<UsoMaquinaDetalle />} />
        <Route path="/camaras" element={<Camaras />} />
        <Route path="/camaras/:id" element={<CamaraVista />} />
        <Route path="*" element={<NoEncontrado />} />
      </Route>
    </Routes>
  )
}
