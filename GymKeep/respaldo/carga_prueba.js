// Datos de prueba en MongoDB para la prueba de restauracion grande (RNF-21): 200.000 detecciones
// crudas marcadas con metadata.prueba_carga. carga_prueba_limpiar.js las borra.
// Lo corre prueba-restauracion-grande.bat (mongosh ... --file).
const total = 200000;
const lote = 10000;
const ahora = Date.now();
for (let i = 0; i < total; i += lote) {
  const docs = [];
  for (let j = 0; j < lote; j++) {
    docs.push({
      timestamp: new Date(ahora - (i + j) * 1000),
      camara_id: NumberInt(1),
      frame_id: NumberInt(i + j),
      modelo: { nombre: "prueba", version: "0" },
      detecciones: [{ clase: "persona", confianza: 0.9, bbox: [10, 20, 30, 40] }],
      procesado: true,
      metadata: { prueba_carga: true },
    });
  }
  db.detecciones_raw.insertMany(docs);
}
print("detecciones_raw: " + db.detecciones_raw.countDocuments({ "metadata.prueba_carga": true }) + " documentos de prueba");
