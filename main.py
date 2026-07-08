import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from fastapi import FastAPI, Request, Depends, HTTPException, Form
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from datetime import datetime
import json

from database import engine, get_db, Base
from models import Transportista, Empresa, Carga, Mensaje, Resena, Notificacion, EstadoCarga, EstadoDocumento
from routers import transportistas
from routers import empresas
from admin import router as admin_router
from pagos import router as pagos_router
from rutas import router as rutas_router
from cuenta import router as cuenta_router
from auth import hash_contrasena, crear_sesion, get_sesion_actual
from notificaciones import (
    notificar_nueva_carga, obtener_notificaciones,
    contar_no_leidas, marcar_leida
)

Base.metadata.create_all(bind=engine)

app = FastAPI(title="RETACHE", description="Logística inversa MX", version="1.0.0")

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

app.include_router(transportistas.router)
app.include_router(empresas.router)
app.include_router(admin_router)
app.include_router(pagos_router)
app.include_router(rutas_router)
app.include_router(cuenta_router)

def contexto(request: Request, db: Session = None, **kwargs):
    sesion = get_sesion_actual(request)
    notif_count = 0
    if sesion and sesion.get("tipo") == "transportista" and db:
        notif_count = contar_no_leidas(db, sesion["id"])
    return {"request": request, "sesion": sesion, "notif_count": notif_count, **kwargs}

@app.get("/terminos", response_class=HTMLResponse)
async def terminos(request: Request, db: Session = Depends(get_db)):
    return templates.TemplateResponse("terminos.html", contexto(request, db))


@app.get("/privacidad", response_class=HTMLResponse)
async def privacidad(request: Request, db: Session = Depends(get_db)):
    return templates.TemplateResponse("privacidad.html", contexto(request, db))

@app.get("/sitemap.xml")
async def sitemap():
    from fastapi.responses import Response
    content = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://retache.com.mx/</loc><priority>1.0</priority></url>
  <url><loc>https://retache.com.mx/como-funciona</loc><priority>0.9</priority></url>
  <url><loc>https://retache.com.mx/cargas</loc><priority>0.8</priority></url>
  <url><loc>https://retache.com.mx/transportistas/mapa</loc><priority>0.8</priority></url>
  <url><loc>https://retache.com.mx/rutas/buscar</loc><priority>0.8</priority></url>
  <url><loc>https://retache.com.mx/transportistas/registro</loc><priority>0.7</priority></url>
  <url><loc>https://retache.com.mx/empresas/registro</loc><priority>0.7</priority></url>
  <url><loc>https://retache.com.mx/terminos</loc><priority>0.5</priority></url>
  <url><loc>https://retache.com.mx/privacidad</loc><priority>0.5</priority></url>
</urlset>"""
    return Response(content=content, media_type="application/xml")

@app.get("/como-funciona", response_class=HTMLResponse)
async def como_funciona(request: Request, db: Session = Depends(get_db)):
    return templates.TemplateResponse("como_funciona.html", contexto(request, db))

@app.get("/", response_class=HTMLResponse)
async def inicio(request: Request, db: Session = Depends(get_db)):
    total_transportistas = db.query(Transportista).filter(Transportista.activo == True).count()
    total_cargas = db.query(Carga).filter(Carga.estado == EstadoCarga.disponible).count()
    total_completados = db.query(Carga).filter(Carga.estado == EstadoCarga.completada).count()
    cargas_recientes = (
        db.query(Carga)
        .filter(Carga.estado == EstadoCarga.disponible)
        .order_by(Carga.fecha_publicacion.desc())
        .limit(6).all()
    )
    transportistas_activos = (
        db.query(Transportista)
        .filter(Transportista.activo == True, Transportista.disponible == True)
        .order_by(Transportista.calificacion_promedio.desc())
        .limit(4).all()
    )
    return templates.TemplateResponse("index.html", contexto(request, db,
        total_transportistas=total_transportistas,
        total_cargas=total_cargas,
        total_completados=total_completados,
        cargas_recientes=cargas_recientes,
        transportistas_activos=transportistas_activos,
    ))


@app.get("/login", response_class=HTMLResponse)
async def pagina_login(request: Request, db: Session = Depends(get_db)):
    return templates.TemplateResponse("login.html", contexto(request, db))


@app.post("/login")
async def hacer_login(
    request: Request,
    email: str = Form(...),
    contrasena: str = Form(...),
    tipo: str = Form(...),
    db: Session = Depends(get_db),
):
    password_hash = hash_contrasena(contrasena)

    if tipo == "transportista":
        usuario = db.query(Transportista).filter(
            Transportista.email == email.lower().strip(),
            Transportista.contrasena_hash == password_hash,
            Transportista.activo == True,
        ).first()
        if not usuario:
            return templates.TemplateResponse("login.html", contexto(request, db,
                error="Correo o contraseña incorrectos."
            ))
        datos_sesion = {"id": usuario.id, "nombre": usuario.nombre, "email": usuario.email, "tipo": "transportista"}
        destino = f"/transportistas/{usuario.id}"
    else:
        usuario = db.query(Empresa).filter(
            Empresa.email == email.lower().strip(),
            Empresa.contrasena_hash == password_hash,
            Empresa.activo == True,
        ).first()
        if not usuario:
            return templates.TemplateResponse("login.html", contexto(request, db,
                error="Correo o contraseña incorrectos."
            ))
        datos_sesion = {"id": usuario.id, "nombre": usuario.razon_social, "email": usuario.email, "tipo": "empresa"}
        destino = f"/empresas/{usuario.id}"

    token = crear_sesion(datos_sesion)
    response = RedirectResponse(url=destino, status_code=303)
    response.set_cookie(key="retache_sesion", value=token, httponly=True, max_age=86400, samesite="lax")
    return response


@app.get("/logout")
async def cerrar_sesion():
    response = RedirectResponse(url="/", status_code=303)
    response.delete_cookie("retache_sesion")
    return response


@app.get("/notificaciones", response_class=HTMLResponse)
async def pagina_notificaciones(request: Request, db: Session = Depends(get_db)):
    sesion = get_sesion_actual(request)
    if not sesion or sesion.get("tipo") != "transportista":
        return RedirectResponse(url="/login", status_code=303)
    notifs = obtener_notificaciones(db, sesion["id"])
    return templates.TemplateResponse("notificaciones.html", contexto(request, db,
        notificaciones=notifs,
    ))


@app.post("/notificaciones/{notif_id}/leida")
async def marcar_notificacion_leida(
    notif_id: int, request: Request, db: Session = Depends(get_db)
):
    sesion = get_sesion_actual(request)
    if sesion and sesion.get("tipo") == "transportista":
        marcar_leida(db, notif_id, sesion["id"])
    return {"ok": True}


@app.get("/notificaciones/marcar-todas-leidas")
async def marcar_todas_leidas(request: Request, db: Session = Depends(get_db)):
    sesion = get_sesion_actual(request)
    if sesion and sesion.get("tipo") == "transportista":
        db.query(Notificacion).filter(
            Notificacion.transportista_id == sesion["id"],
            Notificacion.leida == False,
        ).update({"leida": True})
        db.commit()
    return RedirectResponse(url="/notificaciones", status_code=303)


@app.get("/cargas", response_class=HTMLResponse)
async def lista_cargas(
    request: Request,
    origen: str = "",
    destino: str = "",
    tipo_vehiculo: str = "",
    db: Session = Depends(get_db),
):
    query = db.query(Carga).filter(Carga.estado == EstadoCarga.disponible)
    if origen:
        query = query.filter(Carga.origen_ciudad.ilike(f"%{origen}%"))
    if destino:
        query = query.filter(Carga.destino_ciudad.ilike(f"%{destino}%"))
    if tipo_vehiculo:
        query = query.filter(Carga.tipo_vehiculo_requerido == tipo_vehiculo)
    cargas = query.order_by(Carga.fecha_publicacion.desc()).all()
    return templates.TemplateResponse("cargas.html", contexto(request, db,
        cargas=cargas,
        filtro_origen=origen,
        filtro_destino=destino,
        filtro_vehiculo=tipo_vehiculo,
    ))


@app.get("/cargas/{carga_id}", response_class=HTMLResponse)
async def detalle_carga(request: Request, carga_id: int, db: Session = Depends(get_db)):
    carga = db.query(Carga).filter(Carga.id == carga_id).first()
    if not carga:
        raise HTTPException(status_code=404, detail="Carga no encontrada")
    mensajes = (
        db.query(Mensaje)
        .filter(Mensaje.carga_id == carga_id)
        .order_by(Mensaje.fecha_envio.asc())
        .all()
    )
    return templates.TemplateResponse("detalle_carga.html", contexto(request, db,
        carga=carga,
        mensajes=mensajes,
    ))


@app.post("/cargas/{carga_id}/asignar")
async def asignar_transportista(
    carga_id: int,
    transportista_id: int = Form(...),
    db: Session = Depends(get_db),
):
    carga = db.query(Carga).filter(Carga.id == carga_id).first()
    if not carga:
        raise HTTPException(status_code=404, detail="Carga no encontrada")
    transportista = db.query(Transportista).filter(Transportista.id == transportista_id).first()
    if not transportista:
        raise HTTPException(status_code=404, detail="Transportista no encontrado")
    if not transportista.carta_porte_habilitada:
        raise HTTPException(status_code=403, detail="El transportista no tiene documentos en regla.")
    carga.transportista_id = transportista_id
    carga.estado = EstadoCarga.asignada
    carga.fecha_asignacion = datetime.utcnow()
    transportista.disponible = False
    db.commit()
    return RedirectResponse(url=f"/cargas/{carga_id}", status_code=303)


@app.post("/mensajes/enviar")
async def enviar_mensaje(
    carga_id: int = Form(...),
    contenido: str = Form(...),
    remitente_tipo: str = Form(...),
    remitente_id: int = Form(...),
    db: Session = Depends(get_db),
):
    if not contenido.strip():
        raise HTTPException(status_code=400, detail="El mensaje no puede estar vacío.")
    nuevo_mensaje = Mensaje(
        carga_id=carga_id,
        contenido=contenido.strip(),
        remitente_transportista_id=remitente_id if remitente_tipo == "transportista" else None,
        remitente_empresa_id=remitente_id if remitente_tipo == "empresa" else None,
    )
    db.add(nuevo_mensaje)
    db.commit()
    return RedirectResponse(url=f"/cargas/{carga_id}", status_code=303)


@app.get("/cargas/{carga_id}/carta-porte")
async def generar_carta_porte(carga_id: int, db: Session = Depends(get_db)):
    carga = db.query(Carga).filter(Carga.id == carga_id).first()
    if not carga:
        raise HTTPException(status_code=404, detail="Carga no encontrada")
    if not carga.transportista_id:
        raise HTTPException(status_code=400, detail="La carga necesita un transportista asignado.")
    t = carga.transportista
    e = carga.empresa
    carta = {
        "version": "3.1",
        "emisor": {"rfc": e.rfc, "razon_social": e.razon_social},
        "complemento_carta_porte": {
            "version": "3.1",
            "ubicaciones": [
                {"tipoUbicacion": "Origen", "municipio": carga.origen_ciudad, "estado": carga.origen_estado},
                {"tipoUbicacion": "Destino", "municipio": carga.destino_ciudad, "estado": carga.destino_estado},
            ],
            "mercancias": {
                "pesoBrutoTotal": carga.peso_kg,
                "mercancia": [{"descripcion": carga.tipo_mercancia, "pesoEnKg": carga.peso_kg}],
                "autotransporte": {
                    "placaVM": t.placa or "",
                    "polizaCarga": t.num_poliza_seguro or "",
                },
            },
            "figuraTransporte": [{"rfcFigura": t.rfc, "numLicencia": t.num_licencia_federal or "", "nombreFigura": f"{t.nombre} {t.apellidos}"}],
        },
        "nota": "Requiere timbrado con PAC autorizado SAT antes de usarse en carretera.",
    }
    carga.carta_porte_generada = True
    carga.carta_porte_xml = json.dumps(carta, ensure_ascii=False, indent=2)
    db.commit()
    return carta


@app.post("/dev/cargar-datos-prueba")
async def cargar_datos_prueba(db: Session = Depends(get_db)):
    import hashlib
    def h(p): return hashlib.sha256(p.encode()).hexdigest()

    t1 = Transportista(
        nombre="Juan", apellidos="Pérez Lara",
        email="juan@retache.mx", telefono="3411234567",
        contrasena_hash=h("retache123"), rfc="PELJ850312KL4",
        rfc_verificado=True, num_licencia_federal="LIC-FED-001",
        licencia_estado="vigente", num_poliza_seguro="POL-2024-001",
        seguro_estado="vigente", seguro_cobertura_mxn=2000000,
        tarjeta_circulacion_estado="vigente",
        verificacion_vehicular_estado="vigente",
        tipo_vehiculo="Torton", marca_vehiculo="Kenworth",
        modelo_vehiculo="T370", anio_vehiculo=2019,
        placa="MSJ4821B", capacidad_kg=12000,
        carta_porte_habilitada=True, disponible=True,
        latitud=19.9831, longitud=-102.2836,
        calificacion_promedio=4.9, total_viajes=208,
        porcentaje_puntualidad=99.0,
        rutas_frecuentes=json.dumps(["Zamora → CDMX", "Guadalajara → Morelia", "Zamora → Manzanillo"]),
    )
    t2 = Transportista(
        nombre="Mario", apellidos="Ramírez Soto",
        email="mario@retache.mx", telefono="3339876543",
        contrasena_hash=h("retache123"), rfc="RASM780901AB3",
        rfc_verificado=True, num_licencia_federal="LIC-FED-002",
        licencia_estado="vigente", num_poliza_seguro="POL-2024-002",
        seguro_estado="vigente", seguro_cobertura_mxn=1500000,
        tarjeta_circulacion_estado="vigente",
        verificacion_vehicular_estado="vigente",
        tipo_vehiculo="C3 (3 ejes)", marca_vehiculo="Freightliner",
        modelo_vehiculo="M2 106", anio_vehiculo=2021,
        placa="GDL5532A", capacidad_kg=8000,
        carta_porte_habilitada=True, disponible=True,
        latitud=20.6597, longitud=-103.3496,
        calificacion_promedio=4.7, total_viajes=134,
        porcentaje_puntualidad=97.0,
    )
    e1 = Empresa(
        razon_social="Distribuidora del Bajío S.A. de C.V.",
        nombre_comercial="Dibajío",
        email="contacto@dibajio.mx", telefono="3412345678",
        contrasena_hash=h("retache123"), rfc="DBA010101AAA",
        rfc_verificado=True, num_acta_constitutiva="ESCRITURA-12345",
        acta_constitutiva_verificada=True, giro="Abarrotes y alimentos",
        nombre_contacto="Roberto García", puesto_contacto="Gerente de Logística",
        municipio="Zamora", estado="Michoacán", cp="59700",
        calificacion_promedio=4.8, total_cargas_publicadas=2,
    )
    db.add_all([t1, t2, e1])
    db.commit()
    db.refresh(t1)
    db.refresh(t2)
    db.refresh(e1)

    c1 = Carga(
        empresa_id=e1.id, titulo="Abarrotes Zamora → CDMX",
        tipo_mercancia="Abarrotes", peso_kg=8500,
        origen_ciudad="Zamora", origen_estado="Michoacán",
        destino_ciudad="CDMX", destino_estado="Ciudad de México",
        fecha_recoleccion=datetime(2025, 5, 30),
        tipo_vehiculo_requerido="Torton", precio_ofrecido_mxn=11500,
        precio_negociable=True, estado=EstadoCarga.disponible,
    )
    c2 = Carga(
        empresa_id=e1.id, titulo="Electrodomésticos GDL → Morelia",
        tipo_mercancia="Electrodomésticos", peso_kg=3200,
        origen_ciudad="Guadalajara", origen_estado="Jalisco",
        destino_ciudad="Morelia", destino_estado="Michoacán",
        fecha_recoleccion=datetime(2025, 5, 28),
        tipo_vehiculo_requerido="C3 (3 ejes)", precio_ofrecido_mxn=4800,
        precio_negociable=False, estado=EstadoCarga.disponible,
    )
    db.add_all([c1, c2])
    db.commit()
    db.refresh(c1)
    db.refresh(c2)

    notificar_nueva_carga(db, c1.id)
    notificar_nueva_carga(db, c2.id)

    return {"mensaje": "✅ Datos de prueba creados con notificaciones", "transportistas": 2, "empresa": 1, "cargas": 2}