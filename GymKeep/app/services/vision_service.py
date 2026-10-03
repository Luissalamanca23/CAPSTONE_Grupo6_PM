"""Integracion del modulo de vision con la plataforma.

Donde queda cada dato:

- PostgreSQL (negocio): las zonas (ROI) de cada maquina en cada camara (`camara_equipos.roi`),
  los parametros de deteccion por camara (`camaras.configuracion["vision"]`), la ultima
  conexion de la camara y, por el flujo de eventos ya existente, `sesiones_uso`.
- MongoDB (registro en vivo):
    - `camaras_vivo`: un documento por camara con lo ultimo que vio el pipeline (estado de
      cada maquina, personas detectadas y el ultimo cuadro en JPEG). Es lo que consulta el
      panel para mostrar la camara "en vivo".
    - `detecciones_raw`: historial de detecciones (TTL 7 dias, ya definido en init-mongo.js).
    - `telemetria_camaras`: salud del pipeline cada 30 s (TTL 30 dias, ya definido).
    - `fotos_equipos`: foto de referencia de cada maquina.
"""

from __future__ import annotations

import io
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from bson import Binary
from PIL import Image, UnidentifiedImageError
from sqlalchemy import delete, insert, select, update
from sqlalchemy.orm import Session

from app.core.mongo import get_mongo_db
from app.crud.sesion_uso import _segundos_union
from app.models.gymkeep import (
    Camara,
    EstadoCamara,
    EstadoEquipo,
    Equipo,
    Mantenimiento,
    SesionUso,
    camara_equipos,
)
from app.schemas.vision import EstadoVivoIn, ParametrosVision

EN_LINEA_S = 15  # sin datos del pipeline por mas de esto, la camara se considera sin senal
TELEMETRIA_CADA_S = 30
MAX_LADO_CUADRO = 1280
MAX_LADO_FOTO = 800

try:
    ZONA_LOCAL = ZoneInfo("America/Santiago")
except ZoneInfoNotFoundError:  # imagen sin base de zonas horarias
    ZONA_LOCAL = timezone(timedelta(hours=-3))


class ImagenInvalida(ValueError):
    pass


def _ahora() -> datetime:
    return datetime.now(timezone.utc)


def _utc(momento: datetime | None) -> datetime | None:
    """Mongo y SQLite devuelven fechas sin zona horaria (en UTC); Postgres, con zona."""
    if momento is None:
        return None
    return momento.replace(tzinfo=timezone.utc) if momento.tzinfo is None else momento


# ---------------------------------------------------------------- imagenes


def _a_jpeg(contenido: bytes, max_lado: int) -> tuple[bytes, int, int]:
    """Valida una imagen (JPEG/PNG/WebP), la achica si hace falta y la deja en JPEG."""
    if not contenido:
        raise ImagenInvalida("La imagen esta vacia.")
    try:
        imagen = Image.open(io.BytesIO(contenido))
        imagen.load()
    except (UnidentifiedImageError, OSError) as exc:
        raise ImagenInvalida("El archivo no es una imagen valida.") from exc
    imagen = imagen.convert("RGB")
    imagen.thumbnail((max_lado, max_lado))
    salida = io.BytesIO()
    imagen.save(salida, format="JPEG", quality=82)
    return salida.getvalue(), imagen.width, imagen.height


# ---------------------------------------------------------------- camaras y ROI


def roi_normalizada(roi, camara: Camara) -> list[tuple[float, float]] | None:
    """ROI guardada en `camara_equipos.roi` -> poligono normalizado (0..1).

    Formato nuevo: {"puntos": [[x, y], ...], "normalizado": true}. Tambien se acepta el
    rectangulo en pixeles de seed.sql ({"x", "y", "w", "h"}) si la camara tiene resolucion."""
    if not roi:
        return None
    if isinstance(roi, dict) and roi.get("puntos"):
        return [(float(x), float(y)) for x, y in roi["puntos"]]
    if isinstance(roi, dict) and {"x", "y", "w", "h"} <= roi.keys():
        if not camara.ancho_px or not camara.alto_px:
            return None
        x, y = roi["x"] / camara.ancho_px, roi["y"] / camara.alto_px
        w, h = roi["w"] / camara.ancho_px, roi["h"] / camara.alto_px
        return [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]
    return None


def _asociaciones(db: Session, *, camara_id: int | None = None, equipo_ids=None):
    consulta = select(camara_equipos)
    if camara_id is not None:
        consulta = consulta.where(camara_equipos.c.camara_id == camara_id)
    if equipo_ids is not None:
        consulta = consulta.where(camara_equipos.c.equipo_id.in_(list(equipo_ids)))
    return db.execute(consulta).all()


def parametros_de(camara: Camara) -> ParametrosVision:
    guardados = (camara.configuracion or {}).get("vision") or {}
    return ParametrosVision(**guardados)


def guardar_parametros(db: Session, camara: Camara, parametros: ParametrosVision) -> ParametrosVision:
    # JSON se reemplaza entero (SQLAlchemy no detecta cambios dentro del dict).
    camara.configuracion = {**(camara.configuracion or {}), "vision": parametros.model_dump()}
    db.commit()
    return parametros


def maquinas_de_camara(db: Session, camara: Camara, *, solo_con_zona: bool = False) -> list[dict]:
    filas = _asociaciones(db, camara_id=camara.id)
    equipos = {e.id: e for e in db.query(Equipo).filter(Equipo.id.in_([f.equipo_id for f in filas]))}
    maquinas = []
    for fila in filas:
        equipo = equipos.get(fila.equipo_id)
        if equipo is None:
            continue
        roi = roi_normalizada(fila.roi, camara)
        if solo_con_zona and (roi is None or not fila.activo):
            continue
        maquinas.append(
            {
                "equipo_id": equipo.id,
                "codigo_activo": equipo.codigo_activo,
                "nombre": equipo.nombre,
                "categoria": equipo.categoria,
                "estado": equipo.estado.value if hasattr(equipo.estado, "value") else equipo.estado,
                "roi": roi,
                "activo": bool(fila.activo),
            }
        )
    return sorted(maquinas, key=lambda m: m["nombre"])


def guardar_roi(db: Session, camara: Camara, equipo: Equipo, puntos: list[tuple[float, float]]) -> dict:
    roi = {"puntos": [list(p) for p in puntos], "normalizado": True}
    existe = _asociaciones(db, camara_id=camara.id, equipo_ids=[equipo.id])
    if existe:
        db.execute(
            update(camara_equipos)
            .where(camara_equipos.c.camara_id == camara.id, camara_equipos.c.equipo_id == equipo.id)
            .values(roi=roi, activo=True)
        )
    else:
        db.execute(insert(camara_equipos).values(camara_id=camara.id, equipo_id=equipo.id, roi=roi, activo=True))
    db.commit()
    return next(m for m in maquinas_de_camara(db, camara) if m["equipo_id"] == equipo.id)


def quitar_maquina(db: Session, camara: Camara, equipo_id: int) -> bool:
    resultado = db.execute(
        delete(camara_equipos).where(
            camara_equipos.c.camara_id == camara.id, camara_equipos.c.equipo_id == equipo_id
        )
    )
    db.commit()
    return resultado.rowcount > 0


def _vivo_por_camara() -> dict[int, dict]:
    docs = get_mongo_db().camaras_vivo.find(
        {}, {"recibido": 1, "maquinas": 1, "cuadro_timestamp": 1, "cuadro_ancho": 1}
    )
    return {d["_id"]: d for d in docs}


def _en_linea(doc: dict | None) -> bool:
    if not doc or not doc.get("recibido"):
        return False
    return (_ahora() - _utc(doc["recibido"])).total_seconds() <= EN_LINEA_S


def resumen_camara(db: Session, camara: Camara, vivo: dict | None) -> dict:
    con_zona = [m for m in maquinas_de_camara(db, camara, solo_con_zona=True)]
    return {
        "id": camara.id,
        "codigo": camara.codigo,
        "nombre": camara.nombre,
        "sucursal_id": camara.sucursal_id,
        "zona_id": camara.zona_id,
        "estado": camara.estado.value if hasattr(camara.estado, "value") else camara.estado,
        "rtsp_url": camara.rtsp_url,
        "ancho_px": camara.ancho_px,
        "alto_px": camara.alto_px,
        "ultima_conexion": camara.ultima_conexion,
        "en_linea": _en_linea(vivo),
        "tiene_cuadro": bool(vivo and vivo.get("cuadro_timestamp")),
        "maquinas": len(con_zona),
    }


def listar_camaras(db: Session, sucursal_id: int | None = None) -> list[dict]:
    consulta = db.query(Camara)
    if sucursal_id is not None:
        consulta = consulta.filter(Camara.sucursal_id == sucursal_id)
    vivos = _vivo_por_camara()
    return [resumen_camara(db, c, vivos.get(c.id)) for c in consulta.order_by(Camara.id)]


def detalle_camara(db: Session, camara: Camara) -> dict:
    vivo = get_mongo_db().camaras_vivo.find_one({"_id": camara.id}, {"cuadro": 0})
    return {
        **resumen_camara(db, camara, vivo),
        "parametros": parametros_de(camara),
        "lista_maquinas": maquinas_de_camara(db, camara),
    }


def configuracion_pipeline(db: Session, camara: Camara) -> dict:
    return {
        "camara_id": camara.id,
        "codigo": camara.codigo,
        "nombre": camara.nombre,
        "empresa_id": camara.sucursal.empresa_id if camara.sucursal else None,
        "sucursal_id": camara.sucursal_id,
        "zona_id": camara.zona_id,
        "parametros": parametros_de(camara),
        "maquinas": maquinas_de_camara(db, camara, solo_con_zona=True),
    }


# ---------------------------------------------------------------- en vivo


def registrar_vivo(db: Session, camara: Camara, estado: EstadoVivoIn) -> None:
    mongo = get_mongo_db()
    ahora = _ahora()
    previo = mongo.camaras_vivo.find_one({"_id": camara.id}, {"ultima_telemetria": 1})

    datos = estado.model_dump(mode="python")
    mongo.camaras_vivo.update_one(
        {"_id": camara.id},
        {"$set": {**datos, "camara_id": camara.id, "recibido": ahora}},
        upsert=True,
    )

    # Historial crudo (TTL 7 dias): solo cuando hay alguien en cuadro, para no llenar la
    # coleccion de documentos vacios.
    if estado.personas:
        mongo.detecciones_raw.insert_one(
            {
                "timestamp": estado.timestamp,
                "camara_id": camara.id,
                "modelo": datos["modelo"],
                "detecciones": datos["personas"],
                "procesado": True,
                "metadata": {"maquinas": datos["maquinas"]},
            }
        )

    ultima = _utc((previo or {}).get("ultima_telemetria"))
    if ultima is None or (ahora - ultima).total_seconds() >= TELEMETRIA_CADA_S:
        mongo.telemetria_camaras.insert_one(
            {
                "timestamp": ahora,
                "camara_id": camara.id,
                "estado": "en_linea",
                "fps_real": estado.fps_analisis,
                "latencia_ms": estado.latencia_ms,
                "metadata": {
                    "ancho": estado.ancho,
                    "alto": estado.alto,
                    "maquinas_en_uso": sum(1 for m in estado.maquinas if m.estado in ("en_uso", "pausa")),
                    "personas": len(estado.personas),
                },
            }
        )
        mongo.camaras_vivo.update_one({"_id": camara.id}, {"$set": {"ultima_telemetria": ahora}})

    camara.ultima_conexion = ahora
    camara.estado = EstadoCamara.activa
    camara.ancho_px, camara.alto_px = estado.ancho, estado.alto
    db.commit()


def estado_vivo(camara_id: int) -> dict:
    doc = get_mongo_db().camaras_vivo.find_one({"_id": camara_id}, {"cuadro": 0})
    if not doc:
        return {"camara_id": camara_id, "en_linea": False}
    recibido = _utc(doc.get("recibido"))
    return {
        **{k: v for k, v in doc.items() if k != "_id"},
        "camara_id": camara_id,
        "en_linea": _en_linea(doc),
        "edad_s": round((_ahora() - recibido).total_seconds(), 1) if recibido else None,
        "recibido": recibido,
        "timestamp": _utc(doc.get("timestamp")),
        "cuadro_timestamp": _utc(doc.get("cuadro_timestamp")),
    }


def guardar_cuadro(camara: Camara, contenido: bytes) -> dict:
    jpeg, ancho, alto = _a_jpeg(contenido, MAX_LADO_CUADRO)
    ahora = _ahora()
    get_mongo_db().camaras_vivo.update_one(
        {"_id": camara.id},
        {
            "$set": {
                "camara_id": camara.id,
                "cuadro": Binary(jpeg),
                "cuadro_timestamp": ahora,
                "cuadro_ancho": ancho,
                "cuadro_alto": alto,
            }
        },
        upsert=True,
    )
    return {"ancho": ancho, "alto": alto, "bytes": len(jpeg), "timestamp": ahora}


def leer_cuadro(camara_id: int) -> bytes | None:
    doc = get_mongo_db().camaras_vivo.find_one({"_id": camara_id}, {"cuadro": 1})
    return bytes(doc["cuadro"]) if doc and doc.get("cuadro") else None


# ---------------------------------------------------------------- uso de maquinas


def _recortar(intervalos, desde: datetime):
    return [(max(ini, desde), fin) for ini, fin in intervalos if fin > desde]


def _horas(intervalos) -> float:
    return round(_segundos_union(intervalos) / 3600, 3) if intervalos else 0.0


def _ultima_mantencion(mantenciones) -> datetime | None:
    momentos = [_utc(m.fecha_fin or m.fecha_inicio) for m in mantenciones]
    return max(momentos) if momentos else None


def _resumenes(db: Session, equipos: list[Equipo]) -> list[dict]:
    ids = [e.id for e in equipos]
    intervalos: dict[int, list] = {i: [] for i in ids}
    ultima: dict[int, datetime] = {}
    cerradas = db.query(SesionUso).filter(
        SesionUso.equipo_id.in_(ids), SesionUso.estado == "cerrada", SesionUso.fecha_fin.isnot(None)
    )
    for s in cerradas:
        ini, fin = _utc(s.fecha_inicio), _utc(s.fecha_fin)
        intervalos[s.equipo_id].append((ini, fin))
        ultima[s.equipo_id] = max(ultima.get(s.equipo_id, fin), fin)

    mantenciones: dict[int, list] = {i: [] for i in ids}
    for m in db.query(Mantenimiento).filter(Mantenimiento.equipo_id.in_(ids)):
        mantenciones[m.equipo_id].append(m)

    camaras_por_equipo: dict[int, list] = {i: [] for i in ids}
    filas = _asociaciones(db, equipo_ids=ids)
    camaras = {c.id: c for c in db.query(Camara).filter(Camara.id.in_({f.camara_id for f in filas}))}
    for fila in filas:
        camara = camaras.get(fila.camara_id)
        if camara is not None and fila.activo and roi_normalizada(fila.roi, camara):
            camaras_por_equipo[fila.equipo_id].append({"id": camara.id, "codigo": camara.codigo, "nombre": camara.nombre})

    # Estado en vivo: lo informa la camara en linea que mira la maquina (si hay varias, gana
    # la que la ve en uso).
    vivo: dict[int, dict] = {}
    for doc in _vivo_por_camara().values():
        if not _en_linea(doc):
            continue
        for m in doc.get("maquinas") or []:
            actual = vivo.get(m["equipo_id"])
            if actual is None or m["estado"] in ("en_uso", "pausa"):
                vivo[m["equipo_id"]] = m
    con_foto = {d["_id"] for d in get_mongo_db().fotos_equipos.find({}, {"_id": 1})}

    hace_7_dias = _ahora() - timedelta(days=7)
    resumenes = []
    for e in equipos:
        mantencion = _ultima_mantencion(mantenciones[e.id])
        estado_vivo_maquina = vivo.get(e.id)
        resumenes.append(
            {
                "equipo_id": e.id,
                "codigo_activo": e.codigo_activo,
                "nombre": e.nombre,
                "categoria": e.categoria,
                "marca": e.marca,
                "modelo": e.modelo,
                "estado": e.estado.value if hasattr(e.estado, "value") else e.estado,
                "zona": e.zona.nombre if e.zona else None,
                "horas_uso": _horas(intervalos[e.id]),
                "horas_ultimos_7_dias": _horas(_recortar(intervalos[e.id], hace_7_dias)),
                "sesiones": len(intervalos[e.id]),
                "ultima_sesion": ultima.get(e.id),
                "ultima_mantencion": mantencion,
                "horas_desde_mantencion": _horas(_recortar(intervalos[e.id], mantencion)) if mantencion else None,
                "incidencias_abiertas": e.incidencias_abiertas,
                "camaras": camaras_por_equipo[e.id],
                "medido_por_camara": bool(camaras_por_equipo[e.id]),
                "en_uso_ahora": (
                    estado_vivo_maquina["estado"] in ("en_uso", "pausa") if estado_vivo_maquina else None
                ),
                "estado_vivo": estado_vivo_maquina,
                "tiene_foto": e.id in con_foto,
            }
        )
    return resumenes


def resumen_maquinas(db: Session, sucursal_id: int | None = None) -> list[dict]:
    consulta = db.query(Equipo).filter(Equipo.estado != EstadoEquipo.retirado)
    if sucursal_id is not None:
        consulta = consulta.filter(Equipo.sucursal_id == sucursal_id)
    return _resumenes(db, consulta.order_by(Equipo.nombre).all())


def detalle_maquina(db: Session, equipo: Equipo, dias: int = 30) -> dict:
    resumen = _resumenes(db, [equipo])[0]

    hoy = _ahora().astimezone(ZONA_LOCAL).date()
    por_dia: dict[date, list] = {hoy - timedelta(days=i): [] for i in range(dias)}
    cerradas = [s for s in equipo.sesiones_uso if s.estado == "cerrada" and s.fecha_fin is not None]
    for s in cerradas:
        dia = _utc(s.fecha_inicio).astimezone(ZONA_LOCAL).date()
        if dia in por_dia:
            por_dia[dia].append((_utc(s.fecha_inicio), _utc(s.fecha_fin)))
    uso_diario = [
        {"fecha": dia, "horas": _horas(por_dia[dia]), "sesiones": len(por_dia[dia])} for dia in sorted(por_dia)
    ]

    sesiones = sorted(equipo.sesiones_uso, key=lambda s: _utc(s.fecha_inicio), reverse=True)[:100]
    incidencias = [
        {
            "id": i.id,
            "fecha_reporte": i.fecha_reporte,
            "tipo_falla": i.tipo_falla.nombre if i.tipo_falla else None,
            "prioridad": i.prioridad.value if hasattr(i.prioridad, "value") else i.prioridad,
            "estado": i.estado.value if hasattr(i.estado, "value") else i.estado,
            "origen": i.origen.value if hasattr(i.origen, "value") else i.origen,
            "reportado_por": i.reportado_por,
        }
        for i in equipo.incidencias[:100]
    ]
    mantenciones = (
        db.query(Mantenimiento)
        .filter(Mantenimiento.equipo_id == equipo.id)
        .order_by(Mantenimiento.fecha_inicio.desc())
        .all()
    )
    return {
        "resumen": resumen,
        "uso_diario": uso_diario,
        "sesiones": [
            {
                "id": s.id,
                "fecha_inicio": s.fecha_inicio,
                "fecha_fin": s.fecha_fin,
                "duracion_segundos": s.duracion_segundos,
                "estado": s.estado,
                "origen": s.origen.value if hasattr(s.origen, "value") else s.origen,
                "confianza_promedio": float(s.confianza_promedio) if s.confianza_promedio is not None else None,
                "camara_id": s.camara_id,
            }
            for s in sesiones
        ],
        "incidencias": incidencias,
        "mantenciones": [
            {
                "id": m.id,
                "tipo": m.tipo,
                "tecnico": m.tecnico,
                "descripcion": m.descripcion,
                "costo_total": float(m.costo_total) if m.costo_total is not None else None,
                "fecha_inicio": m.fecha_inicio,
                "fecha_fin": m.fecha_fin,
            }
            for m in mantenciones
        ],
    }


# ---------------------------------------------------------------- fotos de referencia


def guardar_foto(equipo_id: int, contenido: bytes, *, origen: str, camara_id: int | None = None) -> dict:
    jpeg, ancho, alto = _a_jpeg(contenido, MAX_LADO_FOTO)
    get_mongo_db().fotos_equipos.replace_one(
        {"_id": equipo_id},
        {
            "imagen": Binary(jpeg),
            "content_type": "image/jpeg",
            "ancho": ancho,
            "alto": alto,
            "origen": origen,
            "camara_id": camara_id,
            "actualizado": _ahora(),
        },
        upsert=True,
    )
    return {"ancho": ancho, "alto": alto, "origen": origen}


def leer_foto(equipo_id: int) -> bytes | None:
    doc = get_mongo_db().fotos_equipos.find_one({"_id": equipo_id}, {"imagen": 1})
    return bytes(doc["imagen"]) if doc and doc.get("imagen") else None


def foto_desde_camara(db: Session, equipo: Equipo, camara_id: int | None = None) -> dict:
    """Recorta la zona de la maquina desde el ultimo cuadro de la camara (con margen)."""
    filas = [f for f in _asociaciones(db, equipo_ids=[equipo.id]) if camara_id in (None, f.camara_id)]
    for fila in filas:
        camara = db.get(Camara, fila.camara_id)
        roi = roi_normalizada(fila.roi, camara)
        cuadro = leer_cuadro(fila.camara_id)
        if roi is None or cuadro is None:
            continue
        imagen = Image.open(io.BytesIO(cuadro))
        xs, ys = [p[0] for p in roi], [p[1] for p in roi]
        # La zona es donde se apoyan los pies: la maquina sube por encima de ella, asi que el
        # recorte se corre hacia arriba. Tiene un tamano minimo para que se vea el contexto
        # (en una camara chica la zona puede medir pocos pixeles).
        ancho = max((max(xs) - min(xs)) * 1.5, 0.30)
        alto = max((max(ys) - min(ys)) * 2.2, 0.40)
        centro_x = (min(xs) + max(xs)) / 2
        centro_y = max(ys) - alto * 0.55
        x1 = min(max(0.0, centro_x - ancho / 2), 1.0 - ancho)
        y1 = min(max(0.0, centro_y - alto / 2), 1.0 - alto)
        caja = (
            int(max(0.0, x1) * imagen.width),
            int(max(0.0, y1) * imagen.height),
            int(min(1.0, x1 + ancho) * imagen.width),
            int(min(1.0, y1 + alto) * imagen.height),
        )
        salida = io.BytesIO()
        imagen.crop(caja).save(salida, format="JPEG", quality=88)
        return guardar_foto(equipo.id, salida.getvalue(), origen="camara", camara_id=fila.camara_id)
    raise LookupError("Ninguna camara tiene una imagen y una zona definida para esta maquina.")
