import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import requests
import time
from fastapi import APIRouter, Depends, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from database import get_db
from models import Carga, EstadoCarga
from auth import get_sesion_actual

CONEKTA_API_KEY = "key_o2pOyk863t04xcvxeZtDXyz"
CONEKTA_BASE_URL = "https://api.conekta.io"
HEADERS = {
    "Accept": "application/vnd.conekta-v2.1.0+json",
    "Content-Type": "application/json",
    "Authorization": f"Bearer {CONEKTA_API_KEY}",
}

router = APIRouter(prefix="/pagos", tags=["pagos"])
templates = Jinja2Templates(directory="templates")


def ctx(request, **kwargs):
    return {"request": request, "sesion": get_sesion_actual(request), **kwargs}


def crear_cliente_conekta(nombre: str, email: str) -> str:
    response = requests.post(
        f"{CONEKTA_BASE_URL}/customers",
        headers=HEADERS,
        json={"name": nombre, "email": email, "phone": "+5210000000000"},
    )
    data = response.json()
    print("RESPUESTA CONEKTA CLIENTE:", data)
    if "id" not in data:
        raise Exception(f"Error Conekta: {data}")
    return data["id"]


def crear_orden_conekta(cliente_id: str, descripcion: str, monto_centavos: int, metodo: str) -> dict:
    if metodo == "oxxo":
        payment_method = {"type": "cash", "expires_at": int(time.time()) + 86400 * 3}
    else:
        payment_method = {"type": "spei", "expires_at": int(time.time()) + 86400 * 3}

    payload = {
        "currency": "MXN",
        "customer_info": {"customer_id": cliente_id},
        "line_items": [{"name": descripcion, "unit_price": monto_centavos, "quantity": 1}],
        "charges": [{"payment_method": payment_method}],
    }

    response = requests.post(
        f"{CONEKTA_BASE_URL}/orders",
        headers=HEADERS,
        json=payload,
    )
    return response.json()


@router.get("/carga/{carga_id}", response_class=HTMLResponse)
async def pagina_pago(request: Request, carga_id: int, db: Session = Depends(get_db)):
    sesion = get_sesion_actual(request)
    if not sesion:
        return RedirectResponse(url="/login", status_code=303)

    carga = db.query(Carga).filter(Carga.id == carga_id).first()
    if not carga:
        raise HTTPException(status_code=404, detail="Carga no encontrada")

    comision_retache = round(carga.precio_ofrecido_mxn * 0.05, 2)
    total = round(carga.precio_ofrecido_mxn + comision_retache, 2)

    return templates.TemplateResponse("pago.html", ctx(request,
        carga=carga,
        comision_retache=comision_retache,
        total=total,
    ))


@router.post("/carga/{carga_id}/procesar")
async def procesar_pago(
    request: Request,
    carga_id: int,
    metodo: str = Form(...),
    nombre_cliente: str = Form(...),
    email_cliente: str = Form(...),
    db: Session = Depends(get_db),
):
    sesion = get_sesion_actual(request)
    if not sesion:
        return RedirectResponse(url="/login", status_code=303)

    carga = db.query(Carga).filter(Carga.id == carga_id).first()
    if not carga:
        raise HTTPException(status_code=404, detail="Carga no encontrada")

    comision = round(carga.precio_ofrecido_mxn * 0.05, 2)
    total = round(carga.precio_ofrecido_mxn + comision, 2)
    total_centavos = int(total * 100)

    descripcion = f"Flete RETACHE: {carga.tipo_mercancia} — {carga.origen_ciudad} → {carga.destino_ciudad}"

    try:
        cliente_id = crear_cliente_conekta(nombre_cliente, email_cliente)
        orden = crear_orden_conekta(cliente_id, descripcion, total_centavos, metodo)

        if "object" not in orden:
            raise Exception(orden.get("details", [{}])[0].get("message", "Error desconocido"))

        cargo = orden["charges"]["data"][0]["payment_method"]

        if metodo == "oxxo":
            referencia_oxxo = cargo.get("reference", "N/A")
            return templates.TemplateResponse("pago_resultado.html", ctx(request,
                exito=True,
                metodo="oxxo",
                referencia_oxxo=referencia_oxxo,
                carga=carga,
                total=total,
            ))

        elif metodo == "spei":
            clabe = cargo.get("clabe", "N/A")
            banco = cargo.get("bank", "STP")
            return templates.TemplateResponse("pago_resultado.html", ctx(request,
                exito=True,
                metodo="spei",
                clabe=clabe,
                banco=banco,
                carga=carga,
                total=total,
            ))

    except Exception as e:
        return templates.TemplateResponse("pago_resultado.html", ctx(request,
            exito=False,
            error=str(e),
            carga=carga,
            total=total,
        ))