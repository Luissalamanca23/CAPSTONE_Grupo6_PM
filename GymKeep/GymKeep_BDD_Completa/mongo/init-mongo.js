// ============================================================
// GymKeep - MongoDB
// Eventos de IA, detecciones temporales y telemetría de cámaras
// ============================================================

db = db.getSiblingDB("gymkeep_ai");

// ---- EVENTOS IA CONSOLIDADOS / SEMANTICOS ----
db.createCollection("eventos_ia", {
  validator: {
    $jsonSchema: {
      bsonType: "object",
      required: [
        "event_uuid",
        "timestamp",
        "camara_id",
        "modelo",
        "evento"
      ],
      properties: {
        event_uuid: { bsonType: "string" },
        timestamp: { bsonType: "date" },
        empresa_id: { bsonType: ["long", "int", "null"] },
        sucursal_id: { bsonType: ["long", "int", "null"] },
        zona_id: { bsonType: ["long", "int", "null"] },
        camara_id: { bsonType: ["long", "int"] },
        equipo_id: { bsonType: ["long", "int", "null"] },
        sesion_uso_id: { bsonType: ["long", "int", "null"] },
        modelo: {
          bsonType: "object",
          required: ["nombre", "version"],
          properties: {
            id: { bsonType: ["long", "int", "null"] },
            nombre: { bsonType: "string" },
            version: { bsonType: "string" }
          }
        },
        evento: {
          bsonType: "object",
          required: ["tipo"],
          properties: {
            tipo: {
              enum: [
                "persona_detectada",
                "inicio_uso",
                "fin_uso",
                "uso_en_curso",
                "anomalia",
                "posible_falla",
                "ocupacion_zona"
              ]
            },
            confidence: { bsonType: ["double", "int", "long", "decimal", "null"] }
          }
        },
        detecciones: { bsonType: ["array", "null"] },
        tracking: { bsonType: ["object", "null"] },
        evidencia: {
          bsonType: ["object", "null"],
          properties: {
            snapshot_url: { bsonType: ["string", "null"] },
            clip_url: { bsonType: ["string", "null"] }
          }
        },
        metadata: { bsonType: ["object", "null"] }
      }
    }
  }
});

db.eventos_ia.createIndex({ event_uuid: 1 }, { unique: true });
db.eventos_ia.createIndex({ camara_id: 1, timestamp: -1 });
db.eventos_ia.createIndex({ equipo_id: 1, timestamp: -1 });
db.eventos_ia.createIndex({ "evento.tipo": 1, timestamp: -1 });
db.eventos_ia.createIndex({ sesion_uso_id: 1, timestamp: 1 });

// ---- DETECCIONES CRUDAS / TEMPORALES ----
// TTL: se eliminan automáticamente 7 días después.
// Sirve para depuración y calibración; no es la fuente de verdad del negocio.
db.createCollection("detecciones_raw", {
  validator: {
    $jsonSchema: {
      bsonType: "object",
      required: ["timestamp", "camara_id", "modelo", "detecciones"],
      properties: {
        timestamp: { bsonType: "date" },
        camara_id: { bsonType: ["long", "int"] },
        frame_id: { bsonType: ["long", "int", "null"] },
        modelo: { bsonType: "object" },
        detecciones: { bsonType: "array" },
        procesado: { bsonType: ["bool", "null"] },
        metadata: { bsonType: ["object", "null"] }
      }
    }
  }
});

db.detecciones_raw.createIndex({ timestamp: 1 }, { expireAfterSeconds: 604800 });
db.detecciones_raw.createIndex({ camara_id: 1, timestamp: -1 });

// ---- TELEMETRIA DE CAMARAS ----
// TTL: 30 días.
db.createCollection("telemetria_camaras", {
  validator: {
    $jsonSchema: {
      bsonType: "object",
      required: ["timestamp", "camara_id", "estado"],
      properties: {
        timestamp: { bsonType: "date" },
        camara_id: { bsonType: ["long", "int"] },
        estado: { bsonType: "string" },
        fps_real: { bsonType: ["double", "int", "null"] },
        latencia_ms: { bsonType: ["double", "int", "null"] },
        frames_perdidos: { bsonType: ["long", "int", "null"] },
        cpu_pct: { bsonType: ["double", "int", "null"] },
        gpu_pct: { bsonType: ["double", "int", "null"] },
        temperatura_c: { bsonType: ["double", "int", "null"] },
        metadata: { bsonType: ["object", "null"] }
      }
    }
  }
});

db.telemetria_camaras.createIndex({ timestamp: 1 }, { expireAfterSeconds: 2592000 });
db.telemetria_camaras.createIndex({ camara_id: 1, timestamp: -1 });
