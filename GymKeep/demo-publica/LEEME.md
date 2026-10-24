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
