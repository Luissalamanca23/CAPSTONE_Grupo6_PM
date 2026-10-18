// Vacia los DATOS de MongoDB (eventos IA, telemetria, estado en vivo, fotos).
// Conserva las colecciones, validadores e indices.
// Ejecutar:
//   Get-Content mongo\limpiar_datos_pruebas.js -Raw | docker compose exec -T mongo mongosh -u gymkeep -p gymkeep_mongo_password --authenticationDatabase admin gymkeep_ai
const colecciones = ["eventos_ia", "detecciones_raw", "telemetria_camaras", "camaras_vivo", "fotos_equipos"];
colecciones.forEach((c) => {
  const r = db.getCollection(c).deleteMany({});
  print(c + ": " + r.deletedCount + " documentos borrados");
});
