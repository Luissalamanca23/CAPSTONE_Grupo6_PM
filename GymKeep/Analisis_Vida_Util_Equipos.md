# Análisis de vida útil e historial de uso — GymKeep

Este documento explica **de dónde salen los números** que carga el script
`postgres/historial_demo.sql`: la vida útil (`vida_util_meses`) de cada máquina, el uso, las fallas
y los costos de mantención de un gimnasio que lleva **2 años y 8 meses abierto**. Los datos
generados son **de demostración** (sintéticos): sirven para que el Panel tenga con qué inferir, no
son registros reales del gimnasio.

## 1. Vida útil de referencia por tipo de equipo

Rangos que publican fabricantes y proveedores de equipamiento comercial para gimnasios con uso
normal a alto:

| Equipo | Rango publicado | Fuente |
|---|---|---|
| Cintas de correr | 7–10 años (7 años si funciona ~16 h/día; 5–8 años en la fuente más conservadora) | [Core Health & Fitness](https://corehandf.com/blog/how-long-does-commercial-gym-equipment-last), [Yanre Fitness](https://yanrefitness.com/?p=177766), [Skelcore](https://skelcore.com/guides/gym-equipment-lifespan-when-repair-upgrade) |
| Elípticas | 7–10 años | Core Health & Fitness, Yanre Fitness |
| Bicicletas estáticas | 7–12 años | Core Health & Fitness, Yanre Fitness |
| Máquinas de placas (selector y poleas) | 10–20 años | Core Health & Fitness (10–15+), Yanre Fitness (15–20) |
| Máquinas de carga de discos | sin cifra propia; "suelen durar más que las de selector" | Skelcore |
| Mancuernas, barras | más de 20 años | Core Health & Fitness, Yanre Fitness |
| Racks de potencia y bancos | más de 20 años | Core Health & Fitness, Yanre Fitness |
| Pesas rusas | más de 10 años | Yanre Fitness |
| Balones medicinales | 5–8 años | Yanre Fitness |
| Bandas de resistencia | 2–5 años (hasta 10 con bandas de calidad y buen cuidado) | Yanre Fitness |

Dos ideas de las mismas fuentes que se usaron como reglas de ajuste:

- **La vida real depende más del uso que de la edad.** Una cinta en un gimnasio muy concurrido
  puede durar cerca de 7 años y, en uno liviano, más de 10 (Core Health & Fitness).
- **Se repara mientras el bastidor esté sano y se reemplaza cuando hay fallas repetidas, repuestos
  difíciles de conseguir o una grieta estructural** (Skelcore). Es el criterio detrás del aviso de
  "3 fallas en 30 días" del Panel.

Limitación: son blogs de proveedores, no fichas técnicas de una marca. Sirven como orden de
magnitud razonable; cuando tengas el manual del fabricante de una máquina concreta, edita su
vida útil con el botón **Editar** y prevalecerá ese dato.

## 2. Vida útil asignada en el sistema

Para cada máquina se parte del valor central del rango y se **reduce un 8 % si trabaja ≥ 3 h
por día y un 15 % si trabaja ≥ 4 h por día** (alta rotación, por lo anterior). Se redondea a
semestres y nunca baja de 24 meses.

| Tipo de máquina | Base (meses) | Años | Con uso intenso (≥ 4 h/día) |
|---|---|---|---|
| Cinta de correr / caminadora | 84 | 7 | 72–78 |
| Elíptica | 96 | 8 | 84–90 |
| Bicicleta (estática, spinning) | 108 | 9 | 90–102 |
| Otro cardio (remo, escaladora, skierg) | 96 | 8 | 84 |
| Placas / guiadas | 180 | 15 | 156 |
| Carga de discos | 216 | 18 | 186 |
| Peso libre (mancuernas, barras, discos) | 240 | 20 | 204 |
| Pesa rusa | 144 | 12 | — |
| Balón medicinal | 72 | 6 | — |
| Bancos y racks | 240 | 20 | 204 |
| Bandas elásticas y cuerdas de batalla | 48 | 4 | — |
| TRX, bosu, foam roller, colchoneta | 60 | 5 | — |
| Cajón pliométrico | 96 | 8 | — |
| Otro accesorio funcional | 72 | 6 | — |

Con 32 meses de funcionamiento, una cinta de 72–78 meses lleva consumido ~42–44 % de su vida
útil, una máquina de placas ~18–21 % y las bandas elásticas ~67 %: es lo esperable (los
accesorios baratos se reponen antes, los equipos de acero duran décadas).

## 3. Modelo de uso (horas por máquina)

El Panel mide el uso como horas en que la máquina estuvo ocupada. El script genera **2 franjas por
día** (mañana y tarde-noche) por máquina desde la apertura. Horas en un día hábil típico
(± 25 % entre máquinas del mismo tipo):

| Máquina | Horas / día hábil |
|---|---|
| Mancuernas (juego completo), banco plano o inclinado | 4,6–5,0 |
| Cinta de correr / caminadora | 4,4 |
| Jaula / rack, prensas, poleas y multiestación | 3,9–4,2 |
| Smith, bicicletas | 3,2–3,6 |
| Elíptica, extensión de cuádriceps, curl femoral, pec deck | 2,8–3,1 |
| Hack, hammer, hip thrust, abductor y aductor | 2,4–2,7 |
| Remo, escaladora, skierg | 1,6 |
| Pesa rusa / mancuerna suelta | 1,2–1,4 |
| Accesorios funcionales | 0,4–0,8 |

Sobre eso se aplican patrones realistas para un gimnasio chileno: más uso lunes y martes
(×1,10) que sábado (×0,55) o domingo (×0,35); más en marzo-abril y septiembre-noviembre
(×1,05–1,12) que en enero-febrero (×0,78–0,80); crecimiento suave desde el 80 % de la demanda
actual en la apertura; feriados (1 ene, 1 may, 18 sep, 25 dic) sin uso; y cero uso mientras una
máquina está en reparación.

Resultado con 75 máquinas de ejemplo: ~140.000 horas de uso; las más demandadas (bancos,
mancuernas, caminadoras, prensas, poleas) promedian 3–4,4 h al día, es decir, entre 1,5 y 2,2 veces
lo que una máquina promedio, y los accesorios funcionales quedan bajo 0,5 h al día.

## 4. Modelo de fallas (incidencias)

Las incidencias son **pocas y no ocurren todos los días**: unas 65 a 75 en 2 años y 8 meses (una
cada dos semanas aproximadamente), creciendo de año en año por el desgaste. Se concentran en las
máquinas con partes móviles y alto uso:

- **Caminadoras, bicicletas y máquinas con polea** (jalón, cruce de poleas, cable crossover,
  remo en polea, multiestación) son las que más fallan: entre 0,9 y 1,7 fallas por año cada
  una. Entre las tres reúnen cerca de dos tercios de todas las incidencias.
- El resto de las máquinas falla muy poco: otro cardio 0,5 al año; placas sin polea 0,18; discos
  0,10; bancos y racks 0,07; peso libre 0,04; accesorios 0,15.
- Cada semana, cada máquina tiene una probabilidad de fallar = `tasa del tipo ÷ 52 × factor de
  edad × factor de uso × fragilidad`. El factor de edad es 0,5 el primer semestre, 0,7 hasta el
  año, 1,0 el segundo año y +35 % por cada año siguiente. El de uso es `(horas por día ÷ 3)^0,7`.
  Un 6 % de las máquinas son "problemáticas" (×1,5) y un 14 % algo más fallosas (×1,2).
- Tipo de falla según el equipo (el "no enciende" solo aplica a cardio); horario punta
  17–21 h (55 %) y 7–10 h (25 %); más reportes los lunes y martes.
- Tiempo de reparación: más largo en cardio y roturas estructurales (piezas por encargo), y
  alrededor de 50 % más rápido hoy que en la apertura.

## 5. Mantenciones y costos (tope de $3 millones)

Todos los montos son estimaciones en **pesos chilenos**, no cotizaciones: ajústalos con los valores
de tu proveedor si los tienes. El **gasto total demo de todo el periodo no supera $2.950.000**
(el script lo verifica y, si el azar lo pasara, reduce proporcionalmente las reparaciones).

**Preventiva: una visita con cuota fija.** El encargado viene cada 60 días, cobra una cuota de
**$50.000** y revisa todas las máquinas en la misma visita. Son ~16 visitas desde la apertura
($800.000 en total). Para que cada máquina tenga su historial, la visita genera una fila por
máquina, pero la cuota se registra **una sola vez por visita** (en una máquina distinta cada
vez); las demás filas de esa visita quedan en $0. Por eso, en el ranking "Máquinas que más
cuestan" no conviene leer el costo preventivo por máquina: es la cuota de la visita completa.

**Correctiva: solo lo que lleva repuesto o técnico cuesta.** Cada incidencia resuelta tiene su
mantención. Si es un ajuste menor (apretar, lubricar, cambiar un grip), lo hace el personal del
gimnasio y queda en $0. Las roturas y los equipos que no encienden suelen requerir repuesto y
técnico:

| Tipo de máquina | Falla | Probabilidad de que cueste | Costo típico (CLP) |
|---|---|---|---|
| Cardio | rota (motor, rodillo, bastidor) | 85 % | 90.000–220.000 |
| Cardio | no enciende (fuente, tarjeta) | 85 % | 70.000–180.000 |
| Cardio | desgaste / ruido | 20–25 % | 25.000–90.000 |
| Placas (poleas, cables) | rota | 80 % | 45.000–110.000 |
| Placas | desgaste / ruido | 10–20 % | 15.000–70.000 |
| Discos | rota | 75 % | 50.000–140.000 |
| Bancos y racks | rota | 70 % | 30.000–90.000 |
| Peso libre y funcional | rota | 30 % | 10.000–40.000 |
| Peso libre y funcional | desgaste / ruido | 0 % (personal propio) | — |

Resultado de ejemplo con 75 máquinas: unas 15 a 25 reparaciones con costo, entre $1,3 y $2,1
millones, más $800.000 de cuotas: **$2,1 a $2,9 millones en total**.

No se incluyen mantenciones mayores anuales ni inspecciones con costo: con una cuota fija que
cubre la revisión de todas las máquinas, agregar precios pequeños por máquina no aportaba.

## 6. Qué puedes inferir en el Panel con estos datos

- **Sección "Demanda de máquinas: qué conviene ampliar"** (nueva): ranking de las máquinas que más
  se ocupan (horas por día y % de ocupación sobre 16 h de apertura), demanda por tipo de máquina y
  una sugerencia de qué sumar si el gimnasio se amplía o se abre otro local, junto con lo que no
  es prioridad. Una máquina tiene demanda alta si se usa 1,5 veces o más el promedio del gimnasio y
  baja si se usa menos de la mitad; por tipo, 1,15 veces o más es alta y 0,6 o menos, baja.
  El cálculo está en `calcularDemanda` (`frontend/src/utils/analitica.js`).
- **Vida útil consumida**: edad frente a `vida_util_meses`.
- **Costos**: gasto bajo y estable (cuota cada dos meses) con picos cuando se rompe algo con repuesto.
- **Máquinas con más fallas y tipos de falla**: caminadoras, bicicletas y poleas encabezan los rankings.
- **Atención recomendada**: 2 reportes sin atender hace días, 1 máquina con 3 fallas en 30 días,
  1 en taller y 1 fuera de servicio.
- **Mapa de calor**: las incidencias se concentran lunes-martes y 17–21 h.

## 7. Cómo ejecutarlo y cómo deshacerlo

Desde la carpeta `GymKeep`, con Docker levantado, en PowerShell:

```powershell
docker compose cp postgres\historial_demo.sql db:/tmp/historial_demo.sql
docker compose exec db psql -U gymkeep -d gymkeep -f /tmp/historial_demo.sql
```

Tarda unos segundos y es seguro repetirlo: borra lo que creó antes (y lo de los scripts antiguos
`datos_demo_dashboard.sql` e `historial_3_anios.sql`), lo regenera con fechas relativas a hoy y no toca
lo que hayas creado a mano. Todo queda marcado con `"demo": "historial3"`. Antes de cambiar las fechas
guarda las originales en la tabla `respaldo_fechas_equipos`. Los ajustes (meses abierto, días entre
visitas, cuota, tope de gasto) están al inicio del archivo y se pueden cambiar. Al final del archivo
hay un bloque **DESHACER**.

Nota de rendimiento: genera ~140.000 filas de uso (el Panel las lee completas para calcular
horómetros). Es fluido en un equipo normal; con uso real de varios años conviene agrupar las
sesiones por día.

## 8. Transparencia

Estos datos **no son reales**. Si el sistema se presenta (por ejemplo, en la defensa del
capstone), conviene decir que el historial es una simulación calibrada con rangos de la industria,
y reemplazarla con datos reales a medida que el sistema se use.
