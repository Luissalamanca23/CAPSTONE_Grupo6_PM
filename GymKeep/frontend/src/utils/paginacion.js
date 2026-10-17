import { useEffect, useMemo, useState } from 'react'

/**
 * Paginacion en el navegador para listas que ya estan cargadas completas.
 * - `items`: la lista (ya filtrada y ordenada).
 * - `porPagina`: cuantos elementos se muestran por pagina.
 * - `claveReinicio`: texto que cambia cuando cambian los filtros; al cambiar, vuelve a la pagina 1.
 * Devuelve `visibles` (los de la pagina actual) y lo que necesita <Paginacion paginacion={...} />.
 */
export function usePaginacion(items, porPagina = 25, claveReinicio = '') {
  const [pagina, setPagina] = useState(1)

  useEffect(() => {
    setPagina(1)
  }, [claveReinicio])

  const total = items.length
  const totalPaginas = Math.max(1, Math.ceil(total / porPagina))
  // Si la lista se achica (por ejemplo al resolver incidencias), nunca queda una pagina inexistente.
  const paginaActual = Math.min(pagina, totalPaginas)

  const visibles = useMemo(
    () => items.slice((paginaActual - 1) * porPagina, paginaActual * porPagina),
    [items, paginaActual, porPagina]
  )

  return { visibles, pagina: paginaActual, setPagina, total, totalPaginas, porPagina }
}
