// Achica una foto del celular antes de subirla: las fotos de camara pesan varios MB y el
// formulario publico se usa con datos moviles. Devuelve una cadena base64 (sin prefijo) de
// un JPEG de a lo mas `maxLado` px por lado.
export async function reducirFoto(archivo, maxLado = 1280, calidad = 0.8) {
  if (!archivo || !archivo.type.startsWith('image/')) {
    throw new Error('Elige un archivo de imagen.')
  }
  let bitmap
  try {
    bitmap = await createImageBitmap(archivo, { imageOrientation: 'from-image' })
  } catch {
    throw new Error('No se pudo leer esa foto. Prueba con otra (JPG o PNG).')
  }
  const escala = Math.min(1, maxLado / Math.max(bitmap.width, bitmap.height))
  const canvas = document.createElement('canvas')
  canvas.width = Math.max(1, Math.round(bitmap.width * escala))
  canvas.height = Math.max(1, Math.round(bitmap.height * escala))
  canvas.getContext('2d').drawImage(bitmap, 0, 0, canvas.width, canvas.height)
  bitmap.close?.()
  const dataUrl = canvas.toDataURL('image/jpeg', calidad)
  return { base64: dataUrl.split(',')[1], vistaPrevia: dataUrl }
}
