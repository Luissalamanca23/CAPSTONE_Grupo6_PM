from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.ai_event import EventoIACreate
from app.services import ai_event_service

router = APIRouter()


@router.post("/", status_code=status.HTTP_201_CREATED)
def registrar_evento_ia(evento_in: EventoIACreate, db: Session = Depends(get_db)):
    """Recibe un evento del pipeline de camara/IA (ver GymKeep_BDD_Completa/README.md,
    seccion 'detección != uso'). El documento completo se guarda en MongoDB y un resumen
    consultable queda en `eventos_ia_resumen` (puente Postgres <-> Mongo).

    Nota: el modulo de vision computacional que produce estos eventos (YOLO/OpenCV) todavia
    no esta implementado en este Capstone; este endpoint deja la integracion lista para
    cuando ese pipeline exista, y puede probarse enviando el JSON de ejemplo incluido en
    GymKeep_BDD_Completa/examples/evento_inicio_uso.json."""
    resumen = ai_event_service.guardar_evento_ia(db, evento_in)
    return {
        "id": resumen.id,
        "evento_uuid": str(resumen.evento_uuid),
        "tipo_evento": resumen.tipo_evento,
        "procesado": resumen.procesado,
    }
