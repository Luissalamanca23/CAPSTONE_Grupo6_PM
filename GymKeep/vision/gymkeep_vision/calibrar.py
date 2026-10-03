"""Herramientas para definir las ROI de cada maquina sobre un cuadro de la camara.

- `cuadro`: guarda un cuadro con una grilla de coordenadas (y las ROI ya definidas), para
  dibujar o revisar las ROI a mano.
- `calibrar`: ventana interactiva de OpenCV para marcar los poligonos con el mouse.
"""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import yaml

from gymkeep_vision.config import Config


def leer_cuadro(video: str, t: float) -> np.ndarray:
    captura = cv2.VideoCapture(video)
    captura.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
    ok, cuadro = captura.read()
    captura.release()
    if not ok:
        raise RuntimeError(f"No se pudo leer el cuadro en t={t}s de {video}")
    return cuadro


def dibujar_grilla(img: np.ndarray, paso: int = 100) -> np.ndarray:
    img = img.copy()
    alto, ancho = img.shape[:2]
    for x in range(0, ancho, paso):
        cv2.line(img, (x, 0), (x, alto), (255, 255, 255), 1)
        cv2.putText(img, str(x), (x + 2, 14), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 255), 1, cv2.LINE_AA)
    for y in range(0, alto, paso):
        cv2.line(img, (0, y), (ancho, y), (255, 255, 255), 1)
        cv2.putText(img, str(y), (2, y - 3), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 255), 1, cv2.LINE_AA)
    return img


def dibujar_rois(img: np.ndarray, cfg: Config) -> np.ndarray:
    img = img.copy()
    alto, ancho = img.shape[:2]
    fx = fy = 1.0
    if cfg.resolucion_referencia:
        fx, fy = ancho / cfg.resolucion_referencia[0], alto / cfg.resolucion_referencia[1]
    for maquina in cfg.maquinas:
        puntos = (np.asarray(maquina.roi) * [fx, fy]).round().astype(np.int32)
        cv2.polylines(img, [puntos], True, (0, 0, 255), 2)
        x, y = puntos[:, 0].min(), puntos[:, 1].min()
        cv2.putText(img, maquina.nombre, (int(x), int(y) - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 4, cv2.LINE_AA)
        cv2.putText(img, maquina.nombre, (int(x), int(y) - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 1, cv2.LINE_AA)
    return img


def exportar_cuadro(video: str, t: float, salida: Path, cfg: Config | None = None) -> Path:
    img = dibujar_grilla(leer_cuadro(video, t))
    if cfg is not None:
        img = dibujar_rois(img, cfg)
    cv2.imwrite(str(salida), img)
    return salida


def calibrar(video: str, t: float, salida: Path) -> None:
    """Clic izquierdo: agrega un punto. ENTER: cierra la maquina actual (pide nombre y
    codigo de activo en la terminal). U: deshace el ultimo punto. S: guarda y sale.
    Q/ESC: sale sin guardar."""
    base = leer_cuadro(video, t)
    alto, ancho = base.shape[:2]
    maquinas: list[dict] = []
    puntos: list[list[int]] = []

    def al_clic(evento, x, y, *_):
        if evento == cv2.EVENT_LBUTTONDOWN:
            puntos.append([x, y])

    ventana = "GymKeep - calibrar ROI (clic: punto, ENTER: cerrar maquina, U: deshacer, S: guardar, Q: salir)"
    cv2.namedWindow(ventana, cv2.WINDOW_NORMAL)
    cv2.setMouseCallback(ventana, al_clic)
    while True:
        img = base.copy()
        for m in maquinas:
            poligono = np.asarray(m["roi"], dtype=np.int32)
            cv2.polylines(img, [poligono], True, (0, 200, 0), 2)
            cv2.putText(img, m["nombre"], tuple(poligono[0]), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 200, 0), 2)
        if puntos:
            cv2.polylines(img, [np.asarray(puntos, dtype=np.int32)], False, (0, 0, 255), 2)
            for p in puntos:
                cv2.circle(img, tuple(p), 4, (0, 0, 255), -1)
        cv2.imshow(ventana, img)
        tecla = cv2.waitKey(30) & 0xFF
        if tecla in (13, 10) and len(puntos) >= 3:
            nombre = input("Nombre de la maquina (ej. Cinta 01): ").strip()
            codigo = input("Codigo de activo en GymKeep (ej. EQ-0001): ").strip()
            maquinas.append({"nombre": nombre, "codigo_activo": codigo, "roi": [list(p) for p in puntos]})
            puntos.clear()
        elif tecla == ord("u") and puntos:
            puntos.pop()
        elif tecla == ord("s"):
            break
        elif tecla in (ord("q"), 27):
            cv2.destroyAllWindows()
            return
    cv2.destroyAllWindows()

    if salida.exists():
        datos = yaml.safe_load(salida.read_text(encoding="utf-8")) or {}
        print(f"Aviso: se reemplazan las maquinas de {salida} (los comentarios del YAML se pierden).")
    else:
        datos = {
            "camara": {"codigo": "CAM-XX", "nombre": "Camara nueva", "sucursal_codigo": "PM-01", "zona_nombre": "Cardio"},
            "parametros": {"t_on_s": 30, "t_off_s": 90, "confianza_min": 0.5},
        }
    datos["resolucion_referencia"] = [ancho, alto]
    datos["maquinas"] = maquinas
    salida.write_text(yaml.safe_dump(datos, allow_unicode=True, sort_keys=False), encoding="utf-8")
    print(f"Guardado: {salida} ({len(maquinas)} maquinas)")
