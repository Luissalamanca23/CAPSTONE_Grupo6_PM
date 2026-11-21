# GymKeep

**Gestión inteligente del mantenimiento de equipamiento en gimnasios.**

Proyecto APT (Capstone PTY4614) · Ingeniería en Informática · Duoc UC, sede Puerto Montt · Grupo 6

## Equipo

| Integrante | Cargo |
|---|---|
| Braihan González | Equipo de desarrollo |
| Luis Salamanca | Equipo de desarrollo |
| Benjamin Oviedo | Equipo de desarrollo |

El trabajo es colaborativo: los tres integrantes participan en todas las actividades (diseño de
la base de datos, backend y frontend, módulo de visión por computadora y pruebas de calidad) y
desarrollan las mismas competencias del perfil de egreso.

## Problema

Los gimnasios sufren interrupciones constantes por máquinas fuera de servicio:

- Las fallas se reportan de forma verbal o informal, así que la información llega tarde o se pierde.
- El mantenimiento es reactivo: se actúa cuando la máquina ya se rompió.
- La administración no tiene datos de uso real ni del costo acumulado de cada equipo.

Afecta a los socios, al personal técnico y de aseo, y a la administración.

## Solución

GymKeep integra tres componentes:

1. **Reporte por QR:** cada máquina tiene un código QR. Al escanearlo, cualquier persona reporta
   una falla desde el navegador del celular, sin instalar una aplicación ni crear una cuenta.
2. **Visión por computadora:** analiza el video de las cámaras para medir el tiempo de uso real
   de cada máquina.
3. **Panel web de gestión:** ordena las incidencias por prioridad y reúne el historial, los costos
   y los indicadores de cada equipo.

El objetivo es pasar de un mantenimiento a ciegas a uno preventivo basado en el uso real.

## Objetivos

**General:** desarrollar un sistema web y móvil que automatice el reporte de fallas por QR, mida
el uso de las máquinas con visión por computadora y optimice la gestión del mantenimiento.

**Específicos:**

1. Diseñar la base de datos para activos, usuarios, fallas y registros de uso.
2. Desarrollar el portal de reporte por QR y el panel de gestión de órdenes de trabajo.
3. Implementar el módulo de visión por computadora que mide el tiempo de uso.
4. Construir un panel analítico de costos, fallas y estado del equipamiento.
5. Ejecutar pruebas de calidad de software.

## Metodología

Scrum, con nueve sprints entre el 17 de agosto y el 30 de noviembre de 2026 (seis de dos semanas y tres de una semana), precedidos de una semana de análisis. Las tres fases de la asignatura:

| Fase | Fechas (2026) | Contenido |
|---|---|---|
| 1. Definición | 10 al 28 de agosto | Problema, requisitos, alcance y planificación |
| 2. Desarrollo | 31 de agosto al 20 de noviembre | Base de datos, API, reporte QR, visión por computadora y panel |
| 3. Certificación y cierre | 23 al 30 de noviembre | Pruebas de calidad, documentación y presentación final |

## Estado

| Componente | Estado |
|---|---|
| Base de datos (PostgreSQL, MongoDB; MinIO opcional) | Implementado |
| API backend | Implementado |
| Reporte por QR | Implementado |
| Panel web de gestión | Implementado (con avisos de incidencias, informes de funcionamiento y respaldo automático) |
| Módulo de visión por computadora | Implementado y validado con video grabado (perfil `rpi` para Raspberry Pi 5) |
| Panel de costos (TCO) y autenticación (RUN y clave, roles administrador y técnico) | Implementado |

## Tecnologías

Python, FastAPI, PostgreSQL, MongoDB, MinIO · React, Vite, Tailwind · YOLO, OpenCV · Docker · pytest

## Estructura del repositorio

```text
Fase 1/     Documentos de la fase de definición
GymKeep/    Código del sistema: backend (app/), panel web (frontend/), base de datos y pruebas
GymKeep/raspberry-pi/  Instalación y configuración en una Raspberry Pi 5 (8 GB)
```

Para instalar y ejecutar el sistema, ver [`GymKeep/README.md`](GymKeep/README.md) y
[`GymKeep/CONTRIBUTING.md`](GymKeep/CONTRIBUTING.md).

---

Proyecto académico. No tiene licencia de uso: todos los derechos reservados por sus autores.
