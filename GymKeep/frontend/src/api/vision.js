// Cliente de /api/v1/vision: integracion del modulo de vision por computadora (camaras,
// zonas de cada maquina, estado en vivo y tiempo de uso). Ver vision/INTEGRACION.md.
import { BASE_URL } from './client.js'

async function request(path, options = {}) {
  const respuesta = await fetch(`${BASE_URL}${path}`, {
    headers: options.body instanceof Blob ? {} : { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!respuesta.ok) {
    let detalle = respuesta.statusText
    try {
      const cuerpo = await respuesta.json()
      detalle = typeof cuerpo.detail === 'string' ? cuerpo.detail : JSON.stringify(cuerpo.detail)
    } catch {
      // el cuerpo no era JSON
    }
    throw new Error(detalle)
  }
  if (respuesta.status === 204) return null
  return respuesta.json()
}

function subirImagen(path, archivo) {
  return request(path, { method: 'PUT', body: archivo, headers: { 'Content-Type': archivo.type || 'image/jpeg' } })
}

export const visionApi = {
  // Camaras y zonas
  listarCamaras: () => request('/vision/camaras'),
  obtenerCamara: (id) => request(`/vision/camaras/${id}`),
  crearCamara: (datos) => request('/camaras/', { method: 'POST', body: JSON.stringify(datos) }),
  guardarZona: (camaraId, equipoId, puntos) =>
    request(`/vision/camaras/${camaraId}/maquinas/${equipoId}`, { method: 'PUT', body: JSON.stringify({ puntos }) }),
  quitarZona: (camaraId, equipoId) => request(`/vision/camaras/${camaraId}/maquinas/${equipoId}`, { method: 'DELETE' }),
  guardarParametros: (camaraId, parametros) =>
    request(`/vision/camaras/${camaraId}/parametros`, { method: 'PUT', body: JSON.stringify(parametros) }),

  // En vivo
  obtenerVivo: (camaraId) => request(`/vision/camaras/${camaraId}/vivo`),
  urlCuadro: (camaraId, marca = Date.now()) => `${BASE_URL}/vision/camaras/${camaraId}/cuadro?t=${marca}`,
  subirCuadro: (camaraId, archivo) => subirImagen(`/vision/camaras/${camaraId}/cuadro`, archivo),

  // Uso de maquinas
  listarMaquinas: () => request('/vision/maquinas'),
  obtenerMaquina: (id) => request(`/vision/maquinas/${id}`),
  urlFoto: (id, marca = '') => `${BASE_URL}/vision/maquinas/${id}/foto?t=${marca}`,
  subirFoto: (id, archivo) => subirImagen(`/vision/maquinas/${id}/foto`, archivo),
  fotoDesdeCamara: (id) => request(`/vision/maquinas/${id}/foto/desde-camara`, { method: 'POST' }),
}
