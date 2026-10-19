// Piezas para dibujar los graficos del panel (sin librerias externas: SVG y HTML con Tailwind).
//
// Reglas de diseno que siguen todas: marcas delgadas (barras de hasta 24 px con 4 px de borde
// redondeado en el extremo), cuadricula fina y discreta, 2 px de separacion entre segmentos,
// una leyenda cuando hay 2 o mas series, tooltip al pasar el mouse o con el teclado y una
// "tabla" equivalente de cada grafico (nada depende solo del color ni del tooltip).

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { escalaBonita } from '../utils/analitica.js'

export const COLORES = {
  azul: '#2a78d6',
  naranja: '#eb6834',
  aqua: '#1baf7a',
  gris: '#898781',
  rejilla: '#e1e0d9',
  eje: '#c3c2b7',
  textoEje: '#6f6e69',
  superficie: '#ffffff',
  vacio: '#f1f0ec', // celda sin datos en el mapa de calor
  // Colores de estado (siempre acompanados de un texto): solo para "bueno / alerta / critico".
  estado: { bueno: '#0ca30c', advertencia: '#fab219', critico: '#d03b3b', neutro: '#898781' },
  // Rampa secuencial de un solo tono (de poco a mucho) para el mapa de calor.
  rampa: ['#cde2fb', '#9ec5f4', '#5598e7', '#2a78d6', '#104281'],
}

const clamp = (valor, minimo, maximo) => Math.min(Math.max(valor, minimo), maximo)

// ---------------------------------------------------------------------------------------------
// Medicion y tooltip
// ---------------------------------------------------------------------------------------------

/** Ancho real del contenedor (se actualiza al redimensionar la ventana o el panel). */
export function useAncho() {
  const ref = useRef(null)
  const [ancho, setAncho] = useState(0)

  useEffect(() => {
    const elemento = ref.current
    if (!elemento) return undefined
    const medir = () => setAncho(Math.floor(elemento.getBoundingClientRect().width))
    medir()
    if (typeof ResizeObserver === 'undefined') {
      window.addEventListener('resize', medir)
      return () => window.removeEventListener('resize', medir)
    }
    const observador = new ResizeObserver(medir)
    observador.observe(elemento)
    return () => observador.disconnect()
  }, [])

  return [ref, ancho]
}

/**
 * Estado del tooltip de un grafico. El contenedor (ref) debe ser `relative`; las posiciones
 * se guardan relativas a el.
 */
export function useTooltip() {
  const [ref, ancho] = useAncho()
  const [tip, setTip] = useState(null)

  const mostrarXY = useCallback((x, y, datos) => setTip({ x, y, ...datos }), [])

  const mostrarPuntero = useCallback(
    (evento, datos) => {
      const caja = ref.current?.getBoundingClientRect()
      if (!caja) return
      setTip({ x: evento.clientX - caja.left, y: evento.clientY - caja.top, ...datos })
    },
    [ref]
  )

  const mostrarFoco = useCallback(
    (evento, datos) => {
      const caja = ref.current?.getBoundingClientRect()
      if (!caja) return
      const marca = evento.currentTarget.getBoundingClientRect()
      setTip({
        x: marca.left + marca.width / 2 - caja.left,
        y: marca.top + marca.height / 2 - caja.top,
        ...datos,
      })
    },
    [ref]
  )

  const ocultar = useCallback(() => setTip(null), [])

  return { ref, ancho, tip, mostrarXY, mostrarPuntero, mostrarFoco, ocultar }
}

/** Muestra una serie con un trazo corto (lineas) o un cuadrito (barras). */
export function Clave({ color, forma = 'caja' }) {
  if (forma === 'linea') {
    return <span className="inline-block shrink-0 rounded-full" style={{ width: 14, height: 3, background: color }} />
  }
  return <span className="inline-block shrink-0 rounded-sm" style={{ width: 10, height: 10, background: color }} />
}

/** El valor manda; el nombre de la serie va en segundo plano. */
export function Tooltip({ tip, ancho }) {
  if (!tip) return null
  const aLaIzquierda = tip.x > ancho * 0.55
  return (
    <div
      className="pointer-events-none absolute z-20 min-w-[9rem] max-w-[16rem] rounded-md border border-slate-200 bg-white px-3 py-2 text-xs shadow-lg"
      style={{
        left: tip.x,
        top: Math.max(tip.y, 30),
        transform: `translate(${aLaIzquierda ? 'calc(-100% - 14px)' : '14px'}, -50%)`,
      }}
    >
      {tip.titulo && <p className="mb-1 font-medium text-slate-500">{tip.titulo}</p>}
      <ul className="space-y-1">
        {tip.filas.map((fila, i) => (
          <li key={`${fila.etiqueta}-${i}`} className="flex items-center gap-1.5">
            {fila.color && <Clave color={fila.color} forma={fila.forma} />}
            <span className="font-semibold tabular-nums text-slate-900">{fila.valor}</span>
            {fila.etiqueta && <span className="text-slate-500">{fila.etiqueta}</span>}
          </li>
        ))}
      </ul>
      {tip.nota && <p className="mt-1 text-slate-500">{tip.nota}</p>}
    </div>
  )
}

// ---------------------------------------------------------------------------------------------
// Marco de cada grafico: titulo, leyenda y tabla equivalente
// ---------------------------------------------------------------------------------------------

export function Leyenda({ items, forma = 'caja' }) {
  return (
    <ul className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-600">
      {items.map((item) => (
        <li key={item.etiqueta} className="inline-flex items-center gap-1.5">
          <Clave color={item.color} forma={forma} />
          {item.etiqueta}
        </li>
      ))}
    </ul>
  )
}

/** Version en tabla de un grafico: `columnas` son los titulos y `filas` arreglos de celdas. */
export function TablaDatos({ columnas, filas }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead className="text-slate-500">
          <tr>
            {columnas.map((columna, i) => (
              <th key={columna} className={`py-1.5 font-medium ${i === 0 ? 'pr-3 text-left' : 'pl-3 text-right'}`}>
                {columna}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {filas.map((fila, f) => (
            <tr key={`${fila[0]}-${f}`} className="border-t border-slate-100">
              {fila.map((celda, c) => (
                <td
                  key={`${columnas[c]}-${c}`}
                  className={`py-1.5 ${c === 0 ? 'pr-3 text-left text-slate-700' : 'pl-3 text-right tabular-nums text-slate-900'}`}
                >
                  {celda}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

/**
 * Tarjeta que envuelve un grafico. `tabla` = { columnas, filas } habilita el boton
 * "Ver tabla"; `leyenda` = { items, forma } dibuja la leyenda (solo con 2 o mas series).
 */
export function TarjetaGrafico({ titulo, subtitulo, tabla, leyenda, vacio = false, mensajeVacio, className = '', children }) {
  const [verTabla, setVerTabla] = useState(false)
  return (
    <section className={`flex flex-col rounded-lg border border-slate-200 bg-white p-5 shadow-sm ${className}`}>
      <header className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="font-semibold text-slate-800">{titulo}</h3>
          {subtitulo && <p className="mt-0.5 text-xs text-slate-500">{subtitulo}</p>}
        </div>
        {tabla && !vacio && (
          <button
            type="button"
            onClick={() => setVerTabla((v) => !v)}
            aria-pressed={verTabla}
            className="shrink-0 rounded-md border border-slate-200 px-2 py-1 text-xs font-medium text-slate-500 hover:bg-slate-50 hover:text-slate-900"
          >
            {verTabla ? 'Ver gráfico' : 'Ver tabla'}
          </button>
        )}
      </header>
      {leyenda && !vacio && !verTabla && (
        <div className="mt-3">
          <Leyenda items={leyenda.items} forma={leyenda.forma} />
        </div>
      )}
      <div className="mt-4 flex-1">
        {vacio ? (
          <p className="py-10 text-center text-sm text-slate-400">{mensajeVacio || 'Sin datos en este periodo.'}</p>
        ) : verTabla ? (
          <TablaDatos columnas={tabla.columnas} filas={tabla.filas} />
        ) : (
          children
        )}
      </div>
    </section>
  )
}

/** Tarjeta de cifra del periodo, con variacion respecto al periodo anterior. */
export function TarjetaKpi({ titulo, valor, detalle, delta }) {
  const color =
    delta?.bueno === true ? 'text-emerald-700' : delta?.bueno === false ? 'text-red-600' : 'text-slate-500'
  const simbolo = delta?.direccion === 'sube' ? '▲' : delta?.direccion === 'baja' ? '▼' : '●'
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
      <p className="text-sm text-slate-500">{titulo}</p>
      <p className="mt-1 text-3xl font-bold text-slate-900">{valor}</p>
      {delta && (
        <p className={`mt-1 text-xs font-medium ${color}`}>
          <span aria-hidden="true">{simbolo} </span>
          {delta.texto}
        </p>
      )}
      {detalle && <p className="mt-1 text-xs text-slate-400">{detalle}</p>}
    </div>
  )
}

// ---------------------------------------------------------------------------------------------
// Barras horizontales (rankings y distribuciones)
// ---------------------------------------------------------------------------------------------

/**
 * Ranking en barras. `items` = [{ id, etiqueta, valor, detalle? }]. Una sola serie: un solo
 * color para todas las barras (el largo ya dice cuanto es).
 */
export function BarrasHorizontales({ items, formatoValor = String, nombreValor = '', color = COLORES.azul }) {
  const { ref, ancho, tip, mostrarPuntero, mostrarFoco, ocultar } = useTooltip()
  const maximo = Math.max(1, ...items.map((item) => item.valor))

  return (
    <div ref={ref} className="relative">
      <ul className="space-y-1.5">
        {items.map((item) => {
          const valorTexto = formatoValor(item.valor)
          const datos = {
            titulo: item.etiqueta,
            filas: [{ color, forma: 'caja', valor: valorTexto, etiqueta: nombreValor }],
            nota: item.detalle,
          }
          return (
            <li
              key={item.id}
              tabIndex={0}
              aria-label={`${item.etiqueta}: ${valorTexto} ${nombreValor}`.trim()}
              onPointerMove={(e) => mostrarPuntero(e, datos)}
              onPointerLeave={ocultar}
              onFocus={(e) => mostrarFoco(e, datos)}
              onBlur={ocultar}
              className="group -mx-1 grid grid-cols-[minmax(0,11rem)_minmax(0,1fr)_auto] items-center gap-3 rounded px-1 py-0.5 outline-none hover:bg-slate-50 focus-visible:bg-slate-50 focus-visible:ring-2 focus-visible:ring-slate-300"
            >
              <span className="truncate text-sm text-slate-700" title={item.etiqueta}>
                {item.etiqueta}
              </span>
              <span className="flex h-5 items-center border-l border-slate-300">
                <span
                  className="block flex-none transition group-hover:brightness-110 group-focus-visible:brightness-110"
                  style={{
                    width: `${Math.max((item.valor / maximo) * 100, 1.5)}%`,
                    height: 10,
                    background: color,
                    borderRadius: '0 4px 4px 0',
                  }}
                />
              </span>
              <span className="min-w-[3.5rem] text-right text-sm font-medium tabular-nums text-slate-900">{valorTexto}</span>
            </li>
          )
        })}
      </ul>
      <Tooltip tip={tip} ancho={ancho} />
    </div>
  )
}

// ---------------------------------------------------------------------------------------------
// Barra apilada de un solo tramo (parte de un total, p. ej. estado de la flota)
// ---------------------------------------------------------------------------------------------

/** `segmentos` = [{ clave, etiqueta, valor, color }]. Los de valor 0 no se dibujan. */
export function BarraApilada({ segmentos, nombreValor = '' }) {
  const { ref, ancho, tip, mostrarPuntero, mostrarFoco, ocultar } = useTooltip()
  const visibles = segmentos.filter((segmento) => segmento.valor > 0)
  const total = visibles.reduce((suma, segmento) => suma + segmento.valor, 0)

  return (
    <div ref={ref} className="relative">
      <div className="flex" style={{ gap: 2, height: 16 }}>
        {visibles.map((segmento, i) => {
          const porcentaje = Math.round((segmento.valor / total) * 100)
          const datos = {
            titulo: segmento.etiqueta,
            filas: [{ color: segmento.color, forma: 'caja', valor: segmento.valor, etiqueta: nombreValor }],
            nota: `${porcentaje}% del total`,
          }
          const radio = (alIzquierda, alDerecha) =>
            `${alIzquierda ? 4 : 0}px ${alDerecha ? 4 : 0}px ${alDerecha ? 4 : 0}px ${alIzquierda ? 4 : 0}px`
          return (
            <span
              key={segmento.clave}
              tabIndex={0}
              aria-label={`${segmento.etiqueta}: ${segmento.valor} ${nombreValor} (${porcentaje}%)`.trim()}
              onPointerMove={(e) => mostrarPuntero(e, datos)}
              onPointerLeave={ocultar}
              onFocus={(e) => mostrarFoco(e, datos)}
              onBlur={ocultar}
              className="block outline-none transition hover:brightness-110 focus-visible:brightness-110 focus-visible:ring-2 focus-visible:ring-slate-400"
              style={{
                flex: `${segmento.valor} 1 0`,
                background: segmento.color,
                borderRadius: radio(i === 0, i === visibles.length - 1),
              }}
            />
          )
        })}
      </div>
      <Tooltip tip={tip} ancho={ancho} />
    </div>
  )
}

// ---------------------------------------------------------------------------------------------
// Lineas (tendencia en el tiempo)
// ---------------------------------------------------------------------------------------------

function pasoEtiquetas(cantidad, anchoDisponible, anchoEtiqueta = 52) {
  if (cantidad <= 1) return 1
  return Math.max(1, Math.ceil((anchoEtiqueta * cantidad) / Math.max(anchoDisponible, 1)))
}

/**
 * `series` = [{ id, nombre, color, valores }] con un valor por cada etiqueta.
 * Una sola escala (nunca dos ejes). Cruz vertical que salta al intervalo mas cercano.
 */
export function GraficoLineas({ etiquetas, etiquetasLargas, series, formatoValor = String, alto = 230 }) {
  const { ref, ancho, tip, mostrarXY, ocultar } = useTooltip()
  const [activo, setActivo] = useState(null)

  const cantidad = etiquetas.length
  const maximo = Math.max(0, ...series.flatMap((serie) => serie.valores))
  const escala = useMemo(() => escalaBonita(maximo), [maximo])

  const margen = { izq: 34, der: 22, arr: 10, aba: 26 }
  const anchoPlot = Math.max(ancho - margen.izq - margen.der, 10)
  const altoPlot = alto - margen.arr - margen.aba
  const x = (i) => margen.izq + (cantidad === 1 ? anchoPlot / 2 : (i * anchoPlot) / (cantidad - 1))
  const y = (valor) => margen.arr + altoPlot - (valor / escala.tope) * altoPlot
  const paso = pasoEtiquetas(cantidad, anchoPlot)

  function activar(indice) {
    const i = clamp(indice, 0, cantidad - 1)
    setActivo(i)
    const masAlto = Math.max(...series.map((serie) => serie.valores[i]))
    mostrarXY(x(i), y(masAlto), {
      titulo: etiquetasLargas[i],
      filas: series.map((serie) => ({
        color: serie.color,
        forma: 'linea',
        valor: formatoValor(serie.valores[i]),
        etiqueta: serie.nombre,
      })),
    })
  }

  function desactivar() {
    setActivo(null)
    ocultar()
  }

  function alMoverPuntero(evento) {
    const caja = evento.currentTarget.getBoundingClientRect()
    const relativo = evento.clientX - caja.left
    activar(cantidad === 1 ? 0 : Math.round((relativo / Math.max(caja.width, 1)) * (cantidad - 1)))
  }

  function alPulsarTecla(evento) {
    if (evento.key === 'ArrowRight' || evento.key === 'ArrowLeft') {
      evento.preventDefault()
      const base = activo === null ? cantidad - 1 : activo
      activar(base + (evento.key === 'ArrowRight' ? 1 : -1))
    } else if (evento.key === 'Escape') {
      desactivar()
    }
  }

  return (
    <div ref={ref} className="relative" style={{ minHeight: alto }}>
      {ancho > 0 && (
        <svg
          width={ancho}
          height={alto}
          tabIndex={0}
          role="group"
          aria-label="Gráfico de líneas. Usa las flechas izquierda y derecha para recorrer los intervalos."
          onKeyDown={alPulsarTecla}
          onFocus={() => activar(cantidad - 1)}
          onBlur={desactivar}
          className="block rounded outline-none focus-visible:ring-2 focus-visible:ring-slate-300"
        >
          {escala.marcas.map((marca) => (
            <g key={marca}>
              <line
                x1={margen.izq}
                x2={ancho - margen.der}
                y1={y(marca)}
                y2={y(marca)}
                stroke={marca === 0 ? COLORES.eje : COLORES.rejilla}
                strokeWidth={1}
              />
              <text x={margen.izq - 8} y={y(marca) + 4} textAnchor="end" fontSize={11} fill={COLORES.textoEje}>
                {marca.toLocaleString('es-CL')}
              </text>
            </g>
          ))}

          {etiquetas.map((etiqueta, i) =>
            (cantidad - 1 - i) % paso === 0 ? (
              <text key={`${etiqueta}-${i}`} x={x(i)} y={alto - 8} textAnchor="middle" fontSize={11} fill={COLORES.textoEje}>
                {etiqueta}
              </text>
            ) : null
          )}

          {activo !== null && (
            <line x1={x(activo)} x2={x(activo)} y1={margen.arr} y2={margen.arr + altoPlot} stroke={COLORES.eje} strokeWidth={1} />
          )}

          {series.map((serie) => (
            <g key={serie.id}>
              <path
                d={serie.valores.map((valor, i) => `${i === 0 ? 'M' : 'L'}${x(i)},${y(valor)}`).join(' ')}
                fill="none"
                stroke={serie.color}
                strokeWidth={2}
                strokeLinecap="round"
                strokeLinejoin="round"
              />
              {/* Punto del extremo (o del intervalo activo) con anillo del color de la superficie */}
              <circle
                cx={x(activo ?? cantidad - 1)}
                cy={y(serie.valores[activo ?? cantidad - 1])}
                r={4}
                fill={serie.color}
                stroke={COLORES.superficie}
                strokeWidth={2}
              />
            </g>
          ))}

          {/* Capa que recibe el mouse: cubre todo el area, no solo los 2 px de la linea */}
          <rect
            x={margen.izq}
            y={margen.arr}
            width={anchoPlot}
            height={altoPlot}
            fill="transparent"
            onPointerMove={alMoverPuntero}
            onPointerLeave={desactivar}
          />
        </svg>
      )}
      <Tooltip tip={tip} ancho={ancho} />
    </div>
  )
}

// ---------------------------------------------------------------------------------------------
// Columnas apiladas (cuanto, y de que tipo, por intervalo)
// ---------------------------------------------------------------------------------------------

function trazoColumna(x, y, ancho, alto, radio) {
  // Redondeado arriba, recto sobre la base.
  const r = Math.min(radio, alto, ancho / 2)
  return `M${x},${y + alto} L${x},${y + r} Q${x},${y} ${x + r},${y} L${x + ancho - r},${y} Q${x + ancho},${y} ${x + ancho},${y + r} L${x + ancho},${y + alto} Z`
}

/**
 * `series` = [{ id, nombre, color, valores }] se apilan en ese orden (la primera abajo).
 * Separacion de 2 px entre tramos, columnas de hasta 24 px.
 */
export function GraficoColumnasApiladas({ etiquetas, etiquetasLargas, series, formatoValor = String, formatoEje = String, alto = 240 }) {
  const { ref, ancho, tip, mostrarXY, ocultar } = useTooltip()
  const [activo, setActivo] = useState(null)

  const cantidad = etiquetas.length
  const totales = etiquetas.map((_, i) => series.reduce((suma, serie) => suma + serie.valores[i], 0))
  const escala = useMemo(() => escalaBonita(Math.max(0, ...totales)), [totales.join('|')]) // eslint-disable-line react-hooks/exhaustive-deps

  const anchoEtiquetaEje = Math.max(...escala.marcas.map((marca) => formatoEje(marca).length)) * 6.4
  const margen = { izq: Math.ceil(anchoEtiquetaEje) + 14, der: 8, arr: 10, aba: 26 }
  const anchoPlot = Math.max(ancho - margen.izq - margen.der, 10)
  const altoPlot = alto - margen.arr - margen.aba
  const banda = anchoPlot / cantidad
  const anchoColumna = Math.min(24, banda * 0.6)
  const y = (valor) => margen.arr + altoPlot - (valor / escala.tope) * altoPlot
  const paso = pasoEtiquetas(cantidad, anchoPlot, 48)

  function activar(i) {
    setActivo(i)
    mostrarXY(margen.izq + i * banda + banda / 2, y(totales[i]), {
      titulo: etiquetasLargas[i],
      filas: [
        ...series.map((serie) => ({
          color: serie.color,
          forma: 'caja',
          valor: formatoValor(serie.valores[i]),
          etiqueta: serie.nombre,
        })),
        ...(series.length > 1 ? [{ valor: formatoValor(totales[i]), etiqueta: 'Total' }] : []),
      ],
    })
  }

  function desactivar() {
    setActivo(null)
    ocultar()
  }

  return (
    <div ref={ref} className="relative" style={{ minHeight: alto }}>
      {ancho > 0 && (
        <svg width={ancho} height={alto} role="group" aria-label="Gráfico de columnas apiladas" className="block">
          {escala.marcas.map((marca) => (
            <g key={marca}>
              <line
                x1={margen.izq}
                x2={ancho - margen.der}
                y1={y(marca)}
                y2={y(marca)}
                stroke={marca === 0 ? COLORES.eje : COLORES.rejilla}
                strokeWidth={1}
              />
              <text x={margen.izq - 8} y={y(marca) + 4} textAnchor="end" fontSize={11} fill={COLORES.textoEje}>
                {formatoEje(marca)}
              </text>
            </g>
          ))}

          {etiquetas.map((etiqueta, i) => {
            const inicioX = margen.izq + i * banda
            const bx = inicioX + (banda - anchoColumna) / 2
            let acumulado = 0
            const tramos = []
            series.forEach((serie) => {
              const valor = serie.valores[i]
              if (valor > 0) {
                tramos.push({ serie, desde: acumulado, hasta: acumulado + valor })
                acumulado += valor
              }
            })
            return (
              <g
                key={`${etiqueta}-${i}`}
                tabIndex={0}
                aria-label={`${etiquetasLargas[i]}: ${formatoValor(totales[i])}`}
                onPointerMove={() => activar(i)}
                onPointerLeave={desactivar}
                onFocus={() => activar(i)}
                onBlur={desactivar}
                className="outline-none"
              >
                <rect
                  x={inicioX}
                  y={margen.arr}
                  width={banda}
                  height={altoPlot}
                  fill={activo === i ? '#f1f5f9' : 'transparent'}
                />
                {tramos.map((tramo, k) => {
                  const arriba = y(tramo.hasta) + (k < tramos.length - 1 ? 1 : 0)
                  const abajo = y(tramo.desde) - (k > 0 ? 1 : 0)
                  const altoTramo = Math.max(abajo - arriba, 1)
                  return k === tramos.length - 1 ? (
                    <path key={tramo.serie.id} d={trazoColumna(bx, arriba, anchoColumna, altoTramo, 4)} fill={tramo.serie.color} />
                  ) : (
                    <rect key={tramo.serie.id} x={bx} y={arriba} width={anchoColumna} height={altoTramo} fill={tramo.serie.color} />
                  )
                })}
                {(cantidad - 1 - i) % paso === 0 && (
                  <text x={inicioX + banda / 2} y={alto - 8} textAnchor="middle" fontSize={11} fill={COLORES.textoEje}>
                    {etiqueta}
                  </text>
                )}
              </g>
            )
          })}
        </svg>
      )}
      <Tooltip tip={tip} ancho={ancho} />
    </div>
  )
}

// ---------------------------------------------------------------------------------------------
// Mapa de calor (dia de la semana x bloque horario)
// ---------------------------------------------------------------------------------------------

function indiceRampa(valor, maximo) {
  return clamp(Math.ceil((valor / maximo) * COLORES.rampa.length) - 1, 0, COLORES.rampa.length - 1)
}

/** `matriz[fila][columna]` con los conteos. Las celdas muestran su numero (no solo el color). */
export function MapaCalor({ matriz, maximo, filas, columnas, unidad = 'incidencias' }) {
  const { ref, ancho, tip, mostrarPuntero, ocultar } = useTooltip()

  return (
    <div ref={ref} className="relative">
      <div className="grid text-xs" style={{ gridTemplateColumns: '3rem repeat(6, minmax(0, 1fr))', gap: 2 }}>
        <span />
        {columnas.map((columna) => (
          <span key={columna} className="pb-1 text-center text-slate-500">
            {columna}
          </span>
        ))}
        {filas.map((fila, f) => (
          <div key={fila} className="contents">
            <span className="flex items-center text-slate-500">{fila.slice(0, 3)}</span>
            {matriz[f].map((valor, c) => {
              const paso = valor > 0 ? indiceRampa(valor, maximo) : -1
              const datos = {
                titulo: `${fila} · ${columnas[c]}`,
                filas: [
                  {
                    color: paso >= 0 ? COLORES.rampa[paso] : COLORES.vacio,
                    forma: 'caja',
                    valor,
                    etiqueta: valor === 1 ? unidad.replace(/s$/, '') : unidad,
                  },
                ],
              }
              return (
                <span
                  key={`${fila}-${columnas[c]}`}
                  aria-label={`${fila}, ${columnas[c]}: ${valor} ${unidad}`}
                  onPointerMove={(e) => mostrarPuntero(e, datos)}
                  onPointerLeave={ocultar}
                  className="flex h-8 items-center justify-center rounded text-xs font-medium tabular-nums transition hover:brightness-110"
                  style={{
                    background: paso >= 0 ? COLORES.rampa[paso] : COLORES.vacio,
                    color: paso >= 3 ? '#ffffff' : '#0b0b0b',
                  }}
                >
                  {valor > 0 ? valor : ''}
                </span>
              )
            })}
          </div>
        ))}
      </div>

      <div className="mt-3 flex items-center gap-1.5 text-xs text-slate-500">
        <span>Menos</span>
        {COLORES.rampa.map((color) => (
          <span key={color} className="inline-block rounded-sm" style={{ width: 16, height: 10, background: color }} />
        ))}
        <span>Más</span>
        <span className="ml-3 inline-flex items-center gap-1.5">
          <span className="inline-block rounded-sm" style={{ width: 16, height: 10, background: COLORES.vacio }} />
          Sin {unidad}
        </span>
      </div>
      <Tooltip tip={tip} ancho={ancho} />
    </div>
  )
}
