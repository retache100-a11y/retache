import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from fastapi import APIRouter, Depends, HTTPException, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from datetime import datetime
import re

from database import get_db
from models import Empresa, Carga, EstadoCarga
from auth import hash_contrasena, get_sesion_actual, crear_sesion

router = APIRouter(prefix="/empresas", tags=["empresas"])
templates = Jinja2Templates(directory="templates")


def ctx(request, **kwargs):
    return {"request": request, "sesion": get_sesion_actual(request), **kwargs}


def validar_rfc_empresa(rfc: str) -> bool:
    patron = r'^[A-Z]{3}\d{6}[A-Z0-9]{3}$'
    return bool(re.match(patron, rfc.upper()))


@router.get("/registro", response_class=HTMLResponse)
async def pagina_registro(request: Request):
    return templates.TemplateResponse("registro_empresa.html", ctx(request))


@router.get("/{empresa_id}", response_class=HTMLResponse)
async def perfil_empresa(
    request: Request, empresa_id: int, db: Session = Depends(get_db)
):
    empresa = db.query(Empresa).filter(Empresa.id == empresa_id).first()
    if not empresa:
        raise HTTPException(status_code=404, detail="Empresa no encontrada")

    cargas_activas = (
        db.query(Carga)
        .filter(
            Carga.empresa_id == empresa_id,
            Carga.estado == EstadoCarga.disponible,
        )
        .order_by(Carga.fecha_publicacion.desc())
        .all()
    )
    return templates.TemplateResponse("perfil_empresa.html", ctx(request,
        empresa=empresa,
        cargas_activas=cargas_activas,
    ))


@router.post("/registro")
async def registrar_empresa(
    request: Request,
    razon_social: str = Form(...),
    nombre_comercial: str = Form(""),
    email: str = Form(...),
    telefono: str = Form(...),
    contrasena: str = Form(...),
    rfc: str = Form(...),
    num_acta_constitutiva: str = Form(...),
    giro: str = Form(...),
    nombre_contacto: str = Form(...),
    puesto_contacto: str = Form(""),
    municipio: str = Form(""),
    estado_rep: str = Form(""),
    cp: str = Form(""),
    db: Session = Depends(get_db),
):
    rfc_upper = rfc.upper().strip()
    if not validar_rfc_empresa(rfc_upper):
        raise HTTPException(status_code=400, detail="RFC inválido para empresa.")

    existente = db.query(Empresa).filter(
        (Empresa.email == email) | (Empresa.rfc == rfc_upper)
    ).first()
    if existente:
        raise HTTPException(status_code=400, detail="Ya existe una cuenta con ese email o RFC.")

    if not num_acta_constitutiva or len(num_acta_constitutiva.strip()) < 3:
        raise HTTPException(status_code=400, detail="El número de acta constitutiva es requerido.")

    nueva = Empresa(
        razon_social=razon_social.strip(),
        nombre_comercial=nombre_comercial.strip() or razon_social.strip(),
        email=email.lower().strip(),
        telefono=telefono,
        contrasena_hash=hash_contrasena(contrasena),
        rfc=rfc_upper, rfc_verificado=True,
        num_acta_constitutiva=num_acta_constitutiva.strip(),
        acta_constitutiva_verificada=True,
        giro=giro,
        nombre_contacto=nombre_contacto.strip(),
        puesto_contacto=puesto_contacto.strip(),
        municipio=municipio.strip(),
        estado=estado_rep.strip(),
        cp=cp.strip(),
    )
    db.add(nueva)
    db.commit()
    db.refresh(nueva)

    datos_sesion = {
        "id": nueva.id,
        "nombre": nueva.razon_social,
        "email": nueva.email,
        "tipo": "empresa",
    }
    token = crear_sesion(datos_sesion)
    response = RedirectResponse(url=f"/empresas/{nueva.id}?registro=exitoso", status_code=303)
    response.set_cookie(key="retache_sesion", value=token, httponly=True, max_age=86400, samesite="lax")
    return response


@router.post("/{empresa_id}/publicar-carga")
async def publicar_carga(
    empresa_id: int,
    titulo: str = Form(...),
    tipo_mercancia: str = Form(...),
    descripcion: str = Form(""),
    peso_kg: float = Form(...),
    origen_ciudad: str = Form(...),
    origen_estado: str = Form(...),
    destino_ciudad: str = Form(...),
    destino_estado: str = Form(...),
    fecha_recoleccion: str = Form(...),
    tipo_vehiculo_requerido: str = Form(...),
    precio_ofrecido_mxn: float = Form(...),
    precio_negociable: bool = Form(True),
    db: Session = Depends(get_db),
):
    empresa = db.query(Empresa).filter(Empresa.id == empresa_id).first()
    if not empresa:
        raise HTTPException(status_code=404, detail="Empresa no encontrada")

    if not empresa.acta_constitutiva_verificada:
        raise HTTPException(status_code=403, detail="Tu empresa debe tener el acta constitutiva verificada.")

    fecha = datetime.strptime(fecha_recoleccion, "%Y-%m-%d")

    nueva_carga = Carga(
        empresa_id=empresa_id, titulo=titulo,
        descripcion=descripcion, tipo_mercancia=tipo_mercancia,
        peso_kg=peso_kg,
        origen_ciudad=origen_ciudad, origen_estado=origen_estado,
        destino_ciudad=destino_ciudad, destino_estado=destino_estado,
        fecha_recoleccion=fecha,
        tipo_vehiculo_requerido=tipo_vehiculo_requerido,
        precio_ofrecido_mxn=precio_ofrecido_mxn,
        precio_negociable=precio_negociable,
        estado=EstadoCarga.disponible,
    )
    db.add(nueva_carga)
    empresa.total_cargas_publicadas += 1
    db.commit()
    db.refresh(nueva_carga)

    return RedirectResponse(url=f"/cargas/{nueva_carga.id}?publicada=exitoso", status_code=303)


@router.post("/{empresa_id}/cancelar-carga/{carga_id}")
async def cancelar_carga(
    empresa_id: int,
    carga_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    sesion = get_sesion_actual(request)
    if not sesion or sesion.get("tipo") != "empresa":
        return RedirectResponse(url="/login", status_code=303)

    carga = db.query(Carga).filter(
        Carga.id == carga_id,
        Carga.empresa_id == empresa_id,
        Carga.estado == EstadoCarga.disponible,
    ).first()

    if carga:
        carga.estado = EstadoCarga.cancelada
        db.commit()

    return RedirectResponse(url=f"/empresas/{empresa_id}", status_code=303)