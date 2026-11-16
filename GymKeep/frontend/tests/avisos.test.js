import test from 'node:test'
import assert from 'node:assert/strict'
import {
  calcularAvisos,
  horasAbierta,
  textoAntiguedad,
  PLAZO_VENCIDA_HORAS,
  REAVISO_VENCIDAS_MS,
} from '../src/utils/avisos.js'

const AHORA = Date.parse('2026-11-13T12:00:00Z')
const hace = (ms) => new Date(AHORA - ms).toISOString()
const MIN = 60_000
const H = 3600_000

test('una incidencia nueva avisa una sola vez', () => {
  const inc = { id: 1, fecha_reporte: hace(10_000), prioridad: 'media' }
  const a = calcularAvisos({ pendientes: [inc], ahora: AHORA, vistas: new Set() })
  assert.deepEqual(a.nuevas.map((i) => i.id), [1])
  const b = calcularAvisos({ pendientes: [inc], ahora: AHORA + 15_000, vistas: a.vistas })
  assert.equal(b.nuevas.length, 0)
})

test('al abrir el panel las pendientes antiguas no se avisan como nuevas', () => {
  const vieja = { id: 2, fecha_reporte: hace(30 * MIN) }
  const reciente = { id: 3, fecha_reporte: hace(30_000) }
  const r = calcularAvisos({ pendientes: [vieja, reciente], ahora: AHORA, vistas: new Set(), primeraConsulta: true })
  assert.deepEqual(r.nuevas.map((i) => i.id), [3])
  assert.ok(r.vistas.has(2), 'la antigua queda marcada como vista')
})

test('una incidencia abierta mas de 48 h genera aviso de vencida', () => {
  const justa = { id: 4, fecha_reporte: hace(PLAZO_VENCIDA_HORAS * H) }
  const pasada = { id: 5, fecha_reporte: hace((PLAZO_VENCIDA_HORAS + 1) * H) }
  const r = calcularAvisos({ pendientes: [justa], enProceso: [pasada], ahora: AHORA, vistas: new Set(), primeraConsulta: true })
  assert.deepEqual(r.vencidas.map((v) => v.incidencia.id), [5])
})

test('la vencida no se repite hasta pasar el intervalo de re-aviso', () => {
  const inc = { id: 6, fecha_reporte: hace(60 * H) }
  const a = calcularAvisos({ enProceso: [inc], ahora: AHORA, vistas: new Set() })
  assert.equal(a.vencidas.length, 1)
  const b = calcularAvisos({ enProceso: [inc], ahora: AHORA + 15_000, vistas: a.vistas, vencidasAvisadas: a.vencidasAvisadas })
  assert.equal(b.vencidas.length, 0)
  const c = calcularAvisos({
    enProceso: [inc],
    ahora: AHORA + REAVISO_VENCIDAS_MS + 1,
    vistas: b.vistas,
    vencidasAvisadas: b.vencidasAvisadas,
  })
  assert.equal(c.vencidas.length, 1)
})

test('una incidencia resuelta deja de recordarse', () => {
  const inc = { id: 7, fecha_reporte: hace(60 * H) }
  const a = calcularAvisos({ pendientes: [inc], ahora: AHORA, vistas: new Set() })
  const b = calcularAvisos({ ahora: AHORA + 1000, vistas: a.vistas, vencidasAvisadas: a.vencidasAvisadas })
  assert.deepEqual(b.vencidasAvisadas, {})
})

test('las vencidas se ordenan de la mas antigua a la mas reciente', () => {
  const x = { id: 8, fecha_reporte: hace(50 * H) }
  const y = { id: 9, fecha_reporte: hace(100 * H) }
  const r = calcularAvisos({ pendientes: [x, y], ahora: AHORA, vistas: new Set(), primeraConsulta: true })
  assert.deepEqual(r.vencidas.map((v) => v.incidencia.id), [9, 8])
})

test('horasAbierta tolera fechas invalidas', () => {
  assert.equal(horasAbierta({ fecha_reporte: 'xx' }, AHORA), 0)
  assert.equal(Math.round(horasAbierta({ fecha_reporte: hace(5 * H) }, AHORA)), 5)
})

test('textoAntiguedad', () => {
  assert.equal(textoAntiguedad(0.2), 'menos de 1 h')
  assert.equal(textoAntiguedad(30), '30 h')
  assert.equal(textoAntiguedad(60), '2 d 12 h')
  assert.equal(textoAntiguedad(72), '3 d')
})
