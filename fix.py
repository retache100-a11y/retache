ruta = 'database.py'
with open(ruta, 'r', encoding='utf-8') as f:
    d = f.read()

if 'def asegurar_columnas' in d:
    print("Ya existe la funcion. Sin cambios.")
    raise SystemExit

extra = '''

def asegurar_columnas():
    """Agrega columnas faltantes sin borrar datos (migracion simple)."""
    from sqlalchemy import text, inspect
    faltantes = [
        ("notificaciones", "empresa_id", "INTEGER"),
    ]
    insp = inspect(engine)
    with engine.begin() as conn:
        for tabla, columna, tipo in faltantes:
            try:
                if tabla not in insp.get_table_names():
                    continue
                cols = [c["name"] for c in insp.get_columns(tabla)]
                if columna not in cols:
                    conn.execute(text(f"ALTER TABLE {tabla} ADD COLUMN {columna} {tipo}"))
                    print(f"[migracion] Columna agregada: {tabla}.{columna}")
            except Exception as e:
                print(f"[migracion] Error en {tabla}.{columna}: {e}")
'''

d = d + extra
with open(ruta, 'w', encoding='utf-8') as f:
    f.write(d)
print("Funcion asegurar_columnas agregada a database.py")

# Llamarla en main.py despues de crear las tablas
ruta2 = 'main.py'
with open(ruta2, 'r', encoding='utf-8') as f:
    m = f.read()

viejo = 'Base.metadata.create_all(bind=engine)'
nuevo = 'Base.metadata.create_all(bind=engine)\nfrom database import asegurar_columnas\nasegurar_columnas()'

if 'asegurar_columnas()' in m:
    print("main.py ya la llama. Sin cambios.")
elif viejo in m:
    m = m.replace(viejo, nuevo, 1)
    with open(ruta2, 'w', encoding='utf-8') as f:
        f.write(m)
    print("main.py ahora ejecuta la migracion al arrancar")
else:
    print("NO se encontro create_all en main.py. Revisar manual.")