import test from 'node:test'
import assert from 'node:assert/strict'
import { OPCIONES_USO, datosDeUso } from '../src/utils/usoReporte.js'

test('cada respuesta fija gravedad y funcional sin combinaciones contradictorias', () => {
  assert.deepEqual(datosDeUso('funciona'), { gravedad: 'leve', funcional: true })
  assert.deepEqual(datosDeUso('riesgo'), { gravedad: 'grave', funcional: true })
  assert.deepEqual(datosDeUso('detenida'), { gravedad: 'grave', funcional: false })
})

test('una respuesta desconocida o vacia no produce datos', () => {
  assert.equal(datosDeUso(null), null)
  assert.equal(datosDeUso('otra'), null)
})

test('hay tres opciones, de menos a mas grave, y solo una deja la maquina detenida', () => {
  assert.deepEqual(OPCIONES_USO.map((o) => o.valor), ['funciona', 'riesgo', 'detenida'])
  assert.equal(OPCIONES_USO.filter((o) => !o.funcional).length, 1)
})
