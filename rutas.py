import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from fastapi import APIRouter, Depends, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from datetime import datetime

from database import get_db
from models import RutaDisponible, Transportista, Notificacion, Empresa, Carga, EstadoCarga, MensajeRuta, EstadoDocumento
from auth import get_sesion_actual

router = APIRouter(prefix="/rutas", tags=["rutas"])
templates = Jinja2Templates(directory="templates")


def ctx(request, db=None, **kwargs):
    from notificaciones import contar_no_leidas
    sesion = get_sesion_actual(request)
    notif_count = 0
    if sesion and sesion.get("tipo") == "transportista" and db:
        notif_count = contar_no_leidas(db, sesion["id"])
    return {"request": request, "sesion": sesion, "notif_count": notif_count, **kwargs}


@router.get("/publicar", response_class=HTMLResponse)
async def pagina_publicar_ruta(request: Request, db: Session = Depends(get_db)):
    sesion = get_sesion_actual(request)
    if not sesion or sesion.get("tipo") != "transportista":
        return RedirectResponse(url="/login", status_code=303)
    return templates.TemplateResponse("publicar_ruta.html", ctx(request, db=db))


@router.post("/publicar")
async def publicar_ruta(
    request: Request,
    origen_ciudad: str = Form(...),
    origen_estado: str = Form(...),
    destino_ciudad: str = Form(...),
    destino_estado: str = Form(...),
    fecha_salida: str = Form(...),
    capacidad_disponible_kg: float = Form(...),
    precio_fijo: float = Form(None),
    precio_negociable: bool = Form(True),
    db: Session = Depends(get_db),
):
    sesion = get_sesion_actual(request)
    if not sesion or sesion.get("tipo") != "transportista":
        return RedirectResponse(url="/login", status_code=303)

    fecha = datetime.strptime(fecha_salida, "%Y-%m-%d")

    nueva_ruta = RutaDisponible(
        transportista_id=sesion["id"],
        origen_ciudad=origen_ciudad,
        origen_estado=origen_estado,
        destino_ciudad=destino_ciudad,
        destino_estado=destino_estado,
        fecha_salida=fecha,
        capacidad_disponible_kg=capacidad_disponible_kg,
        precio_fijo=precio_fijo,
        precio_negociable=precio_negociable,
        activa=True,
    )
    db.add(nueva_ruta)
    db.commit()
    db.refresh(nueva_ruta)

    empresas = db.query(Empresa).filter(Empresa.activo == True).all()
    for empresa in empresas:
        cargas_coincidentes = db.query(Carga).filter(
            Carga.empresa_id == empresa.id,
            Carga.estado == EstadoCarga.disponible,
            Carga.origen_ciudad.ilike(f"%{origen_ciudad}%"),
        ).all()
        for carga in cargas_coincidentes:
            notif = Notificacion(
                transportista_id=sesion["id"],
                titulo="¡Transportista disponible para tu carga!",
                mensaje=f"Disponible en ruta {origen_ciudad} → {destino_ciudad} el {fecha.strftime('%d %b %Y')}",
                url=f"/rutas/buscar?origen={origen_ciudad}&destino={destino_ciudad}",
            )
            db.add(notif)
    db.commit()

    return RedirectResponse(url="/rutas/mis-rutas?publicada=exitoso", status_code=303)


@router.get("/buscar", response_class=HTMLResponse)
async def buscar_rutas(
    request: Request,
    origen: str = "",
    destino: str = "",
    db: Session = Depends(get_db),
):
    query = db.query(RutaDisponible).filter(RutaDisponible.activa == True)
    if origen:
        query = query.filter(RutaDisponible.origen_ciudad.ilike(f"%{origen}%"))
    if destino:
        query = query.filter(RutaDisponible.destino_ciudad.ilike(f"%{destino}%"))
    rutas = query.order_by(RutaDisponible.fecha_salida.asc()).all()
    return templates.TemplateResponse("buscar_rutas.html", ctx(request, db=db,
        rutas=rutas,
        filtro_origen=origen,
        filtro_destino=destino,
    ))


@router.get("/mis-rutas", response_class=HTMLResponse)
async def mis_rutas(request: Request, db: Session = Depends(get_db)):
    sesion = get_sesion_actual(request)
    if not sesion or sesion.get("tipo") != "transportista":
        return RedirectResponse(url="/login", status_code=303)
    rutas = db.query(RutaDisponible).filter(
        RutaDisponible.transportista_id == sesion["id"]
    ).order_by(RutaDisponible.fecha_publicacion.desc()).all()
    return templates.TemplateResponse("mis_rutas.html", ctx(request, db=db,
        rutas=rutas,
        publicada=request.query_params.get("publicada"),
    ))


@router.post("/desactivar/{ruta_id}")
async def desactivar_ruta(
    ruta_id: int, request: Request, db: Session = Depends(get_db)
):
    sesion = get_sesion_actual(request)
    if not sesion or sesion.get("tipo") != "transportista":
        return RedirectResponse(url="/login", status_code=303)
    ruta = db.query(RutaDisponible).filter(
        RutaDisponible.id == ruta_id,
        RutaDisponible.transportista_id == sesion["id"],
    ).first()
    if ruta:
        ruta.activa = False
        db.commit()
    return RedirectResponse(url="/rutas/mis-rutas", status_code=303)


# ─────────────────────────────────────────────
# CHAT POR RUTA
# ─────────────────────────────────────────────

@router.get("/{ruta_id}/chat", response_class=HTMLResponse)
async def chat_ruta(ruta_id: int, request: Request, db: Session = Depends(get_db)):
    sesion = get_sesion_actual(request)
    if not sesion:
        return RedirectResponse(url="/login", status_code=303)

    ruta = db.query(RutaDisponible).filter(RutaDisponible.id == ruta_id).first()
    if not ruta:
        raise HTTPException(status_code=404, detail="Ruta no encontrada")

    mensajes = db.query(MensajeRuta).filter(
        MensajeRuta.ruta_id == ruta_id
    ).order_by(MensajeRuta.fecha_envio.asc()).all()

    empresas_disponibles = []
    if sesion.get("tipo") == "transportista":
        ids_empresas = set()
        for m in mensajes:
            if m.remitente_empresa_id:
                ids_empresas.add(m.remitente_empresa_id)
        empresas_disponibles = db.query(Empresa).filter(Empresa.id.in_(ids_empresas)).all()

    return templates.TemplateResponse("chat_ruta.html", ctx(request, db=db,
        ruta=ruta,
        mensajes=mensajes,
    ))


@router.post("/{ruta_id}/chat/enviar")
async def enviar_mensaje_ruta(
    ruta_id: int,
    request: Request,
    contenido: str = Form(...),
    db: Session = Depends(get_db),
):
    sesion = get_sesion_actual(request)
    if not sesion:
        return RedirectResponse(url="/login", status_code=303)

    if not contenido.strip():
        return RedirectResponse(url=f"/rutas/{ruta_id}/chat", status_code=303)

    nuevo_mensaje = MensajeRuta(
        ruta_id=ruta_id,
        contenido=contenido.strip(),
        remitente_transportista_id=sesion["id"] if sesion.get("tipo") == "transportista" else None,
        remitente_empresa_id=sesion["id"] if sesion.get("tipo") == "empresa" else None,
    )
    db.add(nuevo_mensaje)

    ruta = db.query(RutaDisponible).filter(RutaDisponible.id == ruta_id).first()

    if sesion.get("tipo") == "transportista" and ruta:
        ids_empresas = {
            m.remitente_empresa_id
            for m in db.query(MensajeRuta).filter(
                MensajeRuta.ruta_id == ruta_id,
                MensajeRuta.remitente_empresa_id != None,
            ).all()
        }
        for eid in ids_empresas:
            db.add(Notificacion(
                empresa_id=eid,
                titulo=f"Nuevo mensaje de {ruta.transportista.nombre if ruta.transportista else 'un transportista'}",
                mensaje=contenido.strip()[:100],
                url=f"/rutas/{ruta_id}/chat",
            ))

    if sesion.get("tipo") == "empresa" and ruta:
        empresa = db.query(Empresa).filter(Empresa.id == sesion["id"]).first()
        notif = Notificacion(
            transportista_id=ruta.transportista_id,
            titulo=f"Nuevo mensaje de {empresa.razon_social if empresa else 'una empresa'}",
            mensaje=contenido.strip()[:100],
            url=f"/rutas/{ruta_id}/chat",
        )
        db.add(notif)

    db.commit()
    return RedirectResponse(url=f"/rutas/{ruta_id}/chat", status_code=303)


# ─────────────────────────────────────────────
# CERRAR TRATO — CONVERTIR RUTA EN CARGA FORMAL
# ─────────────────────────────────────────────

@router.get("/{ruta_id}/cerrar-trato", response_class=HTMLResponse)
async def pagina_cerrar_trato(ruta_id: int, request: Request, db: Session = Depends(get_db)):
    sesion = get_sesion_actual(request)
    if not sesion or sesion.get("tipo") != "empresa":
        return RedirectResponse(url="/login", status_code=303)

    ruta = db.query(RutaDisponible).filter(RutaDisponible.id == ruta_id).first()
    if not ruta:
        raise HTTPException(status_code=404, detail="Ruta no encontrada")

    return templates.TemplateResponse("cerrar_trato.html", ctx(request, db=db, ruta=ruta))


@router.post("/{ruta_id}/cerrar-trato")
async def cerrar_trato(
    ruta_id: int,
    request: Request,
    tipo_mercancia: str = Form(...),
    descripcion: str = Form(""),
    peso_kg: float = Form(...),
    precio_acordado_mxn: float = Form(...),
    db: Session = Depends(get_db),
):
    sesion = get_sesion_actual(request)
    if not sesion or sesion.get("tipo") != "empresa":
        return RedirectResponse(url="/login", status_code=303)

    ruta = db.query(RutaDisponible).filter(RutaDisponible.id == ruta_id).first()
    if not ruta:
        raise HTTPException(status_code=404, detail="Ruta no encontrada")

    transportista = db.query(Transportista).filter(Transportista.id == ruta.transportista_id).first()
    if not transportista or not transportista.carta_porte_habilitada:
        raise HTTPException(status_code=403, detail="El transportista no tiene documentos en regla.")

    nueva_carga = Carga(
        empresa_id=sesion["id"],
        transportista_id=ruta.transportista_id,
        titulo=f"Trato cerrado: {ruta.origen_ciudad} → {ruta.destino_ciudad}",
        descripcion=descripcion,
        tipo_mercancia=tipo_mercancia,
        peso_kg=peso_kg,
        origen_ciudad=ruta.origen_ciudad,
        origen_estado=ruta.origen_estado,
        destino_ciudad=ruta.destino_ciudad,
        destino_estado=ruta.destino_estado,
        fecha_recoleccion=ruta.fecha_salida,
        tipo_vehiculo_requerido=transportista.tipo_vehiculo,
        precio_ofrecido_mxn=precio_acordado_mxn,
        precio_negociable=False,
        estado=EstadoCarga.asignada,
        fecha_asignacion=datetime.utcnow(),
    )
    db.add(nueva_carga)

    ruta.activa = False
    transportista.disponible = False

    empresa = db.query(Empresa).filter(Empresa.id == sesion["id"]).first()
    empresa.total_cargas_publicadas += 1

    db.commit()
    db.refresh(nueva_carga)

    return RedirectResponse(url=f"/cargas/{nueva_carga.id}?publicada=exitoso", status_code=303)