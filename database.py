import os
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import sessionmaker

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./retache.db")

if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(
        DATABASE_URL, connect_args={"check_same_thread": False}
    )
else:
    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,
        pool_recycle=300,
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

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
