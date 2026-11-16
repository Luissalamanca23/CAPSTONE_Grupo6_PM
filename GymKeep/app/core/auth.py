"""Inicio de sesion: RUN chileno, clave numerica, hash de la clave y token de sesion.

Sin dependencias nuevas (solo biblioteca estandar):
- La clave se guarda con scrypt (sal aleatoria por usuario).
- La sesion es un token firmado HS256 (formato JWT) que viaja en una cookie HttpOnly. El secreto
  de firma sale de AUTH_SECRET o, si no esta definido, se genera una vez y queda en la tabla
  `auth_config` (asi sobrevive a los reinicios y a las copias de la base).
"""

import base64
import hashlib
import hmac
import json
import re
import secrets
import time
from typing import Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.auth import ConfigAuth

COOKIE_SESION = "gk_sesion"
CLAVE_RE = re.compile(r"^\d{4,8}$")
_SCRYPT_N, _SCRYPT_R, _SCRYPT_P = 2**14, 8, 1

# ------------------------------------------------------------------------------------ RUN


def _digito_verificador(cuerpo: str) -> str:
    suma, factor = 0, 2
    for digito in reversed(cuerpo):
        suma += int(digito) * factor
        factor = 2 if factor == 7 else factor + 1
    resto = 11 - (suma % 11)
    return "0" if resto == 11 else "K" if resto == 10 else str(resto)


def normalizar_run(texto: Optional[str]) -> Optional[str]:
    """'12.345.678-5', '12345678 5' o '12345678k' -> '12345678-5' / '12345678-K'.
    Devuelve None si no es un RUN valido (largo o digito verificador)."""
    if not texto:
        return None
    limpio = re.sub(r"[\s.\-]", "", texto).upper()
    if not re.fullmatch(r"\d{7,8}[0-9K]", limpio):
        return None
    cuerpo, dv = limpio[:-1], limpio[-1]
    if _digito_verificador(cuerpo) != dv:
        return None
    return f"{cuerpo}-{dv}"


def clave_valida(clave: Optional[str]) -> bool:
    return bool(clave) and CLAVE_RE.fullmatch(clave) is not None


# ------------------------------------------------------------------------------- hash clave


def hashear_clave(clave: str) -> str:
    sal = secrets.token_bytes(16)
    derivada = hashlib.scrypt(clave.encode(), salt=sal, n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P, dklen=32)
    return f"scrypt${_SCRYPT_N}${_SCRYPT_R}${_SCRYPT_P}${sal.hex()}${derivada.hex()}"


def verificar_clave(clave: str, almacenado: str) -> bool:
    try:
        _, n, r, p, sal, esperado = almacenado.split("$")
        derivada = hashlib.scrypt(clave.encode(), salt=bytes.fromhex(sal), n=int(n), r=int(r), p=int(p), dklen=32)
        return hmac.compare_digest(derivada, bytes.fromhex(esperado))
    except (ValueError, TypeError):
        return False


# Hash de relleno: al probar un RUN que no existe tambien se calcula un scrypt, para que el
# tiempo de respuesta no delate si el RUN esta registrado.
HASH_FALSO = hashear_clave("0000")

# ----------------------------------------------------------------------------- secreto/token

_secreto_cache: Optional[bytes] = None


def _secreto(db: Session) -> bytes:
    global _secreto_cache
    if settings.auth_secret:
        return settings.auth_secret.encode()
    if _secreto_cache is not None:
        return _secreto_cache
    fila = db.get(ConfigAuth, "secreto")
    if fila is None:
        db.add(ConfigAuth(clave="secreto", valor=secrets.token_hex(32)))
        try:
            db.commit()
        except IntegrityError:  # otro proceso la creo a la vez
            db.rollback()
        fila = db.get(ConfigAuth, "secreto")
    _secreto_cache = fila.valor.encode()
    return _secreto_cache


def reiniciar_cache_secreto() -> None:
    """Para los tests."""
    global _secreto_cache
    _secreto_cache = None


def _b64(datos: bytes) -> str:
    return base64.urlsafe_b64encode(datos).rstrip(b"=").decode()


def _b64_inv(texto: str) -> bytes:
    return base64.urlsafe_b64decode(texto + "=" * (-len(texto) % 4))


def crear_token(db: Session, usuario_id: int, sesion_version: int, horas: Optional[float] = None) -> tuple[str, int]:
    """Devuelve (token, segundos de vigencia)."""
    vigencia = int((horas if horas is not None else settings.session_hours) * 3600)
    ahora = int(time.time())
    cabecera = _b64(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode())
    cuerpo = _b64(json.dumps({"sub": usuario_id, "sv": sesion_version, "iat": ahora, "exp": ahora + vigencia}, separators=(",", ":")).encode())
    firma = hmac.new(_secreto(db), f"{cabecera}.{cuerpo}".encode(), hashlib.sha256).digest()
    return f"{cabecera}.{cuerpo}.{_b64(firma)}", vigencia


def leer_token(db: Session, token: Optional[str]) -> Optional[dict]:
    """Datos del token si la firma es valida y no vencio; None en cualquier otro caso."""
    if not token:
        return None
    try:
        cabecera, cuerpo, firma = token.split(".")
        esperada = hmac.new(_secreto(db), f"{cabecera}.{cuerpo}".encode(), hashlib.sha256).digest()
        if not hmac.compare_digest(esperada, _b64_inv(firma)):
            return None
        if json.loads(_b64_inv(cabecera)).get("alg") != "HS256":
            return None
        datos = json.loads(_b64_inv(cuerpo))
        if int(datos["exp"]) < time.time():
            return None
        return datos
    except (ValueError, KeyError, TypeError, json.JSONDecodeError):
        return None
