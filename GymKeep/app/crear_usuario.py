"""Crea una cuenta o restablece su clave desde la consola (la primera cuenta administradora).

    docker exec -e GK_CLAVE=1234 gymkeep_api python -m app.crear_usuario --run 12.345.678-5 --nombre "Ana Perez" --rol admin

Si no se pasa GK_CLAVE, la clave se pide por teclado (no se muestra). Si la cuenta ya existe,
se le restablece la clave, se reactiva y se actualiza nombre y rol.
"""

import argparse
import getpass
import os
import sys

from app.core import auth
from app.core.arranque import asegurar_tablas
from app.core.database import SessionLocal
from app.crud import usuario as crud_usuario
from app.models.auth import ROL_ADMIN, ROLES


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Crear o restablecer una cuenta de GymKeep.")
    parser.add_argument("--run", required=True, help="RUN chileno, con o sin puntos y guion.")
    parser.add_argument("--nombre", required=True)
    parser.add_argument("--rol", choices=sorted(ROLES), default=ROL_ADMIN)
    args = parser.parse_args(argv)

    run = auth.normalizar_run(args.run)
    if run is None:
        print("El RUN no es valido (revisa el digito verificador).", file=sys.stderr)
        return 2
    nombre = args.nombre.strip()
    if len(nombre) < 2:
        print("El nombre es muy corto.", file=sys.stderr)
        return 2

    clave = os.environ.get("GK_CLAVE") or getpass.getpass("Clave (solo numeros, 4 a 8 digitos): ")
    if not auth.clave_valida(clave):
        print("La clave debe tener solo numeros, de 4 a 8 digitos.", file=sys.stderr)
        return 2

    asegurar_tablas()
    db = SessionLocal()
    try:
        existente = crud_usuario.get_por_run(db, run)
        if existente is None:
            crud_usuario.crear(db, run, nombre, args.rol, clave)
            print(f"Cuenta creada: {run} ({args.rol}).")
        else:
            existente.nombre = nombre
            existente.rol = args.rol
            existente.activo = True
            db.commit()
            crud_usuario.cambiar_clave(db, existente, clave)
            print(f"La cuenta {run} ya existia: se actualizo y se restablecio su clave.")
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
