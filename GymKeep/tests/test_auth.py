"""Inicio de sesion y control de acceso de la API."""

import re

import pytest
from fastapi.routing import APIRoute

from app.core import auth
from app.core.config import settings
from app.crud import usuario as crud_usuario
from app.main import app
from app.models.auth import Usuario
from tests.conftest import CLAVE_ADMIN, CLAVE_TECNICO, RUN_ADMIN, RUN_TECNICO, iniciar_sesion

API = "/api/v1"


# ----------------------------------------------------------------------------- RUN y clave


@pytest.mark.parametrize(
    "escrito, canonico",
    [
        ("12.345.678-5", "12345678-5"),
        ("12345678-5", "12345678-5"),
        ("123456785", "12345678-5"),
        (" 12 345 678 5 ", "12345678-5"),
        ("11.111.111-1", "11111111-1"),
        ("9.999.999-3", "9999999-3"),
    ],
)
def test_normalizar_run_acepta_las_formas_habituales(escrito, canonico):
    assert auth.normalizar_run(escrito) == canonico


@pytest.mark.parametrize("escrito", ["", None, "12345678-4", "abc", "1234", "123456789012", "12345678-X"])
def test_normalizar_run_rechaza_lo_invalido(escrito):
    assert auth.normalizar_run(escrito) is None


def test_run_con_k():
    # 6.000.002 -> suma=2*2+0+0+0+0+6*7... se comprueba que el DV 'K' se acepta en mayuscula o minuscula.
    cuerpo = next(str(n) for n in range(10_000_000, 10_000_200) if auth._digito_verificador(str(n)) == "K")
    assert auth.normalizar_run(f"{cuerpo}-k") == f"{cuerpo}-K"
    assert auth.normalizar_run(f"{cuerpo}K") == f"{cuerpo}-K"


@pytest.mark.parametrize("clave, valida", [("1234", True), ("12345678", True), ("123", False), ("123456789", False), ("12a4", False), ("", False), (" 1234", False)])
def test_clave_numerica_de_4_a_8_digitos(clave, valida):
    assert auth.clave_valida(clave) is valida


def test_hash_de_clave_no_guarda_la_clave_y_se_verifica():
    h = auth.hashear_clave("1234")
    assert "1234" not in h and h != auth.hashear_clave("1234")  # sal distinta cada vez
    assert auth.verificar_clave("1234", h)
    assert not auth.verificar_clave("1235", h)
    assert not auth.verificar_clave("1234", "basura")


# ----------------------------------------------------------------------------- login


def test_estado_indica_si_hay_cuentas(client_anonimo, db_session):
    assert client_anonimo.get(f"{API}/auth/estado").json() == {"hay_usuarios": False}
    crud_usuario.crear(db_session, RUN_ADMIN, "Admin", "admin", CLAVE_ADMIN)
    assert client_anonimo.get(f"{API}/auth/estado").json() == {"hay_usuarios": True}


def test_login_correcto_entrega_cookie_httponly_y_los_datos_de_la_persona(client_anonimo, admin):
    r = client_anonimo.post(f"{API}/auth/login", json={"run": "12.345.678-5", "clave": CLAVE_ADMIN})
    assert r.status_code == 200
    cuerpo = r.json()
    assert cuerpo["run"] == RUN_ADMIN and cuerpo["rol"] == "admin" and cuerpo["nombre"] == "Admin de Prueba"
    assert "clave" not in cuerpo and "clave_hash" not in cuerpo
    cookie = r.headers["set-cookie"].lower()
    assert "gk_sesion=" in cookie and "httponly" in cookie and "samesite=lax" in cookie
    assert "max-age=86400" in cookie  # 24 h
    assert client_anonimo.get(f"{API}/auth/me").json()["run"] == RUN_ADMIN


def test_la_cookie_es_secure_cuando_se_entra_por_https(client_anonimo, admin):
    r = client_anonimo.post(
        f"{API}/auth/login", json={"run": RUN_ADMIN, "clave": CLAVE_ADMIN}, headers={"X-Forwarded-Proto": "https"}
    )
    assert "secure" in r.headers["set-cookie"].lower()


def test_credenciales_incorrectas_responden_igual_exista_o_no_el_run(client_anonimo, admin):
    malos = [
        {"run": RUN_ADMIN, "clave": "9999"},
        {"run": "11111111-1", "clave": "1234"},  # no existe
        {"run": "12345678-4", "clave": "1234"},  # digito verificador malo
        {"run": "hola", "clave": "1234"},
    ]
    respuestas = [client_anonimo.post(f"{API}/auth/login", json=m) for m in malos]
    assert all(r.status_code == 401 for r in respuestas)
    assert len({r.json()["detail"] for r in respuestas}) == 1
    assert all(r.headers["www-authenticate"] == "GymKeep-Sesion" for r in respuestas)
    assert "set-cookie" not in respuestas[0].headers


def test_la_cuenta_se_bloquea_tras_5_fallos_y_no_deja_entrar_ni_con_la_clave_buena(client_anonimo, admin):
    for _ in range(5):
        assert client_anonimo.post(f"{API}/auth/login", json={"run": RUN_ADMIN, "clave": "0000"}).status_code == 401
    r = client_anonimo.post(f"{API}/auth/login", json={"run": RUN_ADMIN, "clave": CLAVE_ADMIN})
    assert r.status_code == 429 and "min" in r.json()["detail"]
    assert client_anonimo.get(f"{API}/auth/me").status_code == 401


def test_el_bloqueo_expira(client_anonimo, admin, db_session):
    from datetime import timedelta

    for _ in range(5):
        client_anonimo.post(f"{API}/auth/login", json={"run": RUN_ADMIN, "clave": "0000"})
    usuario = db_session.get(Usuario, admin.id)
    usuario.bloqueado_hasta = crud_usuario.ahora() - timedelta(seconds=1)
    db_session.commit()
    assert client_anonimo.post(f"{API}/auth/login", json={"run": RUN_ADMIN, "clave": CLAVE_ADMIN}).status_code == 200


def test_un_acceso_correcto_reinicia_los_fallos(client_anonimo, admin, db_session):
    for _ in range(4):
        client_anonimo.post(f"{API}/auth/login", json={"run": RUN_ADMIN, "clave": "0000"})
    iniciar_sesion(client_anonimo, RUN_ADMIN, CLAVE_ADMIN)
    assert db_session.get(Usuario, admin.id).intentos_fallidos == 0


def test_limite_de_intentos_por_ip(client_anonimo, admin):
    from app.api.v1 import auth as auth_api

    auth_api.limitador_login_ip.maximo = 3
    try:
        codigos = [client_anonimo.post(f"{API}/auth/login", json={"run": "11111111-1", "clave": "1234"}).status_code for _ in range(5)]
    finally:
        auth_api.limitador_login_ip.maximo = 30
    assert codigos == [401, 401, 401, 429, 429]


def test_cuenta_desactivada_no_puede_entrar(client_anonimo, admin, db_session):
    db_session.get(Usuario, admin.id).activo = False
    db_session.commit()
    assert client_anonimo.post(f"{API}/auth/login", json={"run": RUN_ADMIN, "clave": CLAVE_ADMIN}).status_code == 401


def test_logout_cierra_la_sesion(client):
    assert client.get(f"{API}/auth/me").status_code == 200
    assert client.post(f"{API}/auth/logout").status_code == 204
    assert client.get(f"{API}/auth/me").status_code == 401


# ----------------------------------------------------------------------------- sesion


def test_una_cookie_alterada_o_inventada_no_vale(client_anonimo, admin):
    iniciar_sesion(client_anonimo, RUN_ADMIN, CLAVE_ADMIN)
    token = client_anonimo.cookies.get(auth.COOKIE_SESION)
    cabecera, cuerpo, firma = token.split(".")
    alterado = ".".join([cabecera, cuerpo[:-2] + ("AA" if not cuerpo.endswith("AA") else "BB"), firma])
    for falso in (alterado, "x.y.z", "basura", token + "x"):
        client_anonimo.cookies.clear()
        client_anonimo.cookies.set(auth.COOKIE_SESION, falso)
        assert client_anonimo.get(f"{API}/auth/me").status_code == 401


def test_un_token_vencido_no_vale(client_anonimo, admin, db_session):
    token, _ = auth.crear_token(db_session, admin.id, admin.sesion_version, horas=-1)
    client_anonimo.cookies.set(auth.COOKIE_SESION, token)
    assert client_anonimo.get(f"{API}/auth/me").status_code == 401


def test_la_sesion_dura_lo_configurado(db_session, admin, monkeypatch):
    monkeypatch.setattr(settings, "session_hours", 24)
    assert auth.crear_token(db_session, admin.id, 0)[1] == 24 * 3600


def test_desactivar_la_cuenta_cierra_sus_sesiones(client_anonimo, admin, tecnico, db_session):
    iniciar_sesion(client_anonimo, RUN_TECNICO, CLAVE_TECNICO)
    assert client_anonimo.get(f"{API}/auth/me").status_code == 200
    tecnico.activo = False
    db_session.commit()
    assert client_anonimo.get(f"{API}/auth/me").status_code == 401


def test_cambiar_la_clave_cierra_las_otras_sesiones_pero_no_la_actual(client, app_otro_navegador=None):
    from fastapi.testclient import TestClient

    # Segunda sesion de la misma cuenta (otro navegador).
    with TestClient(app) as otro:
        iniciar_sesion(otro, RUN_ADMIN, CLAVE_ADMIN)
        assert otro.get(f"{API}/auth/me").status_code == 200

        r = client.post(f"{API}/auth/cambiar-clave", json={"clave_actual": CLAVE_ADMIN, "clave_nueva": "5678"})
        assert r.status_code == 204
        assert client.get(f"{API}/auth/me").status_code == 200  # la que cambio la clave sigue
        assert otro.get(f"{API}/auth/me").status_code == 401  # la otra se cerro

    assert client.post(f"{API}/auth/login", json={"run": RUN_ADMIN, "clave": CLAVE_ADMIN}).status_code == 401
    assert client.post(f"{API}/auth/login", json={"run": RUN_ADMIN, "clave": "5678"}).status_code == 200


def test_cambiar_la_clave_pide_la_actual_y_una_nueva_valida(client):
    url = f"{API}/auth/cambiar-clave"
    assert client.post(url, json={"clave_actual": "0000", "clave_nueva": "5678"}).status_code == 400
    assert client.post(url, json={"clave_actual": CLAVE_ADMIN, "clave_nueva": "12"}).status_code == 422
    assert client.post(url, json={"clave_actual": CLAVE_ADMIN, "clave_nueva": "abcd"}).status_code == 422


# ----------------------------------------------------------------------------- todo exige sesion


PUBLICAS = {
    ("GET", "/equipamiento/qr/{token}"),
    ("GET", "/incidencias/tipos-falla"),
    ("POST", "/incidencias/reporte-qr"),
    ("POST", "/auth/login"),
    ("POST", "/auth/logout"),
    ("GET", "/auth/estado"),
}


def _rutas_de_la_api():
    for ruta in app.routes:
        if isinstance(ruta, APIRoute) and ruta.path.startswith(API):
            for metodo in ruta.methods - {"HEAD", "OPTIONS"}:
                yield metodo, ruta.path[len(API):]


def test_la_lista_de_rutas_publicas_es_exactamente_la_esperada():
    existentes = set(_rutas_de_la_api())
    assert PUBLICAS <= existentes
    from app.core.seguridad import RUTAS_PUBLICAS

    assert len(RUTAS_PUBLICAS) == len(PUBLICAS)


def test_sin_sesion_cada_ruta_de_la_api_responde_401_salvo_las_publicas(client_anonimo):
    rutas = sorted(set(_rutas_de_la_api()))
    assert len(rutas) > 40  # que el recorrido realmente cubra la API
    sin_proteger = []
    for metodo, ruta in rutas:
        if (metodo, ruta) in PUBLICAS:
            continue
        url = API + re.sub(r"\{[^}]+\}", "1", ruta)
        r = client_anonimo.request(metodo, url)
        if r.status_code != 401 or r.headers.get("www-authenticate") != "GymKeep-Sesion":
            sin_proteger.append((metodo, ruta, r.status_code))
    assert not sin_proteger, sin_proteger


def test_el_stream_las_fotos_y_el_cuadro_tambien_piden_sesion(client_anonimo):
    for ruta in ("/vision/camaras/1/stream", "/vision/camaras/1/cuadro", "/vision/maquinas/1/foto", "/incidencias/1/foto"):
        assert client_anonimo.get(API + ruta).status_code == 401, ruta


def test_el_formulario_publico_del_qr_funciona_sin_sesion(client_anonimo, db_session):
    assert client_anonimo.get(f"{API}/equipamiento/qr/no-existe").status_code == 404
    assert client_anonimo.post(f"{API}/incidencias/reporte-qr", json={}).status_code == 422


def test_sin_sesion_el_catalogo_de_fallas_solo_muestra_las_del_reporte_por_qr(client_anonimo):
    anonimo = client_anonimo.get(f"{API}/incidencias/tipos-falla", params={"solo_reporte_qr": "false"})
    codigos = {t["codigo"] for t in anonimo.json()}
    assert "OTRO" in codigos and "MOVIMIENTO_ANOMALO" not in codigos


def test_con_sesion_el_catalogo_de_fallas_esta_completo(client):
    codigos = {t["codigo"] for t in client.get(f"{API}/incidencias/tipos-falla").json()}
    assert "MOVIMIENTO_ANOMALO" in codigos


# ----------------------------------------------------------------------------- roles


def test_un_tecnico_puede_usar_el_panel_pero_no_borrar(client_tecnico):
    assert client_tecnico.get(f"{API}/equipamiento/").status_code == 200
    assert client_tecnico.delete(f"{API}/equipamiento/999").status_code == 403


def test_un_administrador_si_puede_borrar(client):
    assert client.delete(f"{API}/equipamiento/999").status_code != 403


def test_un_tecnico_no_administra_usuarios(client_tecnico):
    assert client_tecnico.get(f"{API}/auth/usuarios").status_code == 403
    cuerpo = {"run": "11111111-1", "nombre": "Otra Persona", "rol": "tecnico", "clave": "1234"}
    assert client_tecnico.post(f"{API}/auth/usuarios", json=cuerpo).status_code == 403
    assert client_tecnico.patch(f"{API}/auth/usuarios/1", json={"rol": "admin"}).status_code == 403


# ----------------------------------------------------------------------------- origen (CSRF)


def test_un_sitio_ajeno_no_puede_usar_la_sesion_para_modificar_datos(client):
    r = client.post(f"{API}/empresas/", json={}, headers={"Origin": "https://sitio-malo.example"})
    assert r.status_code == 403
    r = client.post(f"{API}/empresas/", json={}, headers={"Origin": "http://localhost:5173"})
    assert r.status_code != 403
    r = client.post(f"{API}/empresas/", json={})  # sin Origin (herramientas, mismo sitio antiguo)
    assert r.status_code != 403


def test_el_mismo_sitio_publico_puede_modificar_datos(client):
    r = client.post(
        f"{API}/empresas/", json={}, headers={"Origin": "https://pc.ejemplo.ts.net", "Host": "pc.ejemplo.ts.net"}
    )
    assert r.status_code != 403


def test_cors_permite_credenciales_solo_a_origenes_de_confianza(client_anonimo):
    ok = client_anonimo.options(
        f"{API}/auth/login",
        headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "POST"},
    )
    assert ok.headers.get("access-control-allow-origin") == "http://localhost:5173"
    assert ok.headers.get("access-control-allow-credentials") == "true"
    malo = client_anonimo.options(
        f"{API}/auth/login",
        headers={"Origin": "https://sitio-malo.example", "Access-Control-Request-Method": "POST"},
    )
    assert "access-control-allow-origin" not in malo.headers


# ----------------------------------------------------------------------------- pipeline


def test_el_pipeline_entra_con_su_clave_pero_no_borra_ni_administra(client_anonimo, monkeypatch):
    from app.services import vision_service

    # Sin esto el listado de camaras consulta un MongoDB real (y falla si no hay uno levantado).
    monkeypatch.setattr(vision_service, "_vivo_por_camara", lambda: {})
    monkeypatch.setattr(settings, "vision_pipeline_key", "clave-de-servicio")
    clave = {"X-Pipeline-Key": "clave-de-servicio"}
    assert client_anonimo.get(f"{API}/vision/camaras", headers=clave).status_code == 200
    assert client_anonimo.get(f"{API}/vision/camaras", headers={"X-Pipeline-Key": "otra"}).status_code == 401
    assert client_anonimo.get(f"{API}/vision/camaras").status_code == 401
    assert client_anonimo.delete(f"{API}/equipamiento/1", headers=clave).status_code == 403
    assert client_anonimo.get(f"{API}/auth/usuarios", headers=clave).status_code == 403


def test_sin_clave_configurada_la_cabecera_del_pipeline_no_abre_nada(client_anonimo, monkeypatch):
    monkeypatch.setattr(settings, "vision_pipeline_key", "")
    assert client_anonimo.get(f"{API}/vision/camaras", headers={"X-Pipeline-Key": ""}).status_code == 401


# ----------------------------------------------------------------------------- usuarios (admin)


def test_el_administrador_crea_y_lista_cuentas(client, db_session):
    cuerpo = {"run": "11.111.111-1", "nombre": "  Ana Perez ", "rol": "tecnico", "clave": "2468"}
    r = client.post(f"{API}/auth/usuarios", json=cuerpo)
    assert r.status_code == 201
    assert r.json()["run"] == "11111111-1" and r.json()["nombre"] == "Ana Perez" and r.json()["rol"] == "tecnico"
    assert "clave" not in r.json() and "clave_hash" not in r.json()
    guardado = crud_usuario.get_por_run(db_session, "11111111-1")
    assert guardado.clave_hash != "2468" and auth.verificar_clave("2468", guardado.clave_hash)
    assert {u["run"] for u in client.get(f"{API}/auth/usuarios").json()} == {RUN_ADMIN, "11111111-1"}
    # La cuenta nueva puede entrar.
    assert client.post(f"{API}/auth/login", json={"run": "11111111-1", "clave": "2468"}).status_code == 200


@pytest.mark.parametrize(
    "cambio, codigo",
    [
        ({"run": "12345678-4"}, 422),
        ({"run": "xx"}, 422),
        ({"clave": "123"}, 422),
        ({"clave": "12ab"}, 422),
        ({"rol": "dios"}, 422),
        ({"nombre": "A"}, 422),
        ({"run": RUN_ADMIN}, 409),
    ],
)
def test_crear_cuenta_valida_los_datos(client, cambio, codigo):
    cuerpo = {"run": "11111111-1", "nombre": "Ana Perez", "rol": "tecnico", "clave": "2468", **cambio}
    assert client.post(f"{API}/auth/usuarios", json=cuerpo).status_code == codigo


def test_no_se_puede_dejar_el_sistema_sin_administrador(client, admin):
    url = f"{API}/auth/usuarios/{admin.id}"
    assert client.patch(url, json={"activo": False}).status_code == 400
    assert client.patch(url, json={"rol": "tecnico"}).status_code == 400
    assert client.patch(url, json={"clave": "9999"}).status_code == 400  # su clave se cambia desde su perfil
    assert client.patch(url, json={"nombre": "Nuevo Nombre"}).status_code == 200


def test_el_ultimo_administrador_no_se_puede_degradar_ni_desactivar(client, db_session, admin):
    otro = crud_usuario.crear(db_session, "11111111-1", "Otro Admin", "admin", "1111")
    assert client.patch(f"{API}/auth/usuarios/{otro.id}", json={"rol": "tecnico"}).status_code == 200
    assert crud_usuario.contar_admins_activos(db_session) == 1


def test_desactivar_y_restablecer_la_clave_de_otra_cuenta(client, client_anonimo, tecnico):
    from fastapi.testclient import TestClient

    with TestClient(app) as navegador_tecnico:
        iniciar_sesion(navegador_tecnico, RUN_TECNICO, CLAVE_TECNICO)

        r = client.patch(f"{API}/auth/usuarios/{tecnico.id}", json={"clave": "7777"})
        assert r.status_code == 200
        assert navegador_tecnico.get(f"{API}/auth/me").status_code == 401  # su sesion se cerro
        assert client.post(f"{API}/auth/login", json={"run": RUN_TECNICO, "clave": CLAVE_TECNICO}).status_code == 401
        assert client.post(f"{API}/auth/login", json={"run": RUN_TECNICO, "clave": "7777"}).status_code == 200

    # (el cliente de arriba cambio de sesion al entrar como tecnico: se vuelve a entrar como admin)
    iniciar_sesion(client, RUN_ADMIN, CLAVE_ADMIN)
    assert client.patch(f"{API}/auth/usuarios/{tecnico.id}", json={"activo": False}).json()["activo"] is False
    assert client.post(f"{API}/auth/login", json={"run": RUN_TECNICO, "clave": "7777"}).status_code == 401
    assert client.patch(f"{API}/auth/usuarios/{tecnico.id}", json={"activo": True}).json()["activo"] is True


def test_cuenta_inexistente(client):
    assert client.patch(f"{API}/auth/usuarios/99999", json={"nombre": "Nadie Aqui"}).status_code == 404


def test_el_secreto_de_sesion_se_guarda_y_se_reutiliza(client_anonimo, admin, db_session):
    from app.models.auth import ConfigAuth

    iniciar_sesion(client_anonimo, RUN_ADMIN, CLAVE_ADMIN)
    secreto = db_session.get(ConfigAuth, "secreto").valor
    assert len(secreto) >= 32
    auth.reiniciar_cache_secreto()  # como si la API se reiniciara
    assert client_anonimo.get(f"{API}/auth/me").status_code == 200
    assert db_session.get(ConfigAuth, "secreto").valor == secreto


def test_con_auth_secret_en_el_entorno_no_se_usa_la_base(db_session, admin, monkeypatch):
    monkeypatch.setattr(settings, "auth_secret", "secreto-de-entorno")
    auth.reiniciar_cache_secreto()
    token, _ = auth.crear_token(db_session, admin.id, 0)
    assert auth.leer_token(db_session, token)["sub"] == admin.id
    monkeypatch.setattr(settings, "auth_secret", "otro-secreto")
    assert auth.leer_token(db_session, token) is None


def test_quien_escanea_el_qr_solo_ve_los_datos_minimos_de_la_maquina(client, sucursal_id):
    creado = client.post(
        f"{API}/equipamiento/",
        json={
            "sucursal_id": sucursal_id,
            "codigo_activo": "EQ-9001",
            "nombre": "Cinta de correr",
            "numero_serie": "SERIE-SECRETA",
            "observaciones": "Nota interna",
        },
    ).json()
    token = creado["qr_activo"]["token"]
    client.cookies.clear()  # como alguien que escanea el QR con su celular, sin sesion

    publico = client.get(f"{API}/equipamiento/qr/{token}")
    assert publico.status_code == 200
    assert publico.json()["nombre"] == "Cinta de correr"
    assert set(publico.json()) == {"nombre", "categoria", "estado", "zona"}
    assert "SERIE-SECRETA" not in publico.text and "Nota interna" not in publico.text


def test_la_api_envia_cabeceras_de_seguridad_y_no_guarda_en_cache_la_sesion(client_anonimo):
    r = client_anonimo.get(f"{API}/auth/estado")
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["x-frame-options"] == "DENY"
    assert r.headers["cache-control"] == "no-store"
    assert client_anonimo.get("/health").headers["x-content-type-options"] == "nosniff"
