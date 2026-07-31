ruta = 'main.py'
with open(ruta, 'r', encoding='utf-8') as f:
    m = f.read()

viejo = '''    carga.transportista_id = transportista_id
    carga.estado = EstadoCarga.asignada
    carga.fecha_asignacion = datetime.utcnow()
    transportista.disponible = False
    db.commit()
    return RedirectResponse(url=f"/cargas/{carga_id}", status_code=303)'''

nuevo = '''    carga.transportista_id = transportista_id
    carga.estado = EstadoCarga.asignada
    carga.fecha_asignacion = datetime.utcnow()
    transportista.disponible = False

    db.add(Notificacion(
        empresa_id=carga.empresa_id,
        titulo=f"{transportista.nombre} {transportista.apellidos} tomó tu carga",
        mensaje=f"{carga.tipo_mercancia}: {carga.origen_ciudad} → {carga.destino_ciudad}. Ya puedes proceder con el pago.",
        url=f"/cargas/{carga_id}",
    ))

    db.commit()
    return RedirectResponse(url=f"/cargas/{carga_id}", status_code=303)'''

if 'tomó tu carga' in m:
    print("Ya esta corregido. Sin cambios.")
elif viejo in m:
    m = m.replace(viejo, nuevo, 1)
    with open(ruta, 'w', encoding='utf-8') as f:
        f.write(m)
    print("Notificacion a la empresa al tomar carga OK")
else:
    print("NO encontrado. Revisar manual.")