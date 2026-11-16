// RUN chileno: formato, digito verificador (modulo 11) y forma canonica que usa la API.

/** Deja solo digitos y K (mayuscula). */
export function limpiarRun(texto) {
  return (texto || '').replace(/[^0-9kK]/g, '').toUpperCase()
}

export function digitoVerificador(cuerpo) {
  let suma = 0
  let factor = 2
  for (let i = cuerpo.length - 1; i >= 0; i--) {
    suma += Number(cuerpo[i]) * factor
    factor = factor === 7 ? 2 : factor + 1
  }
  const resto = 11 - (suma % 11)
  if (resto === 11) return '0'
  if (resto === 10) return 'K'
  return String(resto)
}

/** Da formato mientras se escribe: 12345678K -> 12.345.678-K. */
export function formatearRun(texto) {
  const limpio = limpiarRun(texto).slice(0, 9)
  if (limpio.length <= 1) return limpio
  const cuerpo = limpio.slice(0, -1).replace(/\D/g, '')
  const dv = limpio.slice(-1)
  return `${cuerpo.replace(/\B(?=(\d{3})+(?!\d))/g, '.')}-${dv}`
}

/** True si tiene 7 u 8 digitos mas un digito verificador correcto. */
export function runValido(texto) {
  const limpio = limpiarRun(texto)
  if (!/^\d{7,8}[0-9K]$/.test(limpio)) return false
  return digitoVerificador(limpio.slice(0, -1)) === limpio.slice(-1)
}

/** Forma que guarda la API: 12345678-5 (o null si no es un RUN valido). */
export function runCanonico(texto) {
  if (!runValido(texto)) return null
  const limpio = limpiarRun(texto)
  return `${limpio.slice(0, -1)}-${limpio.slice(-1)}`
}
