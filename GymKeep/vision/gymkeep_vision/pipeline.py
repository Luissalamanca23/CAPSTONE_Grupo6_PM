"""Etapas 1 a 3 de §6.6.1: deteccion -> seguimiento -> eventos de uso.

Por cada cuadro analizado:
  1. YOLO detecta personas y ByteTrack les asigna un ID que se mantiene entre cuadros.
  2. Cada persona se asigna (o no) a la ROI de una maquina (`zonas.asignar`).
  3. Cada maquina actualiza su maquina de estados (`sesiones.MonitorMaquina`), que emite
     `inicio_uso` / `uso_en_curso` / `fin_uso` cuando corresponde.
Los eventos se escriben en `eventos.jsonl` y, si hay API, se envian a GymKeep.
"""

from __future__ import annotations

import csv
import logging
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

import cv2
import numpy as np

from gymkeep_vision.config import Config, ConfigMaquina
from gymkeep_vision.eventos import construir_evento
from gymkeep_vision.sesiones import Estado, MonitorMaquina, Observacion
from gymkeep_vision.zonas import Deteccion, ZonaMaquina, asignar

log = logging.getLogger(__name__)

# Colores BGR por estado de la maquina.
COLORES = {
    Estado.LIBRE: (120, 170, 60),
    Estado.CANDIDATA: (40, 190, 240),
    Estado.EN_USO: (60, 60, 230),
    Estado.PAUSA: (40, 140, 250),
}
ETIQUETAS = {
    Estado.LIBRE: "LIBRE",
    Estado.CANDIDATA: "DETECTANDO",
    Estado.EN_USO: "EN USO",
    Estado.PAUSA: "PAUSA",
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
    eventos: list[dict] = field(default_factory=list)
    t_inicio_s: float = 0.0
    t_final_s: float = 0.0
    cuadros_analizados: int = 0
    segundos_computo: float = 0.0
    video_salida: Path | None = None
    interrumpido: bool = False


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
    ):
        self.cfg = cfg
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

    # ------------------------------------------------------------------ ejecucion

    def ejecutar(self) -> Resultado:
        from ultralytics import YOLO  # import tardio: los tests no necesitan torch

        es_archivo = Path(self.fuente).exists()
        captura = cv2.VideoCapture(int(self.fuente) if self.fuente.isdigit() else self.fuente)
        if not captura.isOpened():
            raise RuntimeError(f"No se pudo abrir la fuente de video: {self.fuente}")

        fps = captura.get(cv2.CAP_PROP_FPS) or 25.0
        ancho = int(captura.get(cv2.CAP_PROP_FRAME_WIDTH))
        alto = int(captura.get(cv2.CAP_PROP_FRAME_HEIGHT))
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

        escritor = None
        ruta_video_tmp = self.salida / "video_anotado_tmp.mp4"
        if self.guardar_video:
            fps_salida = fps / salto if es_archivo else 1 / self.cfg.intervalo_analisis_s
            escritor = cv2.VideoWriter(
                str(ruta_video_tmp), cv2.VideoWriter_fourcc(*"mp4v"), fps_salida, self._tam_dibujo
            )

        archivo_presencia = (self.salida / "presencia.csv").open("w", newline="", encoding="utf-8")
        presencia = csv.writer(archivo_presencia)
        presencia.writerow(["t_s", "timestamp", "maquina", "personas", "confianza_max", "estado"])

        t0_reloj = time.monotonic()
        t_ultimo_vivo = -1e9
        t = resultado.t_inicio_s
        try:
            while True:
                if es_archivo and (indice - int(self.desde_s * fps)) % salto:
                    if not captura.grab():
                        break
                    indice += 1
                    continue
                ok, cuadro = captura.read()
                if not ok:
                    break
                indice += 1

                if es_archivo:
                    t = (indice - 1) / fps * escala
                else:
                    t = time.monotonic() - t0_reloj
                    if t - t_ultimo_vivo < self.cfg.intervalo_analisis_s:
                        continue
                    t_ultimo_vivo = t
                if self.max_segundos is not None and (t - resultado.t_inicio_s) / escala > self.max_segundos:
                    break

                inicio_computo = time.perf_counter()
                detecciones = self._detectar(modelo, cuadro)
                # Se asignan todas las detecciones y despues se filtra por confianza_min: asi
                # presencia.csv guarda la confianza aunque no llegue al umbral, y el comando
                # `recalibrar` puede probar otros umbrales sin volver a correr YOLO.
                todas = asignar(detecciones, self.zonas)
                asignadas = {
                    nombre: [d for d in dets if d.confianza >= self.cfg.confianza_min]
                    for nombre, dets in todas.items()
                }
                resultado.segundos_computo += time.perf_counter() - inicio_computo
                resultado.cuadros_analizados += 1

                pendientes = []
                for zona in self.zonas:
                    dets = asignadas[zona.nombre]
                    obs = Observacion(
                        t=t,
                        personas=len(dets),
                        confianza=max((d.confianza for d in dets), default=None),
                        track_ids=tuple(d.track_id for d in dets if d.track_id is not None),
                    )
                    monitor = self.monitores[zona.nombre]
                    pendientes += [(ev, zona.nombre, dets) for ev in monitor.actualizar(obs)]
                    presencia.writerow(
                        [
                            f"{t:.2f}",
                            self._timestamp(t),
                            zona.nombre,
                            obs.personas,
                            f"{max(d.confianza for d in todas[zona.nombre]):.3f}" if todas[zona.nombre] else "",
                            monitor.estado.value,
                        ]
                    )
                # Se dibuja despues de actualizar, para que la evidencia de un inicio_uso ya
                # muestre la maquina EN USO.
                anotado = self._anotar(cuadro, detecciones, asignadas, t)
                for ev, nombre, dets in pendientes:
                    self._emitir(ev, nombre, dets, anotado, resultado)

                if escritor is not None:
                    escritor.write(anotado)
                if self.mostrar:
                    cv2.imshow("GymKeep Vision", anotado)
                    if cv2.waitKey(1) & 0xFF == ord("q"):
                        break
                if resultado.cuadros_analizados % 300 == 0:
                    log.info(
                        "t=%s  en uso: %s",
                        mmss(t),
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
            captura.release()
            archivo_presencia.close()
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
        return [
            Deteccion(bbox=tuple(float(v) for v in xyxy), confianza=float(conf), track_id=tid)
            for xyxy, conf, tid in zip(cajas.xyxy.tolist(), cajas.conf.tolist(), ids)
        ]

    def _timestamp(self, t: float) -> str:
        return (self.inicio_video + timedelta(seconds=t)).isoformat(timespec="seconds")

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
            self._timestamp(ev.t),
            f"  duracion {mmss(ev.sesion.duracion_s)}" if ev.tipo == "fin_uso" else "",
        )

    # ------------------------------------------------------------------ dibujo

    def _anotar(self, cuadro, detecciones, asignadas, t) -> np.ndarray:
        f = self._f
        img = cv2.resize(cuadro, self._tam_dibujo, interpolation=cv2.INTER_LINEAR) if f > 1 else cuadro.copy()
        if self.cfg.difuminar_personas:
            _difuminar_cabezas(img, detecciones, f)

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
            # Junto a la ROI va solo un rotulo corto (maquinas pegadas no se tapan entre si);
            # el detalle va en el panel de estado.
            x, y = puntos[:, 0].min(), puntos[:, 1].min()
            _etiqueta(img, [_rotulo(zona.nombre)], (int(x), int(y)), color)

        self._panel(img, t)
        return img

    def _panel(self, img: np.ndarray, t: float) -> None:
        uso = self.cfg.uso
        filas = [
            (None, f"GymKeep Vision  {self._timestamp(t)}"),
            (None, f"T_on {uso.t_on_s:.0f}s  T_off {uso.t_off_s:.0f}s  conf>={self.cfg.confianza_min:.2f}"),
        ]
        for zona in self.zonas:
            monitor = self.monitores[zona.nombre]
            estado = ETIQUETAS[monitor.estado]
            if monitor.sesion is not None:
                estado += f" {mmss(monitor.sesion.duracion_s)}"
            filas.append(
                (
                    COLORES[monitor.estado],
                    f"{zona.nombre}: {estado:<16} total {mmss(monitor.uso_total_s)} ({len(monitor.sesiones)} ses.)",
                )
            )
        escala, alto_linea = 0.5, 20
        ancho = max(cv2.getTextSize(txt, cv2.FONT_HERSHEY_SIMPLEX, escala, 1)[0][0] for _, txt in filas) + 34
        alto = alto_linea * len(filas) + 10
        x0, y0 = 10, img.shape[0] - alto - 10
        fondo = img.copy()
        cv2.rectangle(fondo, (x0, y0), (x0 + ancho, y0 + alto), (30, 30, 30), -1)
        cv2.addWeighted(fondo, 0.72, img, 0.28, 0, img)
        for i, (color, txt) in enumerate(filas):
            y = y0 + 20 + i * alto_linea
            x = x0 + 8
            if color is not None:
                cv2.rectangle(img, (x, y - 11), (x + 12, y + 1), color, -1)
                x += 20
            cv2.putText(img, txt, (x, y), cv2.FONT_HERSHEY_SIMPLEX, escala, (255, 255, 255), 1, cv2.LINE_AA)


def _rotulo(nombre: str) -> str:
    """'Trotadora 03' -> '03' (lo que cabe junto a la ROI); 'Remo sentado' queda igual."""
    ultima = nombre.split()[-1]
    return ultima if ultima.isdigit() else nombre


def _difuminar_cabezas(img: np.ndarray, detecciones: list[Deteccion], f: float = 1.0) -> None:
    """Privacidad por diseno: el sistema mide uso de maquinas, no identifica personas.
    Difumina el tercio superior de cada persona en el video y las evidencias."""
    alto, ancho = img.shape[:2]
    for det in detecciones:
        x1, y1, x2, y2 = (v * f for v in det.bbox)
        cabeza_y2 = y1 + (y2 - y1) * 0.3
        x1, x2 = max(0, int(x1)), min(ancho, int(x2))
        y1, cabeza_y2 = max(0, int(y1)), min(alto, int(cabeza_y2))
        if x2 - x1 < 4 or cabeza_y2 - y1 < 4:
            continue
        region = img[y1:cabeza_y2, x1:x2]
        k = max(9, (min(region.shape[:2]) // 2) | 1)
        img[y1:cabeza_y2, x1:x2] = cv2.GaussianBlur(region, (k, k), 0)


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
