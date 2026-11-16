import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import { api, registrarAlExpirarSesion } from '../api/client.js'

const AuthContext = createContext(null)

/**
 * Sesion de la persona que usa el panel. La sesion vive en una cookie HttpOnly que pone la API
 * (el JavaScript de la pagina nunca ve la clave ni el token); aqui solo se guarda quien es.
 *
 * estado: 'cargando' (preguntando a la API) | 'listo' | 'sin-conexion' (la API no respondio).
 */
export function AuthProvider({ children }) {
  const [usuario, setUsuario] = useState(null)
  const [estado, setEstado] = useState('cargando')

  const comprobar = useCallback(() => {
    setEstado('cargando')
    api
      .yo()
      .then((datos) => {
        setUsuario(datos)
        setEstado('listo')
      })
      .catch((err) => {
        if (err.status === 401) {
          setUsuario(null)
          setEstado('listo')
        } else {
          setEstado('sin-conexion')
        }
      })
  }, [])

  useEffect(() => {
    comprobar()
  }, [comprobar])

  // Cualquier peticion que descubra que la sesion vencio saca a la persona al login.
  useEffect(() => registrarAlExpirarSesion(() => setUsuario(null)), [])

  const iniciarSesion = useCallback(async (run, clave) => {
    const datos = await api.login(run, clave)
    setUsuario(datos)
    setEstado('listo')
    return datos
  }, [])

  const cerrarSesion = useCallback(async () => {
    try {
      await api.logout()
    } finally {
      setUsuario(null)
    }
  }, [])

  const valor = useMemo(
    () => ({ usuario, estado, esAdmin: usuario?.rol === 'admin', iniciarSesion, cerrarSesion, reintentar: comprobar }),
    [usuario, estado, iniciarSesion, cerrarSesion, comprobar],
  )
  return <AuthContext.Provider value={valor}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const contexto = useContext(AuthContext)
  if (!contexto) throw new Error('useAuth debe usarse dentro de <AuthProvider>')
  return contexto
}
