// Pruebas de los calculos del dashboard (RF-28 a RF-31): son funciones puras, asi que se
// ejecutan con el ejecutor de pruebas que trae Node (sin instalar nada):  npm test
import test from 'node:test'
import assert from 'node:assert/strict'

import {
  PERIODOS,
  UMBRAL_HORAS_PREVENTIVO,
  calcularAnalitica,
  calcularBuckets,
  calcularDemanda,
  escalaBonita,
  formatearDuracionHoras,
  porcentajeCambio,
} from '../src/utils/analitica.js'

const MS_HORA = 3600 * 1000
// Fecha fija: las pruebas no dependen del dia en que se ejecutan.
const AHORA = new Date('2026-11-13T12:00:00')
const haceHoras = (horas) => new Date(AHORA.getTime() - horas * MS_HORA).toISOString()
const MES6 = PERIODOS.find((p) => p.valor === 'mes6')
const SEM8 = PERIODOS.find((p) => p.valor === 'sem8')

function incidencia(id, equipoId, horasAtras, extra = {}) {
  return {
    id,
    equipo_id: equipoId,
    estado: 'pendiente',
    prioridad: 'urgente',
    fecha_reporte: haceHoras(horasAtras),
    fecha_resolucion: null,
    equipo: { id: equipoId, nombre: `Maquina ${equipoId}` },
    tipo_falla: { codigo: 'ROTA', nombre: 'Pieza rota / no funciona' },
    ...extra,
  }
}

function analizar(datos, periodo = MES6) {
  return calcularAnalitica(
    { incidencias: [], mantenimientos: [], equipos: [], uso: [], ...datos },
    periodo,
    AHORA
  )
}

// ---------- RF-28: atencion recomendada ----------

test('RF-28: una incidencia urgente o alta abierta hace mas de 48 h aparece como sin atender', () => {
  const { atencion } = analizar({
    incidencias: [
      incidencia(1, 1, 50), // 50 h: si
      incidencia(2, 2, 47), // 47 h: todavia no
      incidencia(3, 3, 100, { prioridad: 'alta' }), // alta y mas vieja: primera de la lista
      incidencia(4, 4, 100, { prioridad: 'media' }), // media: no entra
      incidencia(5, 5, 100, { estado: 'resuelta' }), // ya resuelta: no entra
      incidencia(6, 6, 48), // exactamente 48 h: el umbral es "mas de 48 h"
    ],
  })
  assert.deepEqual(
    atencion.urgentesViejas.map((x) => x.id),
    [3, 1]
  )
  assert.ok(atencion.urgentesViejas[0].horas > atencion.urgentesViejas[1].horas)
})

test('RF-28: 3 incidencias de una maquina en 30 dias la marcan como reincidente', () => {
  const { atencion } = analizar({
    incidencias: [
      incidencia(1, 1, 24, { estado: 'resuelta', prioridad: 'baja' }),
      incidencia(2, 1, 24 * 10, { estado: 'resuelta', prioridad: 'baja' }),
      incidencia(3, 1, 24 * 29, { estado: 'resuelta', prioridad: 'baja' }),
      incidencia(4, 2, 24, { estado: 'resuelta', prioridad: 'baja' }),
      incidencia(5, 2, 24 * 2, { estado: 'resuelta', prioridad: 'baja' }),
      incidencia(6, 3, 24, { estado: 'resuelta', prioridad: 'baja' }),
      incidencia(7, 3, 24 * 2, { estado: 'resuelta', prioridad: 'baja' }),
      incidencia(8, 3, 24 * 31, { estado: 'resuelta', prioridad: 'baja' }), // fuera de la ventana de 30 dias
    ],
  })
  assert.equal(atencion.recurrentes.length, 1)
  assert.equal(atencion.recurrentes[0].equipoId, 1)
  assert.equal(atencion.recurrentes[0].cantidad, 3)
})

test('RF-28: se sugiere mantencion desde las 200 h de uso desde la ultima mantencion', () => {
  assert.equal(UMBRAL_HORAS_PREVENTIVO, 200)
  const { atencion } = analizar({
    uso: [
      { equipo_id: 1, nombre: 'Justo', horas_desde_mantencion: 200, horas_uso: 500 },
      { equipo_id: 2, nombre: 'Casi', horas_desde_mantencion: 199, horas_uso: 500 },
      { equipo_id: 3, nombre: 'Nunca mantenida', horas_desde_mantencion: null, horas_uso: 350 },
      { equipo_id: 4, nombre: 'Nueva', horas_desde_mantencion: null, horas_uso: 20 },
    ],
  })
  assert.deepEqual(
    atencion.preventivo.map((m) => m.equipoId),
    [3, 1]
  )
  assert.equal(atencion.preventivo[0].nuncaMantenida, true)
  assert.equal(atencion.preventivo[1].nuncaMantenida, false)
})

// ---------- RF-29: costos ----------

test('RF-29: el gasto del periodo es la suma de las mantenciones y coincide con sus dos tipos', () => {
  const { kpis, gastoCorrectivo, gastoPreventivo } = analizar({
    mantenimientos: [
      { id: 1, tipo: 'preventivo', costo_total: 45000, fecha_fin: haceHoras(24 * 5), equipo: { id: 1, nombre: 'A' } },
      { id: 2, tipo: 'correctivo', costo_total: 38000, fecha_fin: haceHoras(24 * 40), equipo: { id: 2, nombre: 'B' } },
      { id: 3, tipo: 'correctivo', costo_total: null, fecha_fin: haceHoras(24 * 41), equipo: { id: 2, nombre: 'B' } },
      { id: 4, tipo: 'correctivo', costo_total: '28000', fecha_fin: haceHoras(24 * 60), equipo: { id: 3, nombre: 'C' } },
      // Hace 2 anos: queda fuera del periodo de 6 meses.
      { id: 5, tipo: 'correctivo', costo_total: 999999, fecha_fin: haceHoras(24 * 730), equipo: { id: 4, nombre: 'D' } },
    ],
  })
  const suma = (lista) => lista.reduce((total, valor) => total + valor, 0)
  assert.equal(kpis.gasto, 45000 + 38000 + 28000)
  assert.equal(suma(gastoCorrectivo) + suma(gastoPreventivo), kpis.gasto) // diferencia 0
  assert.equal(suma(gastoPreventivo), 45000)
  assert.equal(kpis.mantenimientos, 4)
  assert.equal(kpis.preventivos, 1)
})

test('RF-29: el ranking de gasto ordena las maquinas por costo y deja fuera las de costo 0', () => {
  const { rankingGasto } = analizar({
    mantenimientos: [
      { id: 1, tipo: 'correctivo', costo_total: 10000, fecha_fin: haceHoras(48), equipo: { id: 1, nombre: 'A' } },
      { id: 2, tipo: 'correctivo', costo_total: 52000, fecha_fin: haceHoras(48), equipo: { id: 2, nombre: 'B' } },
      { id: 3, tipo: 'correctivo', costo_total: 15000, fecha_fin: haceHoras(72), equipo: { id: 1, nombre: 'A' } },
      { id: 4, tipo: 'preventivo', costo_total: 0, fecha_fin: haceHoras(72), equipo: { id: 3, nombre: 'C' } },
    ],
  })
  assert.deepEqual(
    rankingGasto.map((x) => [x.etiqueta, x.valor]),
    [
      ['B', 52000],
      ['A', 25000],
    ]
  )
})

const equiposMarca = [
  { id: 1, marca: 'Technogym', categoria: 'CARDIO_MOTOR', estado: 'operativo' },
  { id: 2, marca: 'technogym ', categoria: 'CARDIO_MOTOR', estado: 'operativo' }, // misma marca: otra mayuscula y un espacio
  { id: 3, marca: 'Life Fitness', categoria: 'FUERZA_SELECTORIZADA', estado: 'operativo' },
  { id: 4, marca: null, categoria: null, estado: 'operativo' },
]
const mantMarca = (id, equipoId, costo, diasAtras = 5) => ({
  id, equipo_id: equipoId, tipo: 'correctivo', costo_total: costo, fecha_fin: haceHoras(24 * diasAtras),
})

test('RF-29: el costo por marca y por categoria suma exactamente el gasto total del periodo', () => {
  const { kpis, gastoPorMarca, gastoPorCategoria } = analizar({
    equipos: equiposMarca,
    mantenimientos: [
      mantMarca(1, 1, 45000),
      mantMarca(2, 2, 15000),
      mantMarca(3, 3, 38000),
      mantMarca(4, 4, 7000), // equipo sin marca ni categoria: no se pierde
      mantMarca(5, 99, 1000), // equipo que ya no esta en la lista: tampoco
      mantMarca(6, 3, 500000, 730), // fuera del periodo
    ],
    etiquetasCategoria: { CARDIO_MOTOR: 'Cardio con motor' },
  })
  const suma = (lista) => lista.reduce((total, x) => total + x.valor, 0)
  assert.equal(kpis.gasto, 45000 + 15000 + 38000 + 7000 + 1000)
  assert.equal(suma(gastoPorMarca), kpis.gasto) // diferencia 0
  assert.equal(suma(gastoPorCategoria), kpis.gasto) // diferencia 0
  // "Technogym" y "technogym " son la misma marca y se ordena de mayor a menor gasto.
  assert.deepEqual(gastoPorMarca.map((x) => [x.etiqueta, x.valor]), [['Technogym', 60000], ['Life Fitness', 38000], ['Sin marca', 8000]])
  assert.equal(gastoPorCategoria[0].etiqueta, 'Cardio con motor')
  assert.equal(gastoPorCategoria[0].valor, 60000)
})

test('RF-29: con mas de 6 marcas, las menores se juntan en "Otros" y la suma no cambia', () => {
  const equipos = Array.from({ length: 8 }, (_, i) => ({ id: i + 1, marca: `Marca ${i + 1}`, categoria: 'OTRO', estado: 'operativo' }))
  const mantenimientos = equipos.map((e, i) => mantMarca(i + 1, e.id, (8 - i) * 1000))
  const { kpis, gastoPorMarca } = analizar({ equipos, mantenimientos })
  assert.equal(gastoPorMarca.length, 7) // 6 marcas + "Otros"
  assert.equal(gastoPorMarca.at(-1).etiqueta, 'Otros')
  assert.equal(gastoPorMarca.reduce((total, x) => total + x.valor, 0), kpis.gasto)
})

test('RF-29: sin mantenciones con costo no hay costo por marca', () => {
  const { gastoPorMarca, gastoPorCategoria } = analizar({ equipos: equiposMarca, mantenimientos: [mantMarca(1, 1, 0), mantMarca(2, 3, null)] })
  assert.deepEqual(gastoPorMarca, [])
  assert.deepEqual(gastoPorCategoria, [])
})

test('RF-29: las marcas mas problematicas se ordenan por incidencias e informan cuantos equipos tiene cada una', () => {
  const { marcasProblematicas } = analizar({
    equipos: equiposMarca,
    incidencias: [
      incidencia(1, 1, 24), incidencia(2, 1, 48), incidencia(3, 2, 72), // Technogym: 3 incidencias en 2 equipos
      incidencia(4, 3, 24), incidencia(5, 3, 30), // Life Fitness: 2 incidencias en 1 equipo
      incidencia(6, 4, 24), // sin marca: no entra al ranking
      incidencia(7, 3, 24 * 400), // fuera del periodo
    ],
    mantenimientos: [mantMarca(1, 3, 38000)],
  })
  assert.deepEqual(marcasProblematicas.map((m) => [m.etiqueta, m.valor, m.equipos]), [['Technogym', 3, 2], ['Life Fitness', 2, 1]])
  assert.equal(marcasProblematicas[0].fallasPorEquipo, 1.5)
  assert.equal(marcasProblematicas[1].fallasPorEquipo, 2)
  assert.equal(marcasProblematicas[1].gasto, 38000)
})

test('el periodo se compara con el anterior: variacion de incidencias y de gasto', () => {
  const { kpis } = analizar({
    incidencias: [incidencia(1, 1, 24, { estado: 'resuelta' }), incidencia(2, 1, 24 * 2, { estado: 'resuelta' })],
    mantenimientos: [
      { id: 1, tipo: 'correctivo', costo_total: 20000, fecha_fin: haceHoras(24 * 3), equipo: { id: 1, nombre: 'A' } },
    ],
  })
  assert.equal(kpis.reportadas, 2)
  assert.equal(kpis.reportadasAnterior, 0)
  assert.equal(kpis.tasaResolucion, 100)
  assert.equal(porcentajeCambio(kpis.reportadas, kpis.reportadasAnterior), null) // sin periodo previo no hay %
  assert.equal(porcentajeCambio(150, 100), 50)
  assert.equal(porcentajeCambio(50, 100), -50)
})

test('el tiempo medio de resolucion usa solo incidencias resueltas del periodo', () => {
  const resuelta = (id, horasAtrasReporte, horasAtrasResolucion) =>
    incidencia(id, 1, horasAtrasReporte, { estado: 'resuelta', fecha_resolucion: haceHoras(horasAtrasResolucion) })
  const { kpis } = analizar({
    incidencias: [resuelta(1, 100, 90), resuelta(2, 200, 160), incidencia(3, 1, 30)], // 10 h y 40 h; la abierta no cuenta
  })
  assert.equal(kpis.mttrHoras, 25)
})

// ---------- periodos ----------

test('los periodos de 6 meses y de 8 semanas generan intervalos contiguos que terminan hoy', () => {
  const meses = calcularBuckets(MES6, AHORA)
  assert.equal(meses.length, 6)
  assert.equal(meses.at(-1).inicio.getMonth(), AHORA.getMonth())
  for (let i = 1; i < meses.length; i += 1) assert.equal(meses[i].inicio.getTime(), meses[i - 1].fin.getTime())

  const semanas = calcularBuckets(SEM8, AHORA)
  assert.equal(semanas.length, 8)
  assert.equal(semanas[0].inicio.getDay(), 1) // las semanas parten el lunes
  assert.ok(AHORA >= semanas.at(-1).inicio && AHORA < semanas.at(-1).fin)
})

// ---------- RF-30: demanda ----------

test('RF-30: la demanda alta y baja se calcula contra el promedio horas por dia del gimnasio', () => {
  const instalada = '2026-08-05' // unos 100 dias antes de AHORA
  const equipos = [1, 2, 3, 4, 5].map((id) => ({ id, fecha_instalacion: instalada }))
  const uso = [
    { equipo_id: 1, nombre: 'Caminadora 1', categoria: 'cardio', horas_uso: 1000 }, // ~10 h/dia
    { equipo_id: 2, nombre: 'Prensa', categoria: 'fuerza', horas_uso: 280 }, // ~2,8 h/dia
    { equipo_id: 3, nombre: 'Polea', categoria: 'fuerza', horas_uso: 280 },
    { equipo_id: 4, nombre: 'Banco', categoria: 'fuerza', horas_uso: 100 }, // ~1 h/dia
    { equipo_id: 5, nombre: 'Bici', categoria: 'cardio', horas_uso: 100 },
  ]
  const demanda = calcularDemanda({ equipos, uso }, new Date('2026-11-13T00:00:00'))
  const nivel = Object.fromEntries(demanda.maquinas.map((m) => [m.etiqueta, m.nivel]))
  assert.deepEqual(nivel, {
    'Caminadora 1': 'alta',
    Prensa: 'normal',
    Polea: 'normal',
    Banco: 'baja',
    Bici: 'baja',
  })
  assert.equal(demanda.cantidad, 5)
  assert.equal(demanda.maquinas[0].etiqueta, 'Caminadora 1') // la mas usada va primero
  assert.deepEqual(demanda.sugeridas.map((m) => m.etiqueta), ['Caminadora 1'])
  assert.equal(demanda.totalHoras, 1760)
})

test('RF-30: sin muestra suficiente no se compara (menos de 30 dias o sin horas)', () => {
  const ahora = new Date('2026-11-13T00:00:00')
  const reciente = [{ id: 1, fecha_instalacion: '2026-11-01' }] // 12 dias
  assert.equal(calcularDemanda({ equipos: reciente, uso: [{ equipo_id: 1, nombre: 'X', horas_uso: 50 }] }, ahora), null)
  const sinHoras = [{ id: 1, fecha_instalacion: '2026-01-01' }]
  assert.equal(calcularDemanda({ equipos: sinHoras, uso: [{ equipo_id: 1, nombre: 'X', horas_uso: 0 }] }, ahora), null)
  assert.equal(calcularDemanda({ equipos: [], uso: [] }, ahora), null)
})

// ---------- ejes y formatos ----------

test('la escala de los ejes parte en 0, crece de forma pareja y cubre el maximo', () => {
  for (const maximo of [0, 1, 7, 87000, 123456]) {
    const { tope, marcas } = escalaBonita(maximo)
    assert.equal(marcas[0], 0)
    assert.equal(marcas.at(-1), tope)
    assert.ok(tope >= maximo, `el tope ${tope} no cubre ${maximo}`)
    for (let i = 1; i < marcas.length; i += 1) assert.ok(marcas[i] > marcas[i - 1])
  }
})

test('la duracion se muestra en minutos, horas o dias', () => {
  assert.equal(formatearDuracionHoras(null), '—')
  assert.equal(formatearDuracionHoras(Number.NaN), '—')
  assert.equal(formatearDuracionHoras(0.5), '30 min')
  assert.match(formatearDuracionHoras(5), /^5 h$/)
  assert.equal(formatearDuracionHoras(28), '1 d 4 h')
  assert.equal(formatearDuracionHoras(48), '2 d')
})
