import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from fastapi import APIRouter, Depends, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import secrets
import hashlib

from database import get_db
from models import Transportista, Empresa
from auth import get_sesion_actual
from emails import email_verificacion, email_recuperar_contrasena

router = APIRouter(tags=["cuenta"])
templates = Jinja2Templates(directory="templates")


def ctx(request, **kwargs):
    sesion = get_sesion_actual(request)
    return {"request": request, "sesion": sesion, **kwargs}


def hash_contrasena(contrasena: str) -> str:
    return hashlib.sha256(contrasena.encode()).hexdigest()


# ─────────────────────────────────────────────
# VERIFICACIÓN DE EMAIL
# ─────────────────────────────────────────────

@router.get("/verificar-email/{token}", response_class=HTMLResponse)
async def verificar_email(token: str, request: Request, db: Session = Depends(get_db)):
    transportista = db.query(Transportista).filter(
        Transportista.token_verificacion == token
    ).first()

    if transportista:
        transportista.email_verificado = True
        transportista.token_verificacion = None
        db.commit()
        return templates.TemplateResponse("verificacion_exitosa.html", ctx(request,
            nombre=transportista.nombre,
            tipo="transportista",
        ))

    empresa = db.query(Empresa).filter(
        Empresa.token_verificacion == token
    ).first()

    if empresa:
        empresa.email_verificado = True
        empresa.token_verificacion = None
        db.commit()
        return templates.TemplateResponse("verificacion_exitosa.html", ctx(request,
            nombre=empresa.razon_social,
            tipo="empresa",
        ))

    return templates.TemplateResponse("verificacion_exitosa.html", ctx(request,
        error=True,
    ))


# ─────────────────────────────────────────────
# RECUPERAR CONTRASEÑA
# ─────────────────────────────────────────────

@router.get("/recuperar-contrasena", response_class=HTMLResponse)
async def pagina_recuperar(request: Request):
    return templates.TemplateResponse("recuperar_contrasena.html", ctx(request))


@router.post("/recuperar-contrasena")
async def solicitar_recuperacion(
    request: Request,
    email: str = Form(...),
    tipo: str = Form(...),
    db: Session = Depends(get_db),
):
    token = secrets.token_urlsafe(32)
    expira = datetime.utcnow() + timedelta(hours=1)

    if tipo == "transportista":
        usuario = db.query(Transportista).filter(
            Transportista.email == email.lower().strip()
        ).first()
        if usuario:
            usuario.token_reset_password = token
            usuario.token_reset_expira = expira
            db.commit()
            email_recuperar_contrasena(usuario.email, usuario.nombre, token)
    else:
        usuario = db.query(Empresa).filter(
            Empresa.email == email.lower().strip()
        ).first()
        if usuario:
            usuario.token_reset_password = token
            usuario.token_reset_expira = expira
            db.commit()
            email_recuperar_contrasena(usuario.email, usuario.razon_social, token)

    return templates.TemplateResponse("recuperar_contrasena.html", ctx(request,
        enviado=True,
    ))


@router.get("/restablecer-contrasena/{token}", response_class=HTMLResponse)
async def pagina_restablecer(token: str, request: Request, db: Session = Depends(get_db)):
    transportista = db.query(Transportista).filter(
        Transportista.token_reset_password == token,
        Transportista.token_reset_expira > datetime.utcnow(),
    ).first()

    empresa = db.query(Empresa).filter(
        Empresa.token_reset_password == token,
        Empresa.token_reset_expira > datetime.utcnow(),
    ).first()

    if not transportista and not empresa:
        return templates.TemplateResponse("restablecer_contrasena.html", ctx(request,
            error="El enlace ha expirado o no es válido. Solicita uno nuevo.",
        ))

    return templates.TemplateResponse("restablecer_contrasena.html", ctx(request,
        token=token,
    ))


@router.post("/restablecer-contrasena/{token}")
async def restablecer_contrasena(
    token: str,
    request: Request,
    nueva_contrasena: str = Form(...),
    db: Session = Depends(get_db),
):
    if len(nueva_contrasena) < 8:
        return templates.TemplateResponse("restablecer_contrasena.html", ctx(request,
            token=token,
            error="La contraseña debe tener al menos 8 caracteres.",
        ))

    nueva_hash = hash_contrasena(nueva_contrasena)

    transportista = db.query(Transportista).filter(
        Transportista.token_reset_password == token,
        Transportista.token_reset_expira > datetime.utcnow(),
    ).first()

    if transportista:
        transportista.contrasena_hash = nueva_hash
        transportista.token_reset_password = None
        transportista.token_reset_expira = None
        db.commit()
        return RedirectResponse(url="/login?reset=exitoso", status_code=303)

    empresa = db.query(Empresa).filter(
        Empresa.token_reset_password == token,
        Empresa.token_reset_expira > datetime.utcnow(),
    ).first()

    if empresa:
        empresa.contrasena_hash = nueva_hash
        empresa.token_reset_password = None
        empresa.token_reset_expira = None
        db.commit()
        return RedirectResponse(url="/login?reset=exitoso", status_code=303)

    return templates.TemplateResponse("restablecer_contrasena.html", ctx(request,
        error="El enlace ha expirado. Solicita uno nuevo.",
    ))