"""Etapas 1 a 3 de §6.6.1: deteccion -> seguimiento -> eventos de uso.

Por cada cuadro analizado:
  1. YOLO detecta personas y ByteTrack les asigna un ID que se mantiene entre cuadros.
  2. Cada persona se asigna (o no) a la ROI de una maquina (`zonas.asignar`).
  3. Cada maquina actualiza su maquina de estados (`sesiones.MonitorMaquina`), que emite
     `inicio_uso` / `uso_en_curso` / `fin_uso` cuando corresponde.
Los eventos se escriben en `eventos.jsonl` y, si hay API, se envian a GymKeep.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
import time
from collections import deque
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta
from pathlib import Path

import cv2
import numpy as np

from gymkeep_vision import rostros, tiempo
from gymkeep_vision.actividad import MedidorActividad
from gymkeep_vision.captura import LectorVivo
from gymkeep_vision.config import Config, ConfigMaquina
from gymkeep_vision.eventos import construir_evento
from gymkeep_vision.registro import RegistroPresencia
from gymkeep_vision.sesiones import Estado, MonitorMaquina, Observacion
from gymkeep_vision.zonas import Deteccion, ZonaMaquina, asignar

log = logging.getLogger(__name__)

# En una camara en vivo (24/7) `Resultado.eventos` guarda solo los ultimos eventos: el
# historial completo esta en eventos.jsonl y en la API.
MAX_EVENTOS_VIVO = 1000

# Colores BGR por estado de la maquina.
COLORES = {
    Estado.LIBRE: (120, 170, 60),
    Estado.CANDIDATA: (40, 190, 240),
    Estado.EN_USO: (60, 60, 230),
    Estado.PAUSA: (40, 140, 250),
    Estado.OCUPADA: (170, 120, 150),
}
ETIQUETAS = {
    Estado.LIBRE: "LIBRE",
    Estado.CANDIDATA: "DETECTANDO",
    Estado.EN_USO: "EN USO",
    Estado.PAUSA: "PAUSA",
    Estado.OCUPADA: "OCUPADA SIN USO",
}


def mmss(segundos: float) -> str:
    segundos = int(round(segundos))
    h, resto = divmod(segundos, 3600)
    m, s = divmod(resto, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


@dataclass
class Resultado:
    config: Config
    fuente: str
    inicio_video: datetime
    monitores: dict[str, MonitorMaquina]
    eventos: list[dict] | deque = field(default_factory=list)
    t_inicio_s: float = 0.0
    t_final_s: float = 0.0
    cuadros_analizados: int = 0
    segundos_computo: float = 0.0
    video_salida: Path | None = None
    interrumpido: bool = False
    origen_inicio: str = ""


class Pipeline:
    def __init__(
        self,
        cfg: Config,
        fuente: str,
        salida: Path,
        *,
        destinos: list,
        inicio_video: datetime,
        guardar_video: bool = True,
        mostrar: bool = False,
        desde_s: float = 0.0,
        max_segundos: float | None = None,
        publicador=None,
        tiempo_real: bool = False,
        repetir: bool = False,
    ):
        self.cfg = cfg
        # Actividad por pose (actividad.py): solo si la config la pide.
        self.medidor = MedidorActividad(cfg.actividad) if cfg.actividad else None
        self._activa: dict = {}
        # Conexion en vivo con la plataforma (vivo.PublicadorVivo), opcional.
        self.publicador = publicador
        # Rostros que YOLO no detecta como persona (muy cerca o cortados por el borde).
        self.detector_rostros = rostros.crear() if cfg.difuminar_personas else None
        # Un archivo se analiza al ritmo del reloj (como una camara en vivo) y, con repetir,
        # vuelve a empezar al terminar: sirve para mostrar la integracion sin camara real.
        self.tiempo_real = tiempo_real
        self.repetir = repetir
        self.fuente = fuente
        self.salida = salida
        self.destinos = destinos
        self.inicio_video = inicio_video
        self.guardar_video = guardar_video
        self.mostrar = mostrar
        self.desde_s = desde_s
        self.max_segundos = max_segundos

        self.maquinas: dict[str, ConfigMaquina] = {m.nombre: m for m in cfg.maquinas}
        self.zonas = [
            ZonaMaquina(
                m.nombre, m.roi, criterio=m.criterio or cfg.criterio_zona, solape_min=cfg.solape_min
            )
            for m in cfg.maquinas
        ]
        self.monitores = {m.nombre: MonitorMaquina(cfg.uso) for m in cfg.maquinas}
        self._sin_senal = False  # camara en vivo: ya se cerraron las sesiones por falta de cuadros

    # ------------------------------------------------------------------ ejecucion

    def ejecutar(self) -> Resultado:
        from ultralytics import YOLO  # import tardio: los tests no necesitan torch

        es_archivo = Path(self.fuente).exists()

        def abrir() -> cv2.VideoCapture:
            return cv2.VideoCapture(int(self.fuente) if self.fuente.isdigit() else self.fuente)

        captura = abrir()
        if not captura.isOpened():
            raise RuntimeError(f"No se pudo abrir la fuente de video: {self.fuente}")

        fps = captura.get(cv2.CAP_PROP_FPS) or 25.0
        ancho = int(captura.get(cv2.CAP_PROP_FRAME_WIDTH))
        alto = int(captura.get(cv2.CAP_PROP_FRAME_HEIGHT))
        self._ancho, self._alto = ancho, alto
        self._preparar_zonas(ancho, alto)
        # Las camaras CCTV chicas (ej. 352x240) se dibujan ampliadas para que se lean las etiquetas.
        self._f = max(1.0, 960 / ancho)
        self._tam_dibujo = (round(ancho * self._f), round(alto * self._f))

        # Segundos reales por segundo de video: 1.0 salvo que el grabador haya exportado a
        # otra tasa (ver escala_tiempo en config.py). Todo `t` de aqui en adelante es tiempo real.
        escala = self.cfg.escala_tiempo
        salto = max(1, round(fps / escala * self.cfg.intervalo_analisis_s)) if es_archivo else 1
        indice = 0
        if es_archivo and self.desde_s > 0:
            indice = int(self.desde_s * fps)
            captura.set(cv2.CAP_PROP_POS_FRAMES, indice)

        modelo = YOLO(self.cfg.modelo.ruta_pesos())
        self.salida.mkdir(parents=True, exist_ok=True)
        (self.salida / "evidencias").mkdir(exist_ok=True)
        resultado = Resultado(self.cfg, self.fuente, self.inicio_video, self.monitores)
        resultado.t_inicio_s = self.desde_s * escala if es_archivo else 0.0
        # Una camara no termina: si deja de entregar cuadros se reabre la conexion en vez de salir.
        lector = None if es_archivo else LectorVivo(abrir, captura)
        if not es_archivo:
            resultado.eventos = deque(maxlen=MAX_EVENTOS_VIVO)

        # Reloj del video anotado: cada cuadro escrito representa `periodo` segundos reales,
        # asi la hora impresa avanza al ritmo real al reproducirlo (aunque el archivo venga
        # acelerado o, en vivo, el analisis se atrase).
        periodo = (
            tiempo.periodo_salida(fps, salto, escala) if es_archivo else self.cfg.intervalo_analisis_s
        )
        cuadros_archivo = int(captura.get(cv2.CAP_PROP_FRAME_COUNT)) if es_archivo else 0
        self._en_vivo = not es_archivo
        self._duracion_s = cuadros_archivo / fps * escala if cuadros_archivo > 0 else None
        escritos = 0

        escritor = None
        ruta_video_tmp = self.salida / "video_anotado_tmp.mp4"
        if self.guardar_video:
            escritor = cv2.VideoWriter(
                str(ruta_video_tmp), cv2.VideoWriter_fourcc(*"mp4v"), 1 / periodo, self._tam_dibujo
            )

        # En vivo, presencia.csv rota por dia y tamano para no crecer sin tope.
        presencia = RegistroPresencia(self.salida / "presencia.csv", rotar=not es_archivo)

        t0_reloj = time.monotonic()
        t_ultimo_vivo = -1e9
        t = resultado.t_inicio_s
        inicio_pasada = indice
        self._desfase = 0.0  # segundos reales de las pasadas anteriores (--repetir)
        try:
            while True:
                if es_archivo and (indice - inicio_pasada) % salto:
                    if captura.grab():
                        indice += 1
                        continue
                    ok = False
                else:
                    ok, cuadro = captura.read() if es_archivo else lector.leer()
                if not ok and not es_archivo:
                    # Sin cuadros: no se inventa presencia ni ausencia; solo si el corte dura
                    # mas de t_off_s se cierran las sesiones (motivo 'sin_senal').
                    t = time.monotonic() - t0_reloj
                    self._vigilar_senal(lector, t, resultado)
                    if self.max_segundos is not None and t > self.max_segundos:
                        break
                    time.sleep(0.1)
                    continue
                if ok:
                    self._sin_senal = False
                if not ok:
                    if self.repetir and es_archivo and resultado.cuadros_analizados:
                        captura.set(cv2.CAP_PROP_POS_FRAMES, 0)
                        self._desfase = t + periodo
                        indice = inicio_pasada = 0
                        log.info("Fin del video: vuelve a empezar (--repetir)")
                        continue
                    break
                indice += 1

                if es_archivo:
                    t = self._desfase + (indice - 1) / fps * escala
                else:
                    t = time.monotonic() - t0_reloj
                    if t - t_ultimo_vivo < self.cfg.intervalo_analisis_s:
                        continue
                    t_ultimo_vivo = t
                if self.max_segundos is not None and (t - resultado.t_inicio_s) / escala > self.max_segundos:
                    break

                inicio_computo = time.perf_counter()
                detecciones = self._detectar(modelo, cuadro)
                activa = self._activa = self.medidor.actualizar(t, detecciones) if self.medidor else {}
                # Se asignan todas las detecciones y despues se filtra por confianza_min: asi
                # presencia.csv guarda la confianza aunque no llegue al umbral, y el comando
                # `recalibrar` puede probar otros umbrales sin volver a correr YOLO.
                todas = asignar(detecciones, self.zonas)
                asignadas = {
                    nombre: [d for d in dets if d.confianza >= self.cfg.confianza_min]
                    for nombre, dets in todas.items()
                }
                latencia = time.perf_counter() - inicio_computo
                resultado.segundos_computo += latencia
                resultado.cuadros_analizados += 1

                pendientes = []
                for zona in self.zonas:
                    dets = asignadas[zona.nombre]
                    obs = Observacion(
                        t=t,
                        personas=len(dets),
                        confianza=max((d.confianza for d in dets), default=None),
                        track_ids=tuple(d.track_id for d in dets if d.track_id is not None),
                        activas=self._contar_activas(dets, activa),
                    )
                    monitor = self.monitores[zona.nombre]
                    pendientes += [(ev, zona.nombre, dets) for ev in monitor.actualizar(obs)]
                    presencia.escribir(
                        [
                            f"{t:.2f}",
                            self._timestamp(t),
                            zona.nombre,
                            obs.personas,
                            f"{max(d.confianza for d in todas[zona.nombre]):.3f}" if todas[zona.nombre] else "",
                            monitor.estado.value,
                        ]
                    )
                # Dibujar y buscar rostros cuesta: solo se hace si alguien lo va a usar (video,
                # ventana, evidencia de un inicio_uso o cuadro para el panel). Se dibuja
                # despues de actualizar, para que la evidencia ya muestre la maquina EN USO.
                para_panel = self.publicador is not None and self.publicador.necesita_cuadro()
                dibujar = escritor is not None or self.mostrar or any(ev.tipo == "inicio_uso" for ev, _, _ in pendientes)
                caras = self._buscar_rostros(cuadro) if dibujar or para_panel else []
                anotado = self._anotar(cuadro, detecciones, asignadas, t, caras) if dibujar else None
                for ev, nombre, dets in pendientes:
                    self._emitir(ev, nombre, dets, anotado, resultado)

                if escritor is not None:
                    for _ in range(tiempo.cuadros_pendientes(t, resultado.t_inicio_s, periodo, escritos)):
                        escritor.write(anotado)
                        escritos += 1
                if self.publicador is not None:
                    jpeg = self._cuadro_para_panel(cuadro, detecciones, caras) if para_panel else None
                    fps_analisis = resultado.cuadros_analizados / max(1e-6, time.monotonic() - t0_reloj)
                    self.publicador.publicar(self._estado_vivo(t, detecciones, asignadas, latencia, fps_analisis), jpeg)
                    nueva = self.publicador.tomar_config_nueva()
                    if nueva is not None:
                        self._aplicar_config(nueva, t, resultado)
                if self.tiempo_real and es_archivo:
                    adelanto = (t - resultado.t_inicio_s) - (time.monotonic() - t0_reloj)
                    if adelanto > 0:
                        time.sleep(adelanto)
                if self.mostrar:
                    cv2.imshow("GymKeep Vision", anotado)
                    if cv2.waitKey(1) & 0xFF == ord("q"):
                        break
                if resultado.cuadros_analizados % 300 == 0:
                    log.info(
                        "%s  en uso: %s",
                        self._hora(t),
                        ", ".join(n for n, m in self.monitores.items() if m.sesion) or "-",
                    )
        except KeyboardInterrupt:
            resultado.interrumpido = True
            log.warning("Interrumpido: se cierran las sesiones abiertas")
        finally:
            motivo = "interrumpido" if resultado.interrumpido else "fin_de_video"
            for nombre, monitor in self.monitores.items():
                for ev in monitor.finalizar(t, motivo):
                    self._emitir(ev, nombre, [], None, resultado)
            resultado.t_final_s = t
            if lector is not None:
                lector.liberar()
            else:
                captura.release()
            presencia.cerrar()
            if escritor is not None:
                escritor.release()
                resultado.video_salida = _recodificar_h264(ruta_video_tmp, self.salida / "video_anotado.mp4")
            if self.mostrar:
                cv2.destroyAllWindows()
        return resultado

    # ------------------------------------------------------------------ etapas

    def _preparar_zonas(self, ancho: int, alto: int) -> None:
        if self.cfg.resolucion_referencia:
            ref_ancho, ref_alto = self.cfg.resolucion_referencia
            if (ref_ancho, ref_alto) != (ancho, alto):
                for zona in self.zonas:
                    zona.escalar(ancho / ref_ancho, alto / ref_alto)
        for zona in self.zonas:
            zona.preparar(alto, ancho)
            x_min, y_min = zona.poligono.min(axis=0)
            x_max, y_max = zona.poligono.max(axis=0)
            if x_min <= 2 or y_min <= 2 or x_max >= ancho - 3 or y_max >= alto - 3:
                # Una maquina en el borde queda cortada: la persona encima se detecta mal y
                # el uso se subestima. La solucion es mover la camara, no bajar umbrales.
                log.warning("La ROI de '%s' toca el borde del cuadro: su uso puede quedar subestimado", zona.nombre)

    def _buscar_rostros(self, cuadro: np.ndarray) -> list:
        if self.detector_rostros is None or not self.cfg.difuminar_personas:
            return []
        return self.detector_rostros.detectar(cuadro)

    def _vigilar_senal(self, lector: LectorVivo, t: float, resultado: Resultado) -> None:
        """Camara en vivo sin cuadros: pasados t_off_s segundos se cierran las sesiones
        abiertas con motivo 'sin_senal' (una sola vez por corte)."""
        if self._sin_senal or lector.sin_senal_s() <= self.cfg.uso.t_off_s:
            return
        self._sin_senal = True
        log.warning("Sin senal de la camara hace %.0f s: se cierran las sesiones abiertas", lector.sin_senal_s())
        for nombre, monitor in self.monitores.items():
            for ev in monitor.finalizar(t, "sin_senal"):
                self._emitir(ev, nombre, [], None, resultado)

    def _detectar(self, modelo, cuadro: np.ndarray) -> list[Deteccion]:
        m = self.cfg.modelo
        res = modelo.track(
            cuadro,
            persist=True,  # mantiene el estado del tracker entre llamadas (§6.6.7)
            classes=[0],  # COCO 0 = persona
            conf=m.confianza_detector,
            imgsz=m.imgsz,
            tracker=m.tracker,
            device=m.dispositivo,
            verbose=False,
        )[0]
        cajas = res.boxes
        if cajas is None or len(cajas) == 0:
            return []
        ids = cajas.id.int().tolist() if cajas.id is not None else [None] * len(cajas)
        puntos = res.keypoints.data.tolist() if getattr(res, "keypoints", None) is not None else [None] * len(cajas)
        return [
            Deteccion(
                bbox=tuple(float(v) for v in xyxy),
                confianza=float(conf),
                track_id=tid,
                puntos=tuple(map(tuple, kp)) if kp is not None else None,
            )
            for xyxy, conf, tid, kp in zip(cajas.xyxy.tolist(), cajas.conf.tolist(), ids, puntos)
        ]

    def _contar_activas(self, dets: list[Deteccion], activa: dict) -> int | None:
        """Personas activas en una zona, o None si no se mide la actividad. Una persona de
        actividad desconocida (recien aparecida, sin puntos) cuenta como activa."""
        if self.medidor is None:
            return None
        return sum(1 for d in dets if activa.get(id(d)) is not False)

    def _timestamp(self, t: float) -> str:
        """Hora real del instante `t` para registrar (ISO 8601 con milisegundos)."""
        return tiempo.marca(self.inicio_video, t)

    def _hora(self, t: float) -> str:
        """Hora real del instante `t` para mostrar (dd/mm/aaaa hh:mm:ss)."""
        return tiempo.hora(self.inicio_video + timedelta(seconds=t))

    def _emitir(self, ev, nombre: str, dets: list[Deteccion], anotado, resultado: Resultado) -> None:
        maquina = self.maquinas[nombre]
        evento = construir_evento(
            ev,
            cfg=self.cfg,
            maquina=maquina,
            inicio_video=self.inicio_video,
            detecciones=dets,
            snapshot_url=None,
            fuente=Path(self.fuente).name,
        )
        if ev.tipo == "inicio_uso" and anotado is not None:
            relativa = f"evidencias/{evento['event_uuid']}.jpg"
            cv2.imwrite(str(self.salida / relativa), anotado, [cv2.IMWRITE_JPEG_QUALITY, 80])
            evento["evidencia"]["snapshot_url"] = relativa
        for destino in self.destinos:
            destino.enviar(evento)
        resultado.eventos.append(evento)
        log.info(
            "%-12s %-22s %s%s",
            ev.tipo,
            nombre,
            self._hora(ev.t),
            f"  duracion {mmss(ev.sesion.duracion_s)}" if ev.tipo == "fin_uso" else "",
        )

    # ------------------------------------------------------------------ en vivo

    def _estado_vivo(self, t: float, detecciones, asignadas, latencia_s: float, fps: float) -> dict:
        """Lo que ve la camara ahora, en el formato de POST /vision/camaras/{id}/vivo. Las
        cajas van normalizadas (0..1) para dibujarlas sobre la imagen en el panel."""
        ancho, alto = self._ancho, self._alto
        maquina_de = {
            id(d): self.maquinas[nombre].equipo_id for nombre, dets in asignadas.items() for d in dets
        }

        def norm(v: float, total: int) -> float:
            return round(min(1.0, max(0.0, v / total)), 4)

        personas = [
            {
                "caja": [norm(d.bbox[0], ancho), norm(d.bbox[1], alto), norm(d.bbox[2], ancho), norm(d.bbox[3], alto)],
                "confianza": round(d.confianza, 3),
                "track_id": d.track_id,
                "equipo_id": maquina_de.get(id(d)),
            }
            for d in detecciones
            if d.confianza >= self.cfg.confianza_min
        ]
        if self.medidor is not None:  # solo si se mide: si no, el formato queda como siempre
            activa = {id(d): self._activa.get(id(d)) for d in detecciones}
            for persona, d in zip(personas, [d for d in detecciones if d.confianza >= self.cfg.confianza_min]):
                persona["activa"] = activa[id(d)]
        maquinas = []
        for zona in self.zonas:
            maquina, monitor = self.maquinas[zona.nombre], self.monitores[zona.nombre]
            if maquina.equipo_id is None:
                continue
            progreso = monitor.progreso(t)
            maquinas.append(
                {
                    "equipo_id": maquina.equipo_id,
                    "estado": monitor.estado.value,
                    "sesion_s": round(monitor.sesion.duracion_s, 1) if monitor.sesion else None,
                    "progreso_s": round(progreso[0], 1) if progreso else None,
                    "umbral_s": progreso[1] if progreso else None,
                    "personas": len(asignadas.get(zona.nombre, [])),
                }
            )
        return {
            "timestamp": self._timestamp(t),
            "ancho": ancho,
            "alto": alto,
            "fps_analisis": round(fps, 2),
            "latencia_ms": round(latencia_s * 1000, 1),
            "modelo": {"nombre": self.cfg.modelo.nombre, "version": self.cfg.modelo.version},
            "maquinas": maquinas,
            "personas": personas,
        }

    def _cuadro_para_panel(self, cuadro: np.ndarray, detecciones, caras=()) -> bytes:
        """Cuadro limpio (sin anotaciones: el panel dibuja las suyas) con cabezas y rostros
        difuminados y a lo mas 1280 px de ancho."""
        img = cuadro.copy()
        if self.cfg.difuminar_personas:
            _difuminar_cabezas(img, detecciones, caras=caras)
        alto, ancho = img.shape[:2]
        if ancho > 1280:
            img = cv2.resize(img, (1280, round(alto * 1280 / ancho)), interpolation=cv2.INTER_AREA)
        return cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 75])[1].tobytes()

    def _aplicar_config(self, datos: dict, t: float, resultado: Resultado) -> None:
        """Aplica zonas/parametros editados en el panel sin reiniciar. Una maquina que sigue
        conserva su estado (su sesion en curso no se corta); una quitada cierra su sesion."""
        from gymkeep_vision.config import desde_api

        try:
            nueva = desde_api(datos, base=self.cfg)
        except ValueError as exc:
            # Parametros de uso incoherentes (ej. t_off_s <= gracia_s): se aplican las zonas
            # pero los parametros siguen siendo los anteriores.
            log.warning("Parametros de uso invalidos desde la plataforma (%s): se conservan los anteriores", exc)
            uso = self.cfg.uso
            parametros = {
                **datos["parametros"],
                "t_on_s": uso.t_on_s, "t_off_s": uso.t_off_s, "gracia_s": uso.gracia_s, "t_max_s": uso.t_max_s,
            }
            nueva = desde_api({**datos, "parametros": parametros}, base=self.cfg)
        # Se emparejan por equipo_id y, si la maquina previa no lo tiene, por nombre.
        previos = {_clave_maquina(self.maquinas[n]): (n, mon) for n, mon in self.monitores.items()}
        continuan = {_clave_previa(m, previos) for m in nueva.maquinas}
        for clave, (nombre, monitor) in previos.items():
            if clave not in continuan:
                for ev in monitor.finalizar(t, "zona_quitada"):
                    self._emitir(ev, nombre, [], None, resultado)

        # El ritmo de analisis y el modelo no cambian en caliente (dependen del video abierto).
        self.cfg = replace(
            nueva,
            modelo=self.cfg.modelo,
            escala_tiempo=self.cfg.escala_tiempo,
            intervalo_analisis_s=self.cfg.intervalo_analisis_s,
        )
        self.maquinas = {m.nombre: m for m in self.cfg.maquinas}
        self.zonas = [
            ZonaMaquina(m.nombre, m.roi, criterio=m.criterio or self.cfg.criterio_zona, solape_min=self.cfg.solape_min)
            for m in self.cfg.maquinas
        ]
        self._preparar_zonas(self._ancho, self._alto)
        self.monitores = {}
        for m in self.cfg.maquinas:
            clave = _clave_previa(m, previos)
            monitor = previos[clave][1] if clave in previos else MonitorMaquina(self.cfg.uso)
            monitor.p = self.cfg.uso
            self.monitores[m.nombre] = monitor
        resultado.config, resultado.monitores = self.cfg, self.monitores
        log.info("Zonas actualizadas desde la plataforma: %s", ", ".join(self.maquinas) or "ninguna")

    # ------------------------------------------------------------------ dibujo

    def _anotar(self, cuadro, detecciones, asignadas, t, caras=()) -> np.ndarray:
        f = self._f
        img = cv2.resize(cuadro, self._tam_dibujo, interpolation=cv2.INTER_LINEAR) if f > 1 else cuadro.copy()
        if self.cfg.difuminar_personas:
            _difuminar_cabezas(img, detecciones, f, caras)

        capa = img.copy()
        for zona in self.zonas:
            color = COLORES[self.monitores[zona.nombre].estado]
            cv2.fillPoly(capa, [(zona.poligono * f).round().astype(np.int32)], color)
        cv2.addWeighted(capa, 0.22, img, 0.78, 0, img)

        en_zona = {id(d) for dets in asignadas.values() for d in dets}
        for det in detecciones:
            x1, y1, x2, y2 = (int(v * f) for v in det.bbox)
            asignada = id(det) in en_zona
            color = (255, 255, 255) if asignada else (170, 170, 170)
            cv2.rectangle(img, (x1, y1), (x2, y2), color, 2 if asignada else 1)
            ax, ay = (int(v * f) for v in det.ancla(self.cfg.criterio_zona))
            cv2.circle(img, (ax, ay), 5, color, -1)
            if det.track_id is not None:
                _texto(img, f"#{det.track_id} {det.confianza:.2f}", (x1, max(14, y1 - 6)), 0.45, color)

        for zona in self.zonas:
            monitor = self.monitores[zona.nombre]
            color = COLORES[monitor.estado]
            puntos = (zona.poligono * f).round().astype(np.int32)
            cv2.polylines(img, [puntos], True, color, 2)
            # Junto a la ROI va un rotulo corto con su cronometro (maquinas pegadas no se
            # tapan entre si); el detalle completo va en el panel de estado.
            x, y = puntos[:, 0].min(), puntos[:, 1].min()
            rotulo = f"{_rotulo(zona.nombre)} {_estado_corto(monitor, t)}".strip()
            _etiqueta(img, [rotulo], (int(x), int(y)), color)

        self._panel(img, t)
        return img

    def _panel(self, img: np.ndarray, t: float) -> None:
        uso = self.cfg.uso
        if self._en_vivo:
            reloj = "EN VIVO"
        elif self._duracion_s:
            reloj = f"video {mmss(t - self._desfase)} / {mmss(self._duracion_s)}"
        else:
            reloj = f"video {mmss(t)}"
        cabecera = [
            f"GymKeep Vision   {self._hora(t)}",
            f"{reloj}    T_on {uso.t_on_s:.0f} s   T_off {uso.t_off_s:.0f} s   conf >= {self.cfg.confianza_min:.2f}",
        ]
        filas = []
        for zona in self.zonas:
            monitor = self.monitores[zona.nombre]
            filas.append(
                (
                    COLORES[monitor.estado],
                    [
                        zona.nombre,
                        _estado_largo(monitor, t),
                        f"total {mmss(monitor.uso_total_s)}  |  {monitor.sesiones_total} ses.",
                    ],
                )
            )

        fuente, escala, alto_linea, sep = cv2.FONT_HERSHEY_SIMPLEX, 0.5, 20, 16

        def ancho_texto(texto: str) -> int:
            return cv2.getTextSize(texto, fuente, escala, 1)[0][0]

        # Columnas alineadas (la fuente no es monoespaciada): maquina | estado | acumulado.
        anchos = [max((ancho_texto(cols[i]) for _, cols in filas), default=0) for i in range(3)]
        ancho = max([ancho_texto(c) for c in cabecera] + [20 + sum(anchos) + 2 * sep]) + 16
        alto = alto_linea * (len(cabecera) + len(filas)) + 10
        x0, y0 = 10, img.shape[0] - alto - 10
        fondo = img.copy()
        cv2.rectangle(fondo, (x0, y0), (x0 + ancho, y0 + alto), (30, 30, 30), -1)
        cv2.addWeighted(fondo, 0.72, img, 0.28, 0, img)

        y = y0 + 20
        for texto in cabecera:
            cv2.putText(img, texto, (x0 + 8, y), fuente, escala, (255, 255, 255), 1, cv2.LINE_AA)
            y += alto_linea
        for color, cols in filas:
            x = x0 + 8
            cv2.rectangle(img, (x, y - 11), (x + 12, y + 1), color, -1)
            x += 20
            for texto, ancho_col in zip(cols, anchos):
                cv2.putText(img, texto, (x, y), fuente, escala, (255, 255, 255), 1, cv2.LINE_AA)
                x += ancho_col + sep
            y += alto_linea


def _clave_maquina(maquina: ConfigMaquina) -> int | str:
    """Identidad de una maquina entre dos configuraciones: su equipo_id o, si no lo tiene, su nombre."""
    return maquina.equipo_id if maquina.equipo_id is not None else maquina.nombre


def _clave_previa(maquina: ConfigMaquina, previos: dict) -> int | str:
    """Clave con la que una maquina de la configuracion nueva figura en `previos` (si estaba)."""
    if maquina.equipo_id in previos:
        return maquina.equipo_id
    return maquina.nombre if maquina.nombre in previos else _clave_maquina(maquina)


def _estado_largo(monitor: MonitorMaquina, t: float) -> str:
    """Estado con su cronometro: cuanto dura la sesion, o cuanto falta para T_on / T_off."""
    progreso = monitor.progreso(t)
    if monitor.estado == Estado.EN_USO:
        return f"EN USO {mmss(monitor.sesion.duracion_s)}"
    if monitor.estado == Estado.PAUSA and progreso:
        return f"PAUSA {progreso[0]:.0f}/{progreso[1]:.0f} s"
    if monitor.estado == Estado.CANDIDATA and progreso:
        return f"DETECTANDO {progreso[0]:.0f}/{progreso[1]:.0f} s"
    return ETIQUETAS[monitor.estado]


def _estado_corto(monitor: MonitorMaquina, t: float) -> str:
    """Cronometro que va junto a la ROI (vacio si la maquina esta libre)."""
    progreso = monitor.progreso(t)
    if monitor.estado == Estado.EN_USO:
        return mmss(monitor.sesion.duracion_s)
    if monitor.estado == Estado.PAUSA and progreso:
        return f"pausa {progreso[0]:.0f}s"
    if monitor.estado == Estado.CANDIDATA and progreso:
        return f"{progreso[0]:.0f}/{progreso[1]:.0f}s"
    return ""


def _rotulo(nombre: str) -> str:
    """'Trotadora 03' -> '03' (lo que cabe junto a la ROI); 'Remo sentado' queda igual."""
    ultima = nombre.split()[-1]
    return ultima if ultima.isdigit() else nombre


def _difuminar_cabezas(img: np.ndarray, detecciones: list[Deteccion], f: float = 1.0, caras=()) -> None:
    """Privacidad por diseno: el sistema mide uso de maquinas, no identifica personas.
    Difumina el tercio superior de cada persona y cada rostro encontrado por el detector de
    rostros (cajas x1, y1, x2, y2 en coordenadas del cuadro original), en el video, las
    evidencias y la imagen del panel."""
    alto, ancho = img.shape[:2]
    cajas = []
    for det in detecciones:
        x1, y1, x2, y2 = det.bbox
        cajas.append((x1, y1, x2, y1 + (y2 - y1) * 0.3))
    cajas += list(caras)
    for x1, y1, x2, y2 in cajas:
        x1, x2 = max(0, int(x1 * f)), min(ancho, int(x2 * f))
        y1, y2 = max(0, int(y1 * f)), min(alto, int(y2 * f))
        if x2 - x1 < 4 or y2 - y1 < 4:
            continue
        region = img[y1:y2, x1:x2]
        k = max(9, (min(region.shape[:2]) // 2) | 1)
        img[y1:y2, x1:x2] = cv2.GaussianBlur(region, (k, k), 0)


def _texto(img, texto, org, escala, color, grosor=1) -> None:
    cv2.putText(img, texto, org, cv2.FONT_HERSHEY_SIMPLEX, escala, (0, 0, 0), grosor + 2, cv2.LINE_AA)
    cv2.putText(img, texto, org, cv2.FONT_HERSHEY_SIMPLEX, escala, color, grosor, cv2.LINE_AA)


def _etiqueta(img, lineas: list[str], org, color) -> None:
    escala, grosor, alto_linea = 0.5, 1, 18
    ancho = max(cv2.getTextSize(l, cv2.FONT_HERSHEY_SIMPLEX, escala, grosor)[0][0] for l in lineas) + 12
    alto = alto_linea * len(lineas) + 8
    x, y = org
    y = max(0, y - alto)
    x = min(max(0, x), img.shape[1] - ancho)
    cv2.rectangle(img, (x, y), (x + ancho, y + alto), color, -1)
    for i, linea in enumerate(lineas):
        cv2.putText(
            img, linea, (x + 6, y + 18 + i * alto_linea), cv2.FONT_HERSHEY_SIMPLEX, escala,
            (255, 255, 255), grosor, cv2.LINE_AA,
        )


def _recodificar_h264(origen: Path, destino: Path) -> Path:
    """OpenCV escribe mp4v, que muchos navegadores no reproducen. Si hay ffmpeg, se
    recodifica a H.264 (y se limita a 1280 px de ancho para que el archivo sea liviano)."""
    if shutil.which("ffmpeg") is None:
        origen.replace(destino)
        return destino
    comando = [
        "ffmpeg", "-y", "-loglevel", "error", "-i", str(origen),
        "-vf", "scale='min(1280,iw)':-2", "-c:v", "libx264", "-preset", "veryfast",
        "-crf", "26", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(destino),
    ]
    if subprocess.run(comando).returncode == 0:
        origen.unlink()
    else:
        origen.replace(destino)
    return destino
