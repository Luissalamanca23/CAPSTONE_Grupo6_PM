export const BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1'

// Error de la API con el codigo HTTP (el flujo del PIN del modulo de vision depende de .status).
export class ErrorApi extends Error {
  constructor(mensaje, status) {
    super(mensaje)
    this.status = status
  }
}

// Peticion JSON compartida por todas las pantallas. Los cuerpos Blob (subida de imagenes)
// no llevan Content-Type JSON; las cabeceras de options se suman a las base.
export async function request(path, options = {}) {
  const respuesta = await fetch(`${BASE_URL}${path}`, {
    ...options,
    headers: {
      ...(options.body instanceof Blob ? {} : { 'Content-Type': 'application/json' }),
      ...options.headers,
    },
  })

  if (!respuesta.ok) {
    let detalle = respuesta.statusText
    try {
      const cuerpo = await respuesta.json()
      if (cuerpo.detail) detalle = typeof cuerpo.detail === 'string' ? cuerpo.detail : JSON.stringify(cuerpo.detail)
    } catch {
      // el cuerpo no era JSON, se mantiene el statusText
    }
    throw new ErrorApi(detalle, respuesta.status)
  }

  if (respuesta.status === 204) return null
  return respuesta.json()
}

export const api = {
  // Conteos agregados (SQL) para el panel de gestion; no dependen de listas truncadas.
  obtenerEstadisticas: () => request('/estadisticas/'),
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
  // `extra` admite skip y limit (la API entrega a lo mas 500 filas por llamada).
  listarEquipos: (sucursalId, extra = {}) => {
    const params = new URLSearchParams(extra)
    if (sucursalId) params.set('sucursal_id', sucursalId)
    const query = params.toString() ? `?${params.toString()}` : ''
    return request(`/equipamiento/${query}`)
  },
  obtenerEquipo: (id) => request(`/equipamiento/${id}`),
  obtenerEquipoPorQr: (token) => request(`/equipamiento/qr/${token}`),
  crearEquipo: (datos) => request('/equipamiento/', { method: 'POST', body: JSON.stringify(datos) }),
  actualizarEquipo: (id, datos) =>
    request(`/equipamiento/${id}`, { method: 'PATCH', body: JSON.stringify(datos) }),
  // Eliminacion desde el panel: la API borra en cascada con `forzar=true` (el dialogo de
  // confirmacion ya mostro lo que se llevaria, via resumenEliminacion).
  resumenEliminacion: (recurso, id) => request(`/${recurso}/${id}/resumen-eliminacion`),
  eliminarEquipo: (id) => request(`/equipamiento/${id}?forzar=true`, { method: 'DELETE' }),
  eliminarSucursal: (id) => request(`/sucursales/${id}?forzar=true`, { method: 'DELETE' }),
  eliminarZona: (id) => request(`/zonas/${id}`, { method: 'DELETE' }),
  eliminarCamara: (id) => request(`/camaras/${id}?forzar=true`, { method: 'DELETE' }),
  eliminarIncidencia: (id) => request(`/incidencias/${id}`, { method: 'DELETE' }),
  eliminarMantenimiento: (id) => request(`/mantenimientos/${id}`, { method: 'DELETE' }),
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
}
