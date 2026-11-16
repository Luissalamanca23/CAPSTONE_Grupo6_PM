import { Route, Routes } from 'react-router-dom'
import RutaProtegida from './auth/RutaProtegida.jsx'
import AdminLayout from './layouts/AdminLayout.jsx'
import Costos from './pages/Costos.jsx'
import Dashboard from './pages/Dashboard.jsx'
import EquipoDetalle from './pages/EquipoDetalle.jsx'
import Equipos from './pages/Equipos.jsx'
import NoEncontrado from './components/NoEncontrado.jsx'
import Incidencias from './pages/Incidencias.jsx'
import Informes from './pages/Informes.jsx'
import Login from './pages/Login.jsx'
import Reportar from './pages/Reportar.jsx'
import Sucursales from './pages/Sucursales.jsx'
import Usuarios from './pages/Usuarios.jsx'
import CamaraVista from './pages/vision/CamaraVista.jsx'
import Camaras from './pages/vision/Camaras.jsx'
import UsoMaquinaDetalle from './pages/vision/UsoMaquinaDetalle.jsx'
import UsoMaquinas from './pages/vision/UsoMaquinas.jsx'

export default function App() {
  return (
    <Routes>
      {/* Pagina publica: a esta ruta apunta el codigo QR pegado en cada maquina (token del QR). */}
      <Route path="/reportar/:token" element={<Reportar />} />

      <Route path="/login" element={<Login />} />

      {/* Todo el panel exige sesion; sin ella se va al login. */}
      <Route element={<RutaProtegida />}>
        {/* Panel de administracion, con menu lateral. */}
        <Route element={<AdminLayout />}>
          <Route path="/" element={<Dashboard />} />
          <Route path="/equipos" element={<Equipos />} />
          <Route path="/equipos/:id" element={<EquipoDetalle />} />
          <Route path="/incidencias" element={<Incidencias />} />
          <Route path="/costos" element={<Costos />} />
          <Route path="/informes" element={<Informes />} />
          <Route path="/sucursales" element={<Sucursales />} />
          {/* Modulo de vision (ver vision/INTEGRACION.md) */}
          <Route path="/uso" element={<UsoMaquinas />} />
          <Route path="/uso/:id" element={<UsoMaquinaDetalle />} />
          <Route path="/camaras" element={<Camaras />} />
          <Route path="/camaras/:id" element={<CamaraVista />} />
          {/* Cuentas: solo administradores. */}
          <Route element={<RutaProtegida soloAdmin />}>
            <Route path="/usuarios" element={<Usuarios />} />
          </Route>
          <Route path="*" element={<NoEncontrado />} />
        </Route>
      </Route>
    </Routes>
  )
}
