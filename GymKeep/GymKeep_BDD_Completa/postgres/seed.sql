-- Datos de demostración opcionales.
-- Ejecutar DESPUÉS de schema.sql.

INSERT INTO empresas (rut, razon_social, nombre_fantasia, email_contacto)
VALUES ('76.000.000-0', 'GymKeep Demo SpA', 'GymKeep Demo', 'demo@gymkeep.local')
ON CONFLICT DO NOTHING;

INSERT INTO sucursales (empresa_id, codigo, nombre, direccion, ciudad, region)
SELECT id, 'PM-01', 'Sucursal Puerto Montt', 'Dirección de ejemplo 123', 'Puerto Montt', 'Los Lagos'
FROM empresas
WHERE nombre_fantasia = 'GymKeep Demo'
ON CONFLICT (empresa_id, codigo) DO NOTHING;

INSERT INTO zonas (sucursal_id, nombre, descripcion)
SELECT id, 'Cardio', 'Zona de máquinas cardiovasculares'
FROM sucursales
WHERE codigo = 'PM-01'
ON CONFLICT (sucursal_id, nombre) DO NOTHING;

INSERT INTO equipos (sucursal_id, zona_id, codigo_activo, nombre, categoria, marca, modelo)
SELECT s.id, z.id, 'EQ-0001', 'Cinta de correr 01', 'cardio', 'DemoFit', 'Run-X'
FROM sucursales s
JOIN zonas z ON z.sucursal_id = s.id AND z.nombre = 'Cardio'
WHERE s.codigo = 'PM-01'
ON CONFLICT (sucursal_id, codigo_activo) DO NOTHING;

INSERT INTO qr_equipos (equipo_id)
SELECT e.id
FROM equipos e
WHERE e.codigo_activo = 'EQ-0001'
AND NOT EXISTS (
    SELECT 1 FROM qr_equipos q WHERE q.equipo_id = e.id AND q.activo = TRUE
);

INSERT INTO camaras (
    sucursal_id, zona_id, codigo, nombre, fabricante, modelo, ip, fps_configurado, ancho_px, alto_px
)
SELECT s.id, z.id, 'CAM-01', 'Cámara Cardio 01', 'Basler', 'a2A1920', '192.168.10.20', 30, 1920, 1080
FROM sucursales s
JOIN zonas z ON z.sucursal_id = s.id AND z.nombre = 'Cardio'
WHERE s.codigo = 'PM-01'
ON CONFLICT (sucursal_id, codigo) DO NOTHING;

INSERT INTO camara_equipos (camara_id, equipo_id, roi)
SELECT c.id, e.id, '{"x":300,"y":150,"w":900,"h":800}'::jsonb
FROM camaras c
JOIN equipos e ON e.sucursal_id = c.sucursal_id
WHERE c.codigo = 'CAM-01' AND e.codigo_activo = 'EQ-0001'
ON CONFLICT (camara_id, equipo_id) DO NOTHING;

INSERT INTO modelos_ia (nombre, version, framework, tipo_modelo, clases, metricas, activo)
VALUES (
    'gymkeep-usage-detector',
    '1.0.0',
    'YOLO/OpenCV',
    'deteccion_tracking',
    '["persona","equipo"]'::jsonb,
    '{"precision":0.92,"recall":0.89}'::jsonb,
    TRUE
)
ON CONFLICT (nombre, version) DO NOTHING;
