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

// Igual que request(), pero para enviar un archivo (imagen) tal cual, sin JSON.
async function requestBinario(path, archivo, method = 'PUT') {
  const respuesta = await fetch(`${BASE_URL}${path}`, {
    method,
    headers: { 'Content-Type': archivo.type || 'image/jpeg' },
    body: archivo,
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
  // Igual que listarIncidencias, pero ademas devuelve el total real que cumple los
  // filtros (header X-Total-Count del backend), para armar paginacion sin traer todos
  // los registros de una vez. Usado por la pagina de Incidencias (historial completo).
  listarIncidenciasPaginado: async (filtros = {}) => {
    const params = new URLSearchParams(filtros)
    const query = params.toString() ? `?${params.toString()}` : ''
    const respuesta = await fetch(`${BASE_URL}/incidencias/${query}`)
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
    const items = await respuesta.json()
    const total = Number(respuesta.headers.get('X-Total-Count') ?? items.length)
    return { items, total }
  },
  crearIncidencia: (datos) => request('/incidencias/', { method: 'POST', body: JSON.stringify(datos) }),
  crearIncidenciaPorQr: (datos) =>
    request('/incidencias/reporte-qr', { method: 'POST', body: JSON.stringify(datos) }),
  actualizarIncidencia: (id, datos) =>
    request(`/incidencias/${id}`, { method: 'PATCH', body: JSON.stringify(datos) }),

  // Mantenimientos (historial de reparaciones/servicios por equipo)
  listarMantenimientos: (equipoId) => request(`/mantenimientos/?equipo_id=${equipoId}`),
  // Igual que listarMantenimientos, pero sin acotar a un equipo: historial completo del
  // gimnasio con filtros opcionales (tipo/fecha/texto). Usado por la vista de Costos.
  listarTodosLosMantenimientos: (filtros = {}) => {
    const params = new URLSearchParams(filtros)
    const query = params.toString() ? `?${params.toString()}` : ''
    return request(`/mantenimientos/${query}`)
  },
  crearMantenimiento: (datos) => request('/mantenimientos/', { method: 'POST', body: JSON.stringify(datos) }),

  // Vision por computadora (ver vision/INTEGRACION.md). Las coordenadas de zonas y personas
  // son normalizadas 0..1 respecto de la imagen de la camara.
  listarCamaras: (sucursalId) => {
    const query = sucursalId ? `?sucursal_id=${sucursalId}` : ''
    return request(`/vision/camaras${query}`)
  },
  obtenerCamara: (id) => request(`/vision/camaras/${id}`),
  crearCamara: (datos) => request('/camaras/', { method: 'POST', body: JSON.stringify(datos) }),
  obtenerVivo: (id) => request(`/vision/camaras/${id}/vivo`),
  // Video en vivo (MJPEG): se muestra con <img src=...>; el navegador va reemplazando el cuadro.
  urlStreamCamara: (id) => `${BASE_URL}/vision/camaras/${id}/stream`,
  urlCuadroCamara: (id, marca) => `${BASE_URL}/vision/camaras/${id}/cuadro${marca ? `?t=${marca}` : ''}`,
  subirCuadroCamara: (id, archivo) => requestBinario(`/vision/camaras/${id}/cuadro`, archivo),
  guardarZona: (camaraId, equipoId, puntos) =>
    request(`/vision/camaras/${camaraId}/maquinas/${equipoId}`, { method: 'PUT', body: JSON.stringify({ puntos }) }),
  quitarZona: (camaraId, equipoId) => request(`/vision/camaras/${camaraId}/maquinas/${equipoId}`, { method: 'DELETE' }),
  guardarParametrosCamara: (id, parametros) =>
    request(`/vision/camaras/${id}/parametros`, { method: 'PUT', body: JSON.stringify(parametros) }),

  listarUsoMaquinas: (sucursalId) => {
    const query = sucursalId ? `?sucursal_id=${sucursalId}` : ''
    return request(`/vision/maquinas${query}`)
  },
  obtenerUsoMaquina: (id) => request(`/vision/maquinas/${id}`),
  urlFotoMaquina: (id, marca) => `${BASE_URL}/vision/maquinas/${id}/foto${marca ? `?t=${marca}` : ''}`,
  subirFotoMaquina: (id, archivo) => requestBinario(`/vision/maquinas/${id}/foto`, archivo),
  fotoMaquinaDesdeCamara: (id, camaraId) => {
    const query = camaraId ? `?camara_id=${camaraId}` : ''
    return request(`/vision/maquinas/${id}/foto/desde-camara${query}`, { method: 'POST' })
  },
}
