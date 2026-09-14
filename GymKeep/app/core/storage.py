import io
from uuid import UUID

import boto3

from app.core.config import settings

s3 = boto3.client(
    "s3",
    endpoint_url=settings.s3_endpoint_url,
    aws_access_key_id=settings.s3_access_key,
    aws_secret_access_key=settings.s3_secret_key,
    region_name=settings.s3_region,
)


def subir_evidencia(
    contenido: bytes,
    *,
    event_uuid: UUID,
    extension: str = "jpg",
    content_type: str = "image/jpeg",
) -> str:
    """
    Guarda snapshot/clip en MinIO/S3 y retorna una URI estable.
    La base de datos guarda esta URI, no los bytes del archivo.
    """
    key = f"eventos/{event_uuid}.{extension.lstrip('.')}"
    s3.put_object(
        Bucket=settings.s3_bucket,
        Key=key,
        Body=io.BytesIO(contenido),
        ContentType=content_type,
    )
    return f"s3://{settings.s3_bucket}/{key}"
