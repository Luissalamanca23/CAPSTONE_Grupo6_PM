import { useEffect, useRef } from 'react'

// Ejecuta `tarea` ahora y luego cada `intervaloMs`, con tres cuidados:
// - se pausa mientras la pestana esta oculta y al volver ejecuta una vez de inmediato;
// - no lanza una ejecucion nueva si la anterior (promesa) sigue en curso;
// - al desmontar (o cambiar los parametros) las respuestas tardias se descartan.
// `tarea` recibe una funcion `vigente()` para no actualizar estado despues de desmontar.
// Con `activo` en false no hace nada. `clave` reinicia el ciclo cuando cambia (ej. id de camara).
export default function usePolling(tarea, intervaloMs, { activo = true, clave = null } = {}) {
  const tareaRef = useRef(tarea)
  useEffect(() => {
    tareaRef.current = tarea
  })

  useEffect(() => {
    if (!activo) return undefined
    let vigente = true
    let enVuelo = false
    const ejecutar = () => {
      if (!vigente || enVuelo || document.hidden) return
      enVuelo = true
      Promise.resolve()
        .then(() => tareaRef.current(() => vigente))
        .catch(() => {}) // cada tarea muestra sus propios errores
        .finally(() => {
          enVuelo = false
        })
    }
    const alCambiarVisibilidad = () => {
      if (!document.hidden) ejecutar()
    }
    ejecutar()
    const temporizador = setInterval(ejecutar, intervaloMs)
    document.addEventListener('visibilitychange', alCambiarVisibilidad)
    return () => {
      vigente = false
      clearInterval(temporizador)
      document.removeEventListener('visibilitychange', alCambiarVisibilidad)
    }
  }, [intervaloMs, activo, clave])
}
