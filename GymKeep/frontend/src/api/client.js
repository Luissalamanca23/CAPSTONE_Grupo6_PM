export const BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1'

// Error de la API con el codigo HTTP (el flujo del PIN del modulo de vision depende de .status).
// `sesion` es true cuando el 401 significa "no hay sesion iniciada o vencio" (y no un PIN malo).
export class ErrorApi extends Error {
  constructor(mensaje, status, sesion = false) {
    super(mensaje)
    this.status = status
    this.sesion = sesion
  }
}

// El contexto de sesion (auth/AuthContext.jsx) se registra aqui para enterarse cuando cualquier
// peticion descubre que la sesion vencio, y asi llevar a la persona al login.
let alExpirarSesion = null
export function registrarAlExpirarSesion(funcion) {
  alExpirarSesion = funcion
  return () => {
    if (alExpirarSesion === funcion) alExpirarSesion = null
  }
}

async function errorDe(respuesta, sesion) {
  let detalle = respuesta.statusText
  try {
    const cuerpo = await respuesta.json()
    if (cuerpo.detail) detalle = typeof cuerpo.detail === 'string' ? cuerpo.detail : JSON.stringify(cuerpo.detail)
  } catch {
    // el cuerpo no era JSON, se mantiene el statusText
  }
  return new ErrorApi(detalle, respuesta.status, sesion)
}

// fetch a la API con la cookie de sesion. Los cuerpos Blob (subida de imagenes) no llevan
// Content-Type JSON; las cabeceras de options se suman a las base. Devuelve la Response si fue ok.
export async function fetchApi(path, options = {}) {
  const respuesta = await fetch(`${BASE_URL}${path}`, {
    credentials: 'include',
    ...options,
    headers: {
      ...(options.body instanceof Blob ? {} : { 'Content-Type': 'application/json' }),
      ...options.headers,
    },
  })

  if (!respuesta.ok) {
    // La API marca "sin sesion" con WWW-Authenticate: GymKeep-Sesion (un PIN malo no la lleva).
    const sesion = respuesta.status === 401 && respuesta.headers.get('WWW-Authenticate') === 'GymKeep-Sesion'
    // Un RUN o clave incorrectos al iniciar sesion tambien llegan asi, pero no es una sesion vencida.
    if (sesion && !path.startsWith('/auth/login') && alExpirarSesion) alExpirarSesion()
    throw await errorDe(respuesta, sesion)
  }
  return respuesta
}

// Peticion JSON compartida por todas las pantallas.
export async function request(path, options = {}) {
  const respuesta = await fetchApi(path, options)
  if (respuesta.status === 204) return null
  return respuesta.json()
}

export const api = {
  // Sesion (RUN + clave numerica). Ver app/api/v1/auth.py.
  estadoAuth: () => request('/auth/estado'),
  login: (run, clave) => request('/auth/login', { method: 'POST', body: JSON.stringify({ run, clave }) }),
  logout: () => request('/auth/logout', { method: 'POST' }),
  yo: () => request('/auth/me'),
  cambiarClave: (claveActual, claveNueva) =>
    request('/auth/cambiar-clave', { method: 'POST', body: JSON.stringify({ clave_actual: claveActual, clave_nueva: claveNueva }) }),
  // Cuentas (solo administradores)
  listarUsuarios: () => request('/auth/usuarios'),
  crearUsuario: (datos) => request('/auth/usuarios', { method: 'POST', body: JSON.stringify(datos) }),
  actualizarUsuario: (id, datos) => request(`/auth/usuarios/${id}`, { method: 'PATCH', body: JSON.stringify(datos) }),

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
  urlFotoIncidencia: (id) => `${BASE_URL}/incidencias/${id}/foto`,
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
    const respuesta = await fetchApi(`/incidencias/${query}`)
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
