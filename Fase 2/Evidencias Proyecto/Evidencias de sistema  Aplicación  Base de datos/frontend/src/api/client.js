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
  listarEquipos: () => request('/equipamiento/'),
  obtenerEquipo: (id) => request(`/equipamiento/${id}`),
  obtenerEquipoPorQr: (codigoQr) => request(`/equipamiento/qr/${codigoQr}`),
  crearEquipo: (datos) => request('/equipamiento/', { method: 'POST', body: JSON.stringify(datos) }),
  actualizarEquipo: (id, datos) =>
    request(`/equipamiento/${id}`, { method: 'PATCH', body: JSON.stringify(datos) }),
  urlCodigoQr: (id) => `${BASE_URL}/equipamiento/${id}/codigo-qr`,

  listarTiposFalla: () => request('/incidencias/tipos-falla'),

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
