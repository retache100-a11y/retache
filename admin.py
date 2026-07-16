import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from fastapi import APIRouter, Depends, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime

from database import get_db
from models import Transportista, Empresa, Carga, Mensaje, Notificacion, EstadoCarga, RutaDisponible, MensajeRuta
from auth import get_sesion_actual, hash_contrasena, crear_sesion

router = APIRouter(prefix="/admin", tags=["admin"])
templates = Jinja2Templates(directory="templates")

ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "admin@retache.mx")
ADMIN_PASSWORD = hash_contrasena(os.environ.get("ADMIN_PASSWORD", "cambiar-esta-clave"))


def ctx(request, **kwargs):
    return {"request": request, "sesion": get_sesion_actual(request), **kwargs}


def requiere_admin(request: Request):
    sesion = get_sesion_actual(request)
    if not sesion or sesion.get("tipo") != "admin":
        raise HTTPException(status_code=302, headers={"Location": "/admin/login"})
    return sesion


@router.get("/login", response_class=HTMLResponse)
async def pagina_login_admin(request: Request):
    return templates.TemplateResponse("admin/login.html", ctx(request))


@router.post("/login")
async def hacer_login_admin(
    request: Request,
    email: str = Form(...),
    contrasena: str = Form(...),
):
    if email.lower().strip() != ADMIN_EMAIL or hash_contrasena(contrasena) != ADMIN_PASSWORD:
        return templates.TemplateResponse("admin/login.html", ctx(request,
            error="Credenciales incorrectas."
        ))

    datos_sesion = {"id": 0, "nombre": "Administrador", "email": ADMIN_EMAIL, "tipo": "admin"}
    token = crear_sesion(datos_sesion)
    response = RedirectResponse(url="/admin", status_code=303)
    response.set_cookie(key="retache_sesion", value=token, httponly=True, max_age=86400, samesite="lax")
    return response


@router.get("/logout")
async def logout_admin():
    response = RedirectResponse(url="/admin/login", status_code=303)
    response.delete_cookie("retache_sesion")
    return response


@router.get("", response_class=HTMLResponse)
async def dashboard_admin(request: Request, db: Session = Depends(get_db)):
    requiere_admin(request)

    total_transportistas = db.query(Transportista).filter(Transportista.activo == True).count()
    total_empresas = db.query(Empresa).filter(Empresa.activo == True).count()
    total_cargas = db.query(Carga).count()
    cargas_activas = db.query(Carga).filter(Carga.estado == EstadoCarga.disponible).count()
    cargas_completadas = db.query(Carga).filter(Carga.estado == EstadoCarga.completada).count()
    cargas_asignadas = db.query(Carga).filter(Carga.estado == EstadoCarga.asignada).count()
    total_mensajes = db.query(Mensaje).count()
    total_notificaciones = db.query(Notificacion).count()

    ingresos_estimados = (
        db.query(func.sum(Carga.precio_ofrecido_mxn))
        .filter(Carga.estado == EstadoCarga.completada)
        .scalar() or 0
    )

    cargas_recientes = (
        db.query(Carga)
        .order_by(Carga.fecha_publicacion.desc())
        .limit(8)
        .all()
    )

    transportistas_recientes = (
        db.query(Transportista)
        .order_by(Transportista.fecha_registro.desc())
        .limit(5)
        .all()
    )

    return templates.TemplateResponse("admin/dashboard.html", ctx(request,
        total_transportistas=total_transportistas,
        total_empresas=total_empresas,
        total_cargas=total_cargas,
        cargas_activas=cargas_activas,
        cargas_completadas=cargas_completadas,
        cargas_asignadas=cargas_asignadas,
        total_mensajes=total_mensajes,
        total_notificaciones=total_notificaciones,
        ingresos_estimados=ingresos_estimados,
        cargas_recientes=cargas_recientes,
        transportistas_recientes=transportistas_recientes,
    ))


@router.get("/transportistas", response_class=HTMLResponse)
async def lista_transportistas(request: Request, db: Session = Depends(get_db)):
    requiere_admin(request)
    transportistas = (
        db.query(Transportista)
        .order_by(Transportista.fecha_registro.desc())
        .all()
    )
    return templates.TemplateResponse("admin/transportistas.html", ctx(request,
        transportistas=transportistas,
    ))


@router.get("/empresas", response_class=HTMLResponse)
async def lista_empresas(request: Request, db: Session = Depends(get_db)):
    requiere_admin(request)
    empresas = (
        db.query(Empresa)
        .order_by(Empresa.fecha_registro.desc())
        .all()
    )
    return templates.TemplateResponse("admin/empresas.html", ctx(request,
        empresas=empresas,
    ))


@router.get("/cargas", response_class=HTMLResponse)
async def lista_cargas_admin(request: Request, db: Session = Depends(get_db)):
    requiere_admin(request)
    cargas = (
        db.query(Carga)
        .order_by(Carga.fecha_publicacion.desc())
        .all()
    )
    return templates.TemplateResponse("admin/cargas.html", ctx(request,
        cargas=cargas,
    ))


@router.post("/transportistas/{t_id}/toggle")
async def toggle_transportista(request: Request, t_id: int, db: Session = Depends(get_db)):
    requiere_admin(request)
    t = db.query(Transportista).filter(Transportista.id == t_id).first()
    if t:
        t.activo = not t.activo
        db.commit()
    return RedirectResponse(url="/admin/transportistas", status_code=303)


@router.post("/empresas/{e_id}/toggle")
async def toggle_empresa(request: Request, e_id: int, db: Session = Depends(get_db)):
    requiere_admin(request)
    e = db.query(Empresa).filter(Empresa.id == e_id).first()
    if e:
        e.activo = not e.activo
        db.commit()
    return RedirectResponse(url="/admin/empresas", status_code=303)


@router.post("/transportistas/{t_id}/verificar")
async def verificar_transportista(request: Request, t_id: int, db: Session = Depends(get_db)):
    requiere_admin(request)
    t = db.query(Transportista).filter(Transportista.id == t_id).first()
    if t:
        t.rfc_verificado = True
        t.carta_porte_habilitada = True
        db.commit()
    return RedirectResponse(url="/admin/transportistas", status_code=303)


@router.post("/cargas/{carga_id}/eliminar")
async def eliminar_carga(request: Request, carga_id: int, db: Session = Depends(get_db)):
    requiere_admin(request)
    carga = db.query(Carga).filter(Carga.id == carga_id).first()
    if carga:
        db.delete(carga)
        db.commit()
    return RedirectResponse(url="/admin/cargas", status_code=303)


@router.post("/transportistas/{t_id}/eliminar")
async def eliminar_transportista(request: Request, t_id: int, db: Session = Depends(get_db)):
    requiere_admin(request)
    t = db.query(Transportista).filter(Transportista.id == t_id).first()
    if t:
        db.delete(t)
        db.commit()
    return RedirectResponse(url="/admin/transportistas", status_code=303)


@router.get("/transportistas/{t_id}/detalle", response_class=HTMLResponse)
async def detalle_transportista(request: Request, t_id: int, db: Session = Depends(get_db)):
    requiere_admin(request)
    t = db.query(Transportista).filter(Transportista.id == t_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Transportista no encontrado")
    cargas = db.query(Carga).filter(Carga.transportista_id == t_id).all()
    return templates.TemplateResponse("admin/detalle_transportista.html", ctx(request,
        t=t,
        cargas=cargas,
    ))


@router.get("/empresas/{e_id}/detalle", response_class=HTMLResponse)
async def detalle_empresa(request: Request, e_id: int, db: Session = Depends(get_db)):
    requiere_admin(request)
    e = db.query(Empresa).filter(Empresa.id == e_id).first()
    if not e:
        raise HTTPException(status_code=404, detail="Empresa no encontrada")
    cargas = db.query(Carga).filter(Carga.empresa_id == e_id).all()
    return templates.TemplateResponse("admin/detalle_empresa.html", ctx(request,
        e=e,
        cargas=cargas,
    ))

@router.get("/rutas", response_class=HTMLResponse)
async def lista_rutas_admin(request: Request, db: Session = Depends(get_db)):
    requiere_admin(request)
    rutas = (
        db.query(RutaDisponible)
        .order_by(RutaDisponible.fecha_publicacion.desc())
        .all()
    )
    return templates.TemplateResponse("admin/rutas.html", ctx(request,
        rutas=rutas,
    ))


@router.post("/rutas/{ruta_id}/eliminar")
async def eliminar_ruta_admin(request: Request, ruta_id: int, db: Session = Depends(get_db)):
    requiere_admin(request)
    ruta = db.query(RutaDisponible).filter(RutaDisponible.id == ruta_id).first()
    if ruta:
        db.query(MensajeRuta).filter(MensajeRuta.ruta_id == ruta_id).delete()
        db.delete(ruta)
        db.commit()
    return RedirectResponse(url="/admin/rutas", status_code=303)