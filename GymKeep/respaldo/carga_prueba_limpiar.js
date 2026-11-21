// Borra los documentos que creo carga_prueba.js (solo los marcados con metadata.prueba_carga).
const r = db.detecciones_raw.deleteMany({ "metadata.prueba_carga": true });
print("detecciones_raw: " + r.deletedCount + " documentos de prueba borrados");
