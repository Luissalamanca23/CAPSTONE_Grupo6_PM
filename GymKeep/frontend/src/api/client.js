export const BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1'

async function request(path, options = {}) {
  const respuesta = await fetch(`${BASE_URL}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })

  if (!respuesta.ok) {
    let detalle = respuesta.statusText
    try {
      const cuerpo = await respuesta.json()
      detalle = cuerpo.detail || detalle
    } catch {
      // el cuerpo no era JSON, se mantiene el statusText
    }
    throw new Error(detalle)
  }

  if (respuesta.status === 204) return null
  return respuesta.json()
}

export const api = {
  // Empresas / sucursales / zonas: jerarquia obligatoria para registrar equipamiento
  // (ver GymKeep_BDD_Completa). Para el Capstone normalmente hay una sola empresa/sucursal,
  // creada por la data de ejemplo (postgres/seed.sql).
  listarEmpresas: () => request('/empresas/'),
  crearEmpresa: (datos) => request('/empresas/', { method: 'POST', body: JSON.stringify(datos) }),

  listarSucursales: (empresaId) => {
    const query = empresaId ? `?empresa_id=${empresaId}` : ''
    return request(`/sucursales/${query}`)
  },
  crearSucursal: (datos) => request('/sucursales/', { method: 'POST', body: JSON.stringify(datos) }),

  listarZonas: (sucursalId) => {
    const query = sucursalId ? `?sucursal_id=${sucursalId}` : ''
    return request(`/zonas/${query}`)
  },
  crearZona: (datos) => request('/zonas/', { method: 'POST', body: JSON.stringify(datos) }),

  // Equipamiento
  listarEquipos: (sucursalId) => {
    const query = sucursalId ? `?sucursal_id=${sucursalId}` : ''
    return request(`/equipamiento/${query}`)
  },
  obtenerEquipo: (id) => request(`/equipamiento/${id}`),
  obtenerEquipoPorQr: (token) => request(`/equipamiento/qr/${token}`),
  crearEquipo: (datos) => request('/equipamiento/', { method: 'POST', body: JSON.stringify(datos) }),
  actualizarEquipo: (id, datos) =>
    request(`/equipamiento/${id}`, { method: 'PATCH', body: JSON.stringify(datos) }),
  eliminarEquipo: (id) => request(`/equipamiento/${id}`, { method: 'DELETE' }),
  regenerarQr: (id) => request(`/equipamiento/${id}/regenerar-qr`, { method: 'POST' }),
  urlCodigoQr: (id) => `${BASE_URL}/equipamiento/${id}/codigo-qr`,

  // Incidencias
  listarTiposFalla: (soloReporteQr = false) => {
    const query = soloReporteQr ? '?solo_reporte_qr=true' : ''
    return request(`/incidencias/tipos-falla${query}`)
  },
  listarIncidencias: (filtros = {}) => {
    const params = new URLSearchParams(filtros)
    const query = params.toString() ? `?${params.toString()}` : ''
    return request(`/incidencias/${query}`)
  },
  crearIncidencia: (datos) => request('/incidencias/', { method: 'POST', body: JSON.stringify(datos) }),
  crearIncidenciaPorQr: (datos) =>
    request('/incidencias/reporte-qr', { method: 'POST', body: JSON.stringify(datos) }),
  actualizarIncidencia: (id, datos) =>
    request(`/incidencias/${id}`, { method: 'PATCH', body: JSON.stringify(datos) }),
}
