from typing import Optional

from sqlalchemy.orm import Session

from app.models.gymkeep import TipoFalla


def list_tipos_falla(db: Session, solo_reporte_qr: bool = False):
    query = db.query(TipoFalla).filter(TipoFalla.activa.is_(True))
    if solo_reporte_qr:
        query = query.filter(TipoFalla.permite_reporte_qr.is_(True))
    return query.order_by(TipoFalla.id).all()


def get_tipo_falla_by_codigo(db: Session, codigo: str) -> Optional[TipoFalla]:
    return db.query(TipoFalla).filter(TipoFalla.codigo == codigo, TipoFalla.activa.is_(True)).first()
