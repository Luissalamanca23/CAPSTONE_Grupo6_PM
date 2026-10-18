import { useEffect, useRef, useState } from 'react'
import { formatearHoras } from './uso.js'

const ALTO = 200
const M = { izq: 40, der: 8, arriba: 10, abajo: 24 }
const COLOR = '#2563eb'
const COLOR_HOVER = '#1d4ed8'

function pasoEje(maximo) {
  for (const paso of [1 / 12, 1 / 6, 0.25, 0.5, 1, 2, 3, 4, 6, 8, 12]) if (maximo / paso <= 4) return paso
  return Math.ceil(maximo / 4)
}

function etiquetaHoras(h) {
  return h < 1 ? `${Math.round(h * 60)}m` : `${h}h`
}

function fechaCorta(iso) {
  const [, mes, dia] = iso.split('-')
  return `${dia}/${mes}`
}

/** Barras de horas de uso por dia (una serie: el titulo de la tarjeta la nombra). */
export default function GraficoUsoDiario({ dias }) {
  const [activo, setActivo] = useState(null)
  // Se dibuja al ancho real del contenedor (no se estira): asi el texto mantiene su tamano.
  const contenedor = useRef(null)
  const [ANCHO, setAncho] = useState(640)
  useEffect(() => {
    const observador = new ResizeObserver(([entrada]) => setAncho(Math.max(320, Math.round(entrada.contentRect.width))))
    observador.observe(contenedor.current)
    return () => observador.disconnect()
  }, [])
  const maximo = Math.max(...dias.map((d) => d.horas), 0)
  const paso = pasoEje(maximo || 1)
  const tope = Math.max(paso, Math.ceil(maximo / paso) * paso)
  const anchoUtil = ANCHO - M.izq - M.der
  const altoUtil = ALTO - M.arriba - M.abajo
  const banda = anchoUtil / dias.length
  const anchoBarra = Math.max(3, Math.min(18, banda * 0.62))
  const y = (h) => M.arriba + altoUtil - (h / tope) * altoUtil
  const lineas = Array.from({ length: Math.round(tope / paso) + 1 }, (_, i) => i * paso)

  return (
    <div ref={contenedor} className="relative">
      <svg width={ANCHO} height={ALTO} viewBox={`0 0 ${ANCHO} ${ALTO}`} className="block" role="img" aria-label="Horas de uso por día">
        {lineas.map((h) => (
          <g key={h}>
            <line x1={M.izq} x2={ANCHO - M.der} y1={y(h)} y2={y(h)} stroke="#e2e8f0" strokeWidth="1" />
            <text x={M.izq - 6} y={y(h) + 3.5} textAnchor="end" fontSize="10" fill="#64748b">
              {etiquetaHoras(h)}
            </text>
          </g>
        ))}
        {dias.map((d, i) => {
          const x = M.izq + i * banda + (banda - anchoBarra) / 2
          const alto = Math.max(0, y(0) - y(d.horas))
          const r = Math.min(3, alto, anchoBarra / 2)
          const base = y(0)
          return (
            <g key={d.fecha}>
              {alto > 0 && (
                <path
                  d={`M${x},${base} V${base - alto + r} Q${x},${base - alto} ${x + r},${base - alto} H${x + anchoBarra - r} Q${x + anchoBarra},${base - alto} ${x + anchoBarra},${base - alto + r} V${base} Z`}
                  fill={activo === i ? COLOR_HOVER : COLOR}
                />
              )}
              {(i % 5 === 4 || i === dias.length - 1) && (
                <text x={x + anchoBarra / 2} y={ALTO - 7} textAnchor="middle" fontSize="10" fill="#64748b">
                  {fechaCorta(d.fecha)}
                </text>
              )}
              {/* Zona de hover mas grande que la barra (toda la columna). */}
              <rect
                x={M.izq + i * banda}
                y={M.arriba}
                width={banda}
                height={altoUtil}
                fill="transparent"
                onMouseEnter={() => setActivo(i)}
                onMouseLeave={() => setActivo(null)}
              />
            </g>
          )
        })}
        <line x1={M.izq} x2={ANCHO - M.der} y1={y(0)} y2={y(0)} stroke="#cbd5e1" strokeWidth="1" />
      </svg>
      {maximo === 0 && (
        <p className="absolute inset-0 flex items-center justify-center text-sm text-slate-400">
          Sin uso registrado en estos 30 días
        </p>
      )}
      {activo !== null && (
        <div
          className="absolute -translate-x-1/2 -translate-y-full pointer-events-none bg-slate-900 text-white text-xs rounded-md px-2.5 py-1.5 shadow-lg whitespace-nowrap"
          style={{
            left: `${((M.izq + activo * banda + banda / 2) / ANCHO) * 100}%`,
            top: `${(Math.min(y(dias[activo].horas), y(0) - 4) / ALTO) * 100}%`,
          }}
        >
          <p className="font-semibold">{fechaCorta(dias[activo].fecha)}</p>
          <p>
            {formatearHoras(dias[activo].horas)} · {dias[activo].sesiones} sesi{dias[activo].sesiones === 1 ? 'ón' : 'ones'}
          </p>
        </div>
      )}
    </div>
  )
}
