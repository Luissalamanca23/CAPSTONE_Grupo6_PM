import test from 'node:test'
import assert from 'node:assert/strict'

import { getSaludEquipo } from '../src/utils/saludEquipo.js'

test('el color de salud sube con las incidencias abiertas: verde, naranjo y rojo', () => {
  assert.equal(getSaludEquipo({ estado: 'operativo', incidencias_abiertas: 0 }).clave, 'verde')
  assert.equal(getSaludEquipo({ estado: 'operativo', incidencias_abiertas: 1 }).clave, 'verde')
  assert.equal(getSaludEquipo({ estado: 'operativo', incidencias_abiertas: 2 }).clave, 'naranjo')
  assert.equal(getSaludEquipo({ estado: 'operativo', incidencias_abiertas: 3 }).clave, 'naranjo')
  assert.equal(getSaludEquipo({ estado: 'operativo', incidencias_abiertas: 4 }).clave, 'rojo')
})

test('una maquina fuera de servicio es negra sin importar cuantas incidencias tenga', () => {
  assert.equal(getSaludEquipo({ estado: 'fuera_de_servicio', incidencias_abiertas: 0 }).clave, 'negro')
  assert.equal(getSaludEquipo({ estado: 'fuera_de_servicio', incidencias_abiertas: 9 }).clave, 'negro')
})

test('sin datos del equipo se muestra como buen estado', () => {
  assert.equal(getSaludEquipo(null).clave, 'verde')
  assert.equal(getSaludEquipo({}).clave, 'verde')
})
