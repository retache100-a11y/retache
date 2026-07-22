import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from fastapi import APIRouter, Depends, HTTPException, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
import hashlib
import json
import re

from database import get_db
from models import Transportista, Carga, Resena, EstadoDocumento
from auth import hash_contrasena, get_sesion_actual, crear_sesion

router = APIRouter(prefix="/transportistas", tags=["transportistas"])
templates = Jinja2Templates(directory="templates")


def ctx(request, **kwargs):
    return {"request": request, "sesion": get_sesion_actual(request), **kwargs}


def validar_rfc_persona_fisica(rfc: str) -> bool:
    rfc = re.sub(r'[\s\-\.]', '', rfc or '').upper().strip()
    return bool(re.match(r'^[A-Z0-9]{12,13}$', rfc))


@router.get("/registro", response_class=HTMLResponse)
async def pagina_registro(request: Request):
    return templates.TemplateResponse("registro_transportista.html", ctx(request))


@router.get("/mapa", response_class=HTMLResponse)
async def pagina_mapa(request: Request, db: Session = Depends(get_db)):
    transportistas = (
        db.query(Transportista)
        .filter(Transportista.activo == True, Transportista.latitud != None)
        .all()
    )
    return templates.TemplateResponse("mapa.html", ctx(request, transportistas=transportistas))


@router.get("/api/disponibles")
async def transportistas_disponibles(db: Session = Depends(get_db)):
    transportistas = (
        db.query(Transportista)
        .filter(
            Transportista.activo == True,
            Transportista.disponible == True,
            Transportista.carta_porte_habilitada == True,
            Transportista.latitud != None,
        )
        .all()
    )
    return [
        {
            "id": t.id,
            "nombre": f"{t.nombre} {t.apellidos[0]}.",
            "tipo_vehiculo": t.tipo_vehiculo,
            "capacidad_kg": t.capacidad_kg,
            "calificacion": round(t.calificacion_promedio, 1),
            "total_viajes": t.total_viajes,
            "lat": t.latitud,
            "lng": t.longitud,
            "carta_porte": t.carta_porte_habilitada,
        }
        for t in transportistas
    ]


@router.get("/{transportista_id}", response_class=HTMLResponse)
async def perfil_transportista(
    request: Request, transportista_id: int, db: Session = Depends(get_db)
):
    t = db.query(Transportista).filter(Transportista.id == transportista_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Transportista no encontrado")

    resenas = (
        db.query(Resena)
        .filter(Resena.transportista_id == transportista_id)
        .order_by(Resena.fecha.desc())
        .limit(5)
        .all()
    )
    cargas_completadas = (
        db.query(Carga)
        .filter(Carga.transportista_id == transportista_id, Carga.estado == "completada")
        .count()
    )
    rutas = []
    if t.rutas_frecuentes:
        try:
            rutas = json.loads(t.rutas_frecuentes)
        except Exception:
            rutas = []

    return templates.TemplateResponse("perfil_transportista.html", ctx(request,
        transportista=t,
        resenas=resenas,
        cargas_completadas=cargas_completadas,
        rutas_frecuentes=rutas,
    ))


@router.post("/registro")
async def registrar_transportista(
    request: Request,
    nombre: str = Form(...),
    apellidos: str = Form(...),
    email: str = Form(...),
    telefono: str = Form(...),
    contrasena: str = Form(...),
    rfc: str = Form(...),
    num_licencia_federal: str = Form(...),
    num_poliza_seguro: str = Form(...),
    tipo_vehiculo: str = Form(...),
    marca_vehiculo: str = Form(...),
    modelo_vehiculo: str = Form(...),
    anio_vehiculo: int = Form(...),
    placa: str = Form(...),
    capacidad_kg: float = Form(...),
    db: Session = Depends(get_db),
):
    rfc_upper = re.sub(r'[\s\-\.]', '', rfc or '').upper().strip()
    if not validar_rfc_persona_fisica(rfc_upper):
        return templates.TemplateResponse("registro_transportista.html", ctx(request,
            error="El RFC no tiene un formato válido. Debe tener 12 o 13 caracteres (ej. ABCD800101XY1)."))

    existente = db.query(Transportista).filter(
        (Transportista.email == email) | (Transportista.rfc == rfc_upper)
    ).first()
    if existente:
        return templates.TemplateResponse("registro_transportista.html", ctx(request,
            error="Ya existe una cuenta registrada con ese correo o RFC."))

    nuevo = Transportista(
        nombre=nombre, apellidos=apellidos,
        email=email.lower().strip(), telefono=telefono,
        contrasena_hash=hash_contrasena(contrasena),
        rfc=rfc_upper, rfc_verificado=True,
        num_licencia_federal=num_licencia_federal,
        licencia_estado=EstadoDocumento.vigente,
        num_poliza_seguro=num_poliza_seguro,
        seguro_estado=EstadoDocumento.vigente,
        tarjeta_circulacion_estado=EstadoDocumento.vigente,
        verificacion_vehicular_estado=EstadoDocumento.vigente,
        tipo_vehiculo=tipo_vehiculo,
        marca_vehiculo=marca_vehiculo,
        modelo_vehiculo=modelo_vehiculo,
        anio_vehiculo=anio_vehiculo,
        placa=placa.upper().strip(),
        capacidad_kg=capacidad_kg,
        carta_porte_habilitada=True,
        disponible=True,
        latitud=19.9831,
        longitud=-102.2836,
    )
    db.add(nuevo)
    db.commit()
    db.refresh(nuevo)

    datos_sesion = {
        "id": nuevo.id,
        "nombre": nuevo.nombre,
        "email": nuevo.email,
        "tipo": "transportista",
    }
    token = crear_sesion(datos_sesion)
    response = RedirectResponse(url=f"/transportistas/{nuevo.id}?registro=exitoso", status_code=303)
    response.set_cookie(key="retache_sesion", value=token, httponly=True, max_age=86400, samesite="lax")
    return response

@router.post("/api/actualizar-ubicacion")
async def actualizar_ubicacion(
    request: Request,
    db: Session = Depends(get_db),
):
    sesion = get_sesion_actual(request)
    if not sesion or sesion.get("tipo") != "transportista":
        return {"error": "No autorizado"}

    data = await request.json()
    lat = data.get("lat")
    lng = data.get("lng")

    if not lat or not lng:
        return {"error": "Coordenadas inválidas"}

    t = db.query(Transportista).filter(Transportista.id == sesion["id"]).first()
    if t:
        t.latitud = lat
        t.longitud = lng
        t.disponible = True
        db.commit()

    return {"ok": True, "lat": lat, "lng": lng}


@router.post("/api/desactivar-disponibilidad")
async def desactivar_disponibilidad(
    request: Request,
    db: Session = Depends(get_db),
):
    sesion = get_sesion_actual(request)
    if not sesion or sesion.get("tipo") != "transportista":
        return {"error": "No autorizado"}

    t = db.query(Transportista).filter(Transportista.id == sesion["id"]).first()
    if t:
        t.disponible = False
        db.commit()

    return {"ok": True}