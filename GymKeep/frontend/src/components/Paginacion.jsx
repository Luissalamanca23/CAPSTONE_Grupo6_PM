// Pie de paginacion: "Mostrando 1–25 de 63 · ‹ Anterior · Página 1 de 3 · Siguiente ›".
// Recibe el objeto de usePaginacion (o uno armado a mano, como en Incidencias, que pagina en
// el servidor): { pagina, setPagina, total, totalPaginas, porPagina }.
// Por defecto no se muestra si todo cabe en una sola pagina; `siempre` lo fuerza.
export default function Paginacion({ paginacion, siempre = false }) {
  const { pagina, setPagina, total, totalPaginas, porPagina } = paginacion
  if (!siempre && total <= porPagina) return null

  const desde = total === 0 ? 0 : (pagina - 1) * porPagina + 1
  const hasta = Math.min(pagina * porPagina, total)

  return (
    <div className="flex flex-wrap items-center justify-between gap-x-3 gap-y-2 px-4 py-3 border-t border-slate-200 text-sm">
      <p className="text-slate-400 text-xs">{total === 0 ? 'Sin resultados' : `Mostrando ${desde}–${hasta} de ${total}`}</p>
      <div className="flex items-center gap-2">
        <button
          type="button"
          disabled={pagina <= 1}
          onClick={() => setPagina((p) => Math.max(1, p - 1))}
          className="px-3 py-1.5 rounded-md border border-slate-300 text-xs font-medium text-slate-600 disabled:opacity-40 hover:bg-slate-50"
        >
          ‹ Anterior
        </button>
        <span className="text-xs text-slate-500">
          Página {pagina} de {totalPaginas}
        </span>
        <button
          type="button"
          disabled={pagina >= totalPaginas}
          onClick={() => setPagina((p) => Math.min(totalPaginas, p + 1))}
          className="px-3 py-1.5 rounded-md border border-slate-300 text-xs font-medium text-slate-600 disabled:opacity-40 hover:bg-slate-50"
        >
          Siguiente ›
        </button>
      </div>
    </div>
  )
}
