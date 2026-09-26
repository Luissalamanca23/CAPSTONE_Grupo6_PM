"""Linea de comandos: python -m gymkeep_vision {procesar,enviar,recalibrar,cuadro,calibrar} ..."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx

from gymkeep_vision import config as config_mod
from gymkeep_vision.config import RAIZ

ZONA_HORARIA = ZoneInfo("America/Santiago")


def _cliente(url: str) -> httpx.Client:
    return httpx.Client(base_url=url.rstrip("/"), timeout=10)


def cmd_procesar(args) -> int:
    from gymkeep_vision import reporte
    from gymkeep_vision.eventos import DestinoAPI, DestinoJSONL, resolver_ids
    from gymkeep_vision.pipeline import Pipeline

    cfg = config_mod.cargar(args.config).con_parametros(
        t_on_s=args.t_on, t_off_s=args.t_off, confianza_min=args.confianza, escala_tiempo=args.escala_tiempo
    )
    inicio = datetime.fromisoformat(args.inicio) if args.inicio else datetime.now(ZONA_HORARIA)
    if inicio.tzinfo is None:
        inicio = inicio.replace(tzinfo=ZONA_HORARIA)
    salida = Path(args.salida) if args.salida else (
        RAIZ / "salida" / f"{Path(args.video).stem}_{datetime.now():%Y%m%d-%H%M%S}"
    )

    destinos: list = [DestinoJSONL(salida / "eventos.jsonl")]
    api = None
    if args.api:
        cliente = _cliente(args.api)
        resolver_ids(cliente, cfg, registrar=args.registrar)
        api = DestinoAPI(cliente)
        destinos.append(api)
        logging.info(
            "GymKeep: camara %s -> id %s; equipos %s",
            cfg.camara.codigo, cfg.camara.id, {m.codigo_activo: m.equipo_id for m in cfg.maquinas},
        )

    resultado = Pipeline(
        cfg,
        args.video,
        salida,
        destinos=destinos,
        inicio_video=inicio,
        guardar_video=not args.sin_video,
        mostrar=args.mostrar,
        desde_s=args.desde,
        max_segundos=args.max_segundos,
    ).ejecutar()
    for destino in destinos:
        destino.cerrar()

    verdad = None
    if args.verdad:
        from gymkeep_vision.recalibrar import leer_verdad

        verdad = leer_verdad(Path(args.verdad))
    resumen = reporte.generar(resultado, salida, verdad)
    print()
    print(reporte.imprimir(resumen))
    print(f"\nResultados en: {salida}")
    if api is not None:
        print(f"Eventos enviados a GymKeep: {api.enviados} (fallidos: {len(api.fallidos)})")
        if api.fallidos:
            with (salida / "eventos_pendientes.jsonl").open("w", encoding="utf-8") as f:
                for evento in api.fallidos:
                    f.write(json.dumps(evento, ensure_ascii=False) + "\n")
            print("Los fallidos quedaron en eventos_pendientes.jsonl (reenviar con el comando 'enviar').")
    return 0


def cmd_enviar(args) -> int:
    """Reenvia a GymKeep los eventos de una corrida anterior (sin volver a procesar video)."""
    from gymkeep_vision.eventos import DestinoAPI, completar_ids, resolver_ids

    cfg = config_mod.cargar(args.config)
    cliente = _cliente(args.api)
    resolver_ids(cliente, cfg, registrar=args.registrar)
    eventos = [json.loads(l) for l in Path(args.eventos).read_text(encoding="utf-8").splitlines() if l.strip()]
    eventos.sort(key=lambda e: (e["metadata"]["t_emision_s"], e["metadata"]["t_s"]))
    api = DestinoAPI(cliente)
    sesiones = set()
    for evento in eventos:
        respuesta = api.enviar(completar_ids(evento, cfg))
        if respuesta and respuesta.get("sesion_uso_id"):
            sesiones.add(respuesta["sesion_uso_id"])
    print(f"Enviados {api.enviados}/{len(eventos)} eventos; sesiones de uso tocadas en GymKeep: {len(sesiones)}")
    return 0 if not api.fallidos else 1


def cmd_recalibrar(args) -> int:
    """Prueba otros parametros sobre la presencia ya registrada (sin volver a correr YOLO)."""
    from gymkeep_vision import recalibrar

    cfg = config_mod.cargar(args.config)
    series = recalibrar.leer_presencia(Path(args.corrida) / "presencia.csv")
    verdad = recalibrar.leer_verdad(Path(args.verdad)) if args.verdad else None
    resultados = recalibrar.barrido(
        series,
        cfg,
        confianzas=args.confianza or [cfg.confianza_min],
        gracias=args.gracia or [cfg.uso.gracia_s],
        t_ons=args.t_on or [cfg.uso.t_on_s],
        t_offs=args.t_off or [cfg.uso.t_off_s],
        verdad=verdad,
    )
    print(recalibrar.imprimir(resultados, con_verdad=verdad is not None))
    if verdad is not None:
        mejor = max(resultados, key=lambda r: (r["iou_promedio"], -r["error_uso_pct"]))
        print(
            f"Mejor combinacion: confianza_min={mejor['confianza_min']} gracia_s={mejor['gracia_s']} "
            f"t_on_s={mejor['t_on_s']} t_off_s={mejor['t_off_s']} "
            f"(IoU {mejor['iou_promedio']:.2f}, error de uso {mejor['error_uso_pct']:.1f}%)"
        )
    return 0


def cmd_cuadro(args) -> int:
    from gymkeep_vision.calibrar import exportar_cuadro

    cfg = config_mod.cargar(args.config) if args.config else None
    salida = Path(args.salida or f"{Path(args.video).stem}_t{int(args.t)}.png")
    print(exportar_cuadro(args.video, args.t, salida, cfg))
    return 0


def cmd_calibrar(args) -> int:
    from gymkeep_vision.calibrar import calibrar

    calibrar(args.video, args.t, Path(args.salida))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="gymkeep_vision", description=__doc__)
    sub = parser.add_subparsers(dest="comando", required=True)

    p = sub.add_parser("procesar", help="analiza un video (o camara) y mide el uso de cada maquina")
    p.add_argument("video", help="archivo de video, URL rtsp:// o indice de webcam (0)")
    p.add_argument("-c", "--config", required=True, help="YAML de la camara (ROI y parametros)")
    p.add_argument("-o", "--salida", help="carpeta de resultados (por defecto vision/salida/<video>_<fecha>)")
    p.add_argument("--api", help="URL de la API GymKeep (ej. http://localhost:8000) para enviar eventos en vivo")
    p.add_argument("--registrar", action="store_true", help="crea en GymKeep la camara/equipos/modelo que falten")
    p.add_argument("--inicio", help="fecha-hora real del primer cuadro (ISO 8601); por defecto, ahora")
    p.add_argument("--desde", type=float, default=0.0, help="segundo del video (del archivo) donde empezar")
    p.add_argument("--max-segundos", type=float, help="analizar solo esta cantidad de segundos del archivo")
    p.add_argument("--t-on", type=float, help="sobrescribe T_on (MP-45) en segundos")
    p.add_argument("--t-off", type=float, help="sobrescribe T_off (MP-46) en segundos")
    p.add_argument("--confianza", type=float, help="sobrescribe la confianza minima (MP-47)")
    p.add_argument("--escala-tiempo", type=float, help="segundos reales por segundo de video (videos de NVR acelerados)")
    p.add_argument("--verdad", help="CSV con el uso real anotado a mano: agrega error e IoU al resumen y al grafico")
    p.add_argument("--sin-video", action="store_true", help="no genera el video anotado (mas rapido)")
    p.add_argument("--mostrar", action="store_true", help="muestra el video anotado en una ventana (Q para salir)")
    p.set_defaults(func=cmd_procesar)

    p = sub.add_parser("enviar", help="reenvia a la API los eventos de un eventos.jsonl")
    p.add_argument("eventos")
    p.add_argument("-c", "--config", required=True)
    p.add_argument("--api", required=True)
    p.add_argument("--registrar", action="store_true")
    p.set_defaults(func=cmd_enviar)

    p = sub.add_parser("recalibrar", help="prueba parametros sobre presencia.csv de una corrida (sin YOLO)")
    p.add_argument("corrida", help="carpeta de resultados de 'procesar' (con presencia.csv)")
    p.add_argument("-c", "--config", required=True)
    p.add_argument("--verdad", help="CSV con los intervalos reales de uso (maquina,inicio_s,fin_s)")
    p.add_argument("--confianza", type=float, nargs="+", help="umbrales a probar (MP-47)")
    p.add_argument("--gracia", type=float, nargs="+", help="tolerancias a huecos de deteccion, en segundos")
    p.add_argument("--t-on", type=float, nargs="+", help="valores de T_on a probar (MP-45)")
    p.add_argument("--t-off", type=float, nargs="+", help="valores de T_off a probar (MP-46)")
    p.set_defaults(func=cmd_recalibrar)

    p = sub.add_parser("cuadro", help="exporta un cuadro con grilla de coordenadas (y ROI) para dibujar ROI")
    p.add_argument("video")
    p.add_argument("-c", "--config")
    p.add_argument("--t", type=float, default=1.0, help="segundo del video")
    p.add_argument("-o", "--salida")
    p.set_defaults(func=cmd_cuadro)

    p = sub.add_parser("calibrar", help="dibuja las ROI con el mouse y las guarda en un YAML")
    p.add_argument("video")
    p.add_argument("-o", "--salida", required=True)
    p.add_argument("--t", type=float, default=1.0)
    p.set_defaults(func=cmd_calibrar)

    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(message)s", datefmt="%H:%M:%S")
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
