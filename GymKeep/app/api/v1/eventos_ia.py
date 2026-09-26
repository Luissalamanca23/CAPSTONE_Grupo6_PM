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

    Los eventos de uso se consolidan en `sesiones_uso`: `inicio_uso` abre una sesion,
    `uso_en_curso` la sostiene y `fin_uso` la cierra con su duracion. Los produce el
    modulo de vision `GymKeep/vision/` (YOLO + ByteTrack), y tambien puede probarse con el
    JSON de ejemplo de GymKeep_BDD_Completa/examples/evento_inicio_uso.json.

    Es idempotente por `event_uuid`: reenviar el mismo evento devuelve el ya guardado."""
    resumen = ai_event_service.guardar_evento_ia(db, evento_in)
    return {
        "id": resumen.id,
        "evento_uuid": str(resumen.evento_uuid),
        "tipo_evento": resumen.tipo_evento,
        "procesado": resumen.procesado,
        "sesion_uso_id": resumen.sesion_uso_id,
    }
