export default function StatCard({ titulo, valor, detalle }) {
  return (
    <div className="bg-white rounded-lg border border-slate-200 p-5 shadow-sm">
      <p className="text-sm text-slate-500">{titulo}</p>
      <p className="text-3xl font-bold text-slate-900 mt-1">{valor}</p>
      {detalle && <p className="text-xs text-slate-400 mt-1">{detalle}</p>}
    </div>
  )
}
