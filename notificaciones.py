import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from sqlalchemy.orm import Session
from models import Transportista, Carga, EstadoCarga
from database import SessionLocal
import json


def crear_notificacion(db: Session, transportista_id: int, titulo: str, mensaje: str, url: str = "/cargas"):
    from models import Notificacion
    notif = Notificacion(
        transportista_id=transportista_id,
        titulo=titulo,
        mensaje=mensaje,
        url=url,
    )
    db.add(notif)
    db.commit()


def notificar_nueva_carga(db: Session, carga_id: int):
    carga = db.query(Carga).filter(Carga.id == carga_id).first()
    if not carga:
        return

    transportistas = db.query(Transportista).filter(
        Transportista.activo == True,
        Transportista.disponible == True,
        Transportista.carta_porte_habilitada == True,
    ).all()

    notificados = 0
    for t in transportistas:
        rutas = []
        if t.rutas_frecuentes:
            try:
                rutas = json.loads(t.rutas_frecuentes)
            except Exception:
                rutas = []

        coincide = False
        for ruta in rutas:
            partes = ruta.lower().replace("→", "->").split("->")
            if len(partes) == 2:
                origen_ruta = partes[0].strip()
                destino_ruta = partes[1].strip()
                if (origen_ruta in carga.origen_ciudad.lower() or
                    carga.origen_ciudad.lower() in origen_ruta or
                    destino_ruta in carga.destino_ciudad.lower() or
                    carga.destino_ciudad.lower() in destino_ruta):
                    coincide = True
                    break

        if not coincide:
            coincide = (
                t.latitud and
                abs(t.latitud - (carga.origen_lat or 19.98)) < 2.0
            )

        if coincide:
            crear_notificacion(
                db=db,
                transportista_id=t.id,
                titulo="Nueva carga disponible en tu ruta",
                mensaje=f"{carga.tipo_mercancia} · {carga.origen_ciudad} → {carga.destino_ciudad} · ${carga.precio_ofrecido_mxn:,.0f}",
                url=f"/cargas/{carga.id}",
            )
            notificados += 1

    return notificados


def marcar_leida(db: Session, notificacion_id: int, transportista_id: int):
    from models import Notificacion
    notif = db.query(Notificacion).filter(
        Notificacion.id == notificacion_id,
        Notificacion.transportista_id == transportista_id,
    ).first()
    if notif:
        notif.leida = True
        db.commit()


def obtener_notificaciones(db: Session, transportista_id: int, solo_no_leidas: bool = False):
    from models import Notificacion
    query = db.query(Notificacion).filter(
        Notificacion.transportista_id == transportista_id
    )
    if solo_no_leidas:
        query = query.filter(Notificacion.leida == False)
    return query.order_by(Notificacion.fecha.desc()).limit(20).all()


def contar_no_leidas(db: Session, transportista_id: int) -> int:
    from models import Notificacion
    return db.query(Notificacion).filter(
        Notificacion.transportista_id == transportista_id,
        Notificacion.leida == False,
    ).count()