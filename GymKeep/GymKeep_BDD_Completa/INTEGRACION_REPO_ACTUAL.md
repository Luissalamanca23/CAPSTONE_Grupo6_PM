# Integración con el repositorio actual

El proyecto actual tiene `codigo_qr` directamente dentro de `equipos` y las
incidencias utilizan un enum fijo de tipo de falla.

El modelo ampliado cambia ambas decisiones:

```text
ANTES
Equipo.codigo_qr
Incidencia.tipo_falla (enum)

DESPUÉS
Equipo -> QrEquipo
Incidencia -> TipoFalla (tabla catálogo)
```

Por eso **no se deben copiar solamente los modelos y ejecutar el backend actual**
sin adaptar CRUD/schemas/endpoints.

## Estrategia recomendada para el Capstone

Como el proyecto todavía está en fase de desarrollo, la opción más limpia es:

```bash
docker compose down -v
```

Luego utilizar el nuevo esquema desde cero.

Esto evita arrastrar una estructura que todavía era prototipo.

## Cambios que debe hacer la API

### Crear equipo

Antes:

```json
{
  "codigo_qr": "QR-001",
  "nombre": "Elíptica"
}
```

Nuevo enfoque:

```json
{
  "sucursal_id": 1,
  "zona_id": 1,
  "codigo_activo": "EQ-001",
  "nombre": "Elíptica",
  "marca": "Technogym",
  "modelo": "Synchro"
}
```

Al crear el equipo, el backend crea automáticamente un registro en `qr_equipos`
con un UUID seguro.

### Buscar equipo por QR

Antes:

```sql
SELECT * FROM equipos WHERE codigo_qr = :codigo;
```

Ahora:

```sql
SELECT e.*
FROM equipos e
JOIN qr_equipos q ON q.equipo_id = e.id
WHERE q.token = :token
  AND q.activo = TRUE
  AND (q.fecha_expiracion IS NULL OR q.fecha_expiracion > NOW());
```

### Reportar una falla por QR

El frontend envía:

```json
{
  "codigo_qr": "UUID-DEL-QR",
  "tipo_falla_codigo": "SONIDO_EXTRANO",
  "reportado_por": "Juan"
}
```

El backend:

1. resuelve el QR activo;
2. obtiene el equipo;
3. busca el catálogo `tipos_falla`;
4. toma `prioridad_base`;
5. crea `incidencias` con `origen = "qr"`.

### Registrar uso por IA

La cámara/modelo **no crea una sesión por frame**.

Debe producir eventos:

```text
inicio_uso
uso_en_curso
fin_uso
```

Al recibir `inicio_uso`:

- documento completo -> MongoDB;
- resumen -> `eventos_ia_resumen`;
- crear `sesiones_uso` estado `abierta`.

Al recibir `fin_uso`:

- documento completo -> MongoDB;
- resumen -> `eventos_ia_resumen`;
- cerrar `sesiones_uso`;
- calcular `duracion_segundos`.

## Orden recomendado de implementación

1. Infraestructura PostgreSQL/MongoDB/MinIO.
2. Empresa.
3. Sucursal.
4. Zona.
5. Equipo.
6. QR.
7. Catálogo de fallas.
8. Incidencias.
9. Cámara.
10. Asociación cámara-equipo + ROI.
11. Modelo IA/versiones.
12. Eventos IA MongoDB.
13. Sesiones de uso.
14. Mantenimiento.
15. Auditoría.
16. Dashboards y métricas.
