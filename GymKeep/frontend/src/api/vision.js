// Cliente de /api/v1/vision: integracion del modulo de vision por computadora (camaras,
// zonas de cada maquina, estado en vivo y tiempo de uso). Ver vision/INTEGRACION.md.
import { BASE_URL } from './client.js'

class ErrorApi extends Error {
  constructor(mensaje, status) {
    super(mensaje)
    this.status = status
  }
}

async function request(path, options = {}) {
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
      detalle = typeof cuerpo.detail === 'string' ? cuerpo.detail : JSON.stringify(cuerpo.detail)
    } catch {
      // el cuerpo no era JSON
    }
    throw new ErrorApi(detalle, respuesta.status)
  }
  if (respuesta.status === 204) return null
  return respuesta.json()
}

// PIN de edicion (VISION_PIN en la API): editar zonas y parametros lo pide solo si el servidor
// responde 401. El PIN correcto se recuerda en la pestana (sessionStorage) hasta cerrarla.
const CLAVE_PIN = 'gymkeep.visionPin'
let pedirPin = async () => null

// La vista registra aqui el dialogo que pregunta el PIN; recibe el mensaje de error previo
// (o null) y devuelve el PIN escrito o null si se cancela.
export function registrarPedirPin(funcion) {
  pedirPin = funcion
}

function leerPin() {
  try {
    return sessionStorage.getItem(CLAVE_PIN)
  } catch {
    return null
  }
}

function recordarPin(pin) {
  try {
    if (pin) sessionStorage.setItem(CLAVE_PIN, pin)
    else sessionStorage.removeItem(CLAVE_PIN)
  } catch {
    // sin almacenamiento: se pedira de nuevo la proxima vez
  }
}

async function conPin(path, options) {
  let pin = leerPin()
  for (;;) {
    try {
      const resultado = await request(path, { ...options, headers: pin ? { 'X-Vision-Pin': pin } : {} })
      if (pin) recordarPin(pin)
      return resultado
    } catch (err) {
      if (err.status !== 401 && err.status !== 429) throw err
      recordarPin(null)
      pin = await pedirPin((pin || err.status === 429) ? err.message : null) // primera vez: sin mensaje de error
      if (!pin) throw new ErrorApi('Edición cancelada: se requiere el PIN.', 401)
    }
  }
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
    conPin(`/vision/camaras/${camaraId}/maquinas/${equipoId}`, { method: 'PUT', body: JSON.stringify({ puntos }) }),
  quitarZona: (camaraId, equipoId) => conPin(`/vision/camaras/${camaraId}/maquinas/${equipoId}`, { method: 'DELETE' }),
  guardarParametros: (camaraId, parametros) =>
    conPin(`/vision/camaras/${camaraId}/parametros`, { method: 'PUT', body: JSON.stringify(parametros) }),

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
