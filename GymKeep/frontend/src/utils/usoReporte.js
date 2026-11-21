// Pregunta 3 del formulario publico del QR: "¿Se puede seguir usando la maquina?".
// Una sola respuesta reemplaza a las antiguas "que tan grave es" y "todavia se puede usar", que se
// pisaban entre si (por ejemplo "leve" junto con "esta detenida"). La API sigue recibiendo
// `gravedad` y `funcional`; cada opcion fija los dos y de ahi sale la prioridad de la incidencia
// (ver crud.incidencia.create_incidencia_por_qr):
//   funciona -> baja, riesgo -> alta, detenida -> urgente.

export const OPCIONES_USO = [
  {
    valor: 'funciona',
    etiqueta: 'Sí, funciona',
    ayuda: 'La falla es leve; se puede seguir usando con cuidado',
    gravedad: 'leve',
    funcional: true,
  },
  {
    valor: 'riesgo',
    etiqueta: 'Funciona, pero es riesgosa',
    ayuda: 'Está muy dañada o puede lastimar a alguien',
    gravedad: 'grave',
    funcional: true,
  },
  {
    valor: 'detenida',
    etiqueta: 'No, está detenida',
    ayuda: 'No se puede usar',
    // Con funcional=false la API ignora la gravedad y deja la incidencia como urgente.
    gravedad: 'grave',
    funcional: false,
  },
]

/** Campos que espera la API ({ gravedad, funcional }) para la opcion elegida, o null si no existe. */
export function datosDeUso(valor) {
  const opcion = OPCIONES_USO.find((o) => o.valor === valor)
  return opcion ? { gravedad: opcion.gravedad, funcional: opcion.funcional } : null
}
