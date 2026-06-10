import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from fastapi import Request, HTTPException
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
import hashlib

SECRET_KEY = "retache-secret-key-2025-zamora-michoacan"
serializer = URLSafeTimedSerializer(SECRET_KEY)


def hash_contrasena(contrasena: str) -> str:
    return hashlib.sha256(contrasena.encode()).hexdigest()


def crear_sesion(datos: dict) -> str:
    return serializer.dumps(datos)


def leer_sesion(token: str) -> dict:
    try:
        return serializer.loads(token, max_age=86400)
    except SignatureExpired:
        return None
    except BadSignature:
        return None


def get_sesion_actual(request: Request) -> dict:
    token = request.cookies.get("retache_sesion")
    if not token:
        return None
    return leer_sesion(token)


def requiere_login(request: Request) -> dict:
    sesion = get_sesion_actual(request)
    if not sesion:
        raise HTTPException(status_code=302, headers={"Location": "/login"})
    return sesion


def requiere_transportista(request: Request) -> dict:
    sesion = get_sesion_actual(request)
    if not sesion:
        raise HTTPException(status_code=302, headers={"Location": "/login"})
    if sesion.get("tipo") != "transportista":
        raise HTTPException(status_code=403, detail="Solo transportistas pueden acceder aquí.")
    return sesion


def requiere_empresa(request: Request) -> dict:
    sesion = get_sesion_actual(request)
    if not sesion:
        raise HTTPException(status_code=302, headers={"Location": "/login"})
    if sesion.get("tipo") != "empresa":
        raise HTTPException(status_code=403, detail="Solo empresas pueden acceder aquí.")
    return sesion