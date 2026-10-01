import { useState } from 'react'

// Preguntas frecuentes del panel (no del formulario publico del QR, ese es para clientes).
// Pensadas para que alguien que nunca uso el sistema entienda las acciones principales sin
// pedir explicacion previa.
const PREGUNTAS = [
  {
    pregunta: '¿Cómo se registra una incidencia?',
    respuesta:
      'No se crean manualmente desde el panel: cada máquina tiene pegado un código QR. Cuando alguien lo escanea (el cliente, o el mismo personal), se abre un formulario donde elige qué le pasa y se guarda solo, con fecha y hora automáticas. El panel de Incidencias es para revisar y gestionar lo que ya se reportó.',
  },
  {
    pregunta: '¿Cómo busco incidencias anteriores?',
    respuesta:
      'En Incidencias, usa la barra de filtros de arriba: puedes buscar por palabra clave (nombre de la máquina, descripción, quién reportó), por categoría, prioridad, estado, o por fecha (hoy, esta semana, este mes, o un rango). También puedes entrar al detalle de un equipo específico para ver solo su historial.',
  },
  {
    pregunta: '¿Cómo uso los filtros?',
    respuesta:
      'Se combinan entre sí: por ejemplo, categoría "Mecánica" + estado "Pendiente" te muestra solo esas. El buscador de texto funciona en cualquier momento. Para quitar un filtro, vuelve a dejarlo en "Todos" o borra el texto buscado.',
  },
  {
    pregunta: '¿Qué significan los estados y clasificaciones?',
    respuesta:
      'De una incidencia: Pendiente (nadie la ha tomado), En proceso (un técnico ya la está viendo), Resuelta, Descartada. Categoría: qué tipo de falla es (mecánica/eléctrica/otro). Prioridad: qué tan urgente es (baja/media/alta/urgente). De un equipo: Operativo, En mantenimiento, Fuera de servicio, Retirado. Los colores (verde/naranjo/rojo/negro) resumen la salud de la máquina según cuántas incidencias abiertas tiene.',
  },
  {
    pregunta: '¿Cómo modifico información?',
    respuesta:
      'El estado de una incidencia se cambia desde el selector en su misma fila, dentro de la tabla. El estado de un equipo se cambia igual, desde el listado de Equipamiento. Para dejar constancia de una reparación, entra al detalle del equipo y usa "Registrar mantenimiento".',
  },
  {
    pregunta: '¿Cómo marco varias incidencias como arregladas de una vez?',
    respuesta:
      'Entra al detalle del equipo (o usa el atajo "Resolver" desde el listado de Equipamiento) y presiona "Registrar mantenimiento". Ahí aparecen todas sus incidencias abiertas, ya preseleccionadas: solo desmarca las que no correspondan y guarda.',
  },
]

export default function FaqAyuda() {
  const [abierto, setAbierto] = useState(false)
  const [preguntaAbierta, setPreguntaAbierta] = useState(0)

  return (
    <>
      <button
        type="button"
        onClick={() => setAbierto(true)}
        title="Ayuda y preguntas frecuentes"
        aria-label="Ayuda y preguntas frecuentes"
        className="fixed bottom-5 right-5 z-40 w-11 h-11 rounded-full bg-emerald-600 text-white shadow-lg hover:bg-emerald-700 flex items-center justify-center text-lg font-bold"
      >
        ?
      </button>

      {abierto && (
        <div className="fixed inset-0 z-50 flex justify-end">
          <button
            type="button"
            aria-label="Cerrar ayuda"
            onClick={() => setAbierto(false)}
            className="absolute inset-0 bg-slate-900/30"
          />
          <div className="relative w-full max-w-sm h-full bg-white shadow-xl flex flex-col">
            <div className="px-5 py-4 border-b border-slate-200 flex items-center justify-between shrink-0">
              <div>
                <p className="font-semibold text-slate-900">Ayuda</p>
                <p className="text-xs text-slate-400">Preguntas frecuentes del panel</p>
              </div>
              <button
                type="button"
                onClick={() => setAbierto(false)}
                className="text-slate-400 hover:text-slate-600 text-xl leading-none px-1"
                aria-label="Cerrar"
              >
                ×
              </button>
            </div>
            <div className="flex-1 overflow-y-auto px-5 py-3 space-y-2">
              {PREGUNTAS.map((item, indice) => {
                const abiertaEsta = preguntaAbierta === indice
                return (
                  <div key={item.pregunta} className="border border-slate-200 rounded-lg overflow-hidden">
                    <button
                      type="button"
                      onClick={() => setPreguntaAbierta(abiertaEsta ? -1 : indice)}
                      className="w-full text-left px-3 py-2.5 text-sm font-medium text-slate-800 bg-slate-50 hover:bg-slate-100 flex items-center justify-between gap-2"
                    >
                      {item.pregunta}
                      <span className="text-slate-400 shrink-0">{abiertaEsta ? '−' : '+'}</span>
                    </button>
                    {abiertaEsta && (
                      <p className="px-3 py-2.5 text-sm text-slate-600 leading-relaxed">{item.respuesta}</p>
                    )}
                  </div>
                )
              })}
            </div>
          </div>
        </div>
      )}
    </>
  )
}
