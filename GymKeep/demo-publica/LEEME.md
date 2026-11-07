# Demo publica de GymKeep (QR desde cualquier celular)

Levanta GymKeep en este PC (base de datos incluida) y lo publica en internet con Tailscale
Funnel, para escanear el QR desde cualquier celular y ver el reporte en la web.

## Una sola vez
1. Instalar **Docker Desktop** y dejarlo abierto.
2. Instalar **Tailscale** (https://tailscale.com/download) e iniciar sesion.
3. En https://login.tailscale.com/admin/dns activar **MagicDNS** y **Enable HTTPS**.

## Cada vez
Doble clic en `iniciar-demo.bat`. Al terminar muestra la direccion publica
(`https://<este-pc>.<red>.ts.net`). La primera vez tarda varios minutos (descarga y compila) y
Tailscale puede mostrar un enlace para habilitar Funnel: abrirlo y aceptar.

- Web: la direccion publica. QR: en la web, Equipos > Ver detalle (o
  `<direccion>/api/v1/equipamiento/<id>/codigo-qr`). Los QR llevan la direccion publica.
- **Simulacion de uso real**: en cada arranque se BORRAN todas las sesiones de uso de la base y se
  generan sesiones nuevas hasta el momento actual (horario de gimnasio real, punta de manana y
  tarde-noche, mas gente lunes-martes, ~158.000 sesiones en 2 anos) junto con problemas recientes:
  una cinta fuera de servicio, una bicicleta en reparacion, cables y tapices gastados y algunas
  fallas ya resueltas. Ver `simular-uso-real.sql`.
- **Datos de ejemplo**: se cargan una sola vez, en este orden (importa: `historial_demo.sql` borra lo
  que genera `datos_demo_dashboard.sql`): reset_demo_incidencias, agregar_mas_datos,
  reclasificar_categorias, historial_demo, `ajustar-datos-demo.sql` (reparte fechas y horas de
  los reportes y cierra los antiguos, para que el Panel no muestre picos ni variaciones absurdas) y
  datos_demo_dashboard.
- `iniciar-demo.bat -SinDatosDemo` arranca sin los datos de ejemplo (solo `seed.sql`).
- `iniciar-demo.bat -SinSimulacion` no regenera las sesiones ni los problemas.
- `detener-demo.bat` quita la publicacion y apaga todo (`-BorrarDatos` borra tambien la base).

La web y la API quedan accesibles desde internet mientras la demo este publicada: apagarla al
terminar. No incluye el modulo de vision (camaras).

## Demo con tus datos reales y camaras
1. **Una sola vez:** `copiar-datos-reales.bat`. Lee la base real (volumenes `gymkeep_*`), deja un
   respaldo en `GymKeep\respaldos\` (no se sube a git) y lo carga en los volumenes de la demo
   (`gymkeep-demo_*`). Los datos originales no se tocan. Al terminar crea `.datos-reales`: mientras
   exista, la demo NO carga datos de ejemplo ni simula uso (eso borraria sesiones reales).
2. Copia tu video a `GymKeep\vision\datos\` (mp4, mov, avi, mkv). No se sube a git.
3. `iniciar-demo-real.bat`: levanta todo con camaras, pregunta que video usar (o
   `iniciar-demo-real.bat -Video mi_video.mp4 -Camara CAM-01`) y publica. El video se analiza en
   bucle como si fuera una camara en vivo: **<direccion>/camaras**. Dibuja las zonas de las
   maquinas en el panel (Camaras > tu camara > Dibujar zona); al ejecutar el script muestra un
   **PIN** que el panel pide para editar zonas.
4. Para cambiar de video: copia el nuevo y vuelve a ejecutar `iniciar-demo-real.bat`.
5. Volver a la demo de ejemplo: `detener-demo.bat -BorrarDatos` y luego `iniciar-demo.bat`.
   Volver a trabajar en local con los datos reales: `..\volver-a-datos-reales.bat`.

Con datos reales publicados, cualquiera con el enlace puede verlos y editarlos: apagar al terminar.
