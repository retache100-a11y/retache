from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Text, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
from database import Base


class EstadoDocumento(str, enum.Enum):
    vigente = "vigente"
    por_vencer = "por_vencer"
    vencido = "vencido"
    pendiente = "pendiente"


class EstadoCarga(str, enum.Enum):
    disponible = "disponible"
    en_negociacion = "en_negociacion"
    asignada = "asignada"
    en_transito = "en_transito"
    completada = "completada"
    cancelada = "cancelada"


class Transportista(Base):
    __tablename__ = "transportistas"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(100), nullable=False)
    apellidos = Column(String(100), nullable=False)
    telefono = Column(String(15), nullable=False)
    email = Column(String(120), unique=True, index=True, nullable=False)
    contrasena_hash = Column(String(200), nullable=False)

    rfc = Column(String(13), unique=True, index=True, nullable=False)
    rfc_verificado = Column(Boolean, default=False)

    num_licencia_federal = Column(String(50), nullable=True)
    licencia_estado = Column(String(20), default=EstadoDocumento.pendiente)
    licencia_vencimiento = Column(DateTime, nullable=True)

    num_poliza_seguro = Column(String(80), nullable=True)
    seguro_estado = Column(String(20), default=EstadoDocumento.pendiente)
    seguro_vencimiento = Column(DateTime, nullable=True)
    seguro_cobertura_mxn = Column(Float, nullable=True)

    verificacion_vehicular_estado = Column(String(20), default=EstadoDocumento.pendiente)
    verificacion_vehicular_vencimiento = Column(DateTime, nullable=True)

    tarjeta_circulacion_estado = Column(String(20), default=EstadoDocumento.pendiente)

    carta_porte_habilitada = Column(Boolean, default=False)

    tipo_vehiculo = Column(String(30), nullable=True)
    marca_vehiculo = Column(String(50), nullable=True)
    modelo_vehiculo = Column(String(50), nullable=True)
    anio_vehiculo = Column(Integer, nullable=True)
    placa = Column(String(10), nullable=True)
    capacidad_kg = Column(Float, nullable=True)

    latitud = Column(Float, nullable=True)
    longitud = Column(Float, nullable=True)
    disponible = Column(Boolean, default=True)

    foto_url = Column(String(200), nullable=True)
    rutas_frecuentes = Column(Text, nullable=True)
    calificacion_promedio = Column(Float, default=0.0)
    total_viajes = Column(Integer, default=0)
    porcentaje_puntualidad = Column(Float, default=100.0)

    fecha_registro = Column(DateTime, server_default=func.now())
    activo = Column(Boolean, default=True)
    email_verificado = Column(Boolean, default=False)
    token_verificacion = Column(String(200), nullable=True)
    token_reset_password = Column(String(200), nullable=True)
    token_reset_expira = Column(DateTime, nullable=True)

    cargas = relationship("Carga", back_populates="transportista")
    mensajes_enviados = relationship("Mensaje", foreign_keys="Mensaje.remitente_transportista_id", back_populates="remitente_transportista")
    resenas = relationship("Resena", back_populates="transportista")
    notificaciones = relationship("Notificacion", back_populates="transportista")
    rutas_disponibles = relationship("RutaDisponible", back_populates="transportista")


class Empresa(Base):
    __tablename__ = "empresas"

    id = Column(Integer, primary_key=True, index=True)
    razon_social = Column(String(200), nullable=False)
    nombre_comercial = Column(String(200), nullable=True)
    telefono = Column(String(15), nullable=False)
    email = Column(String(120), unique=True, index=True, nullable=False)
    contrasena_hash = Column(String(200), nullable=False)

    rfc = Column(String(12), unique=True, index=True, nullable=False)
    rfc_verificado = Column(Boolean, default=False)

    num_acta_constitutiva = Column(String(100), nullable=True)
    acta_constitutiva_verificada = Column(Boolean, default=False)
    giro = Column(String(100), nullable=True)

    calle = Column(String(200), nullable=True)
    colonia = Column(String(100), nullable=True)
    municipio = Column(String(100), nullable=True)
    estado = Column(String(50), nullable=True)
    cp = Column(String(5), nullable=True)

    nombre_contacto = Column(String(150), nullable=True)
    puesto_contacto = Column(String(100), nullable=True)

    logo_url = Column(String(200), nullable=True)
    calificacion_promedio = Column(Float, default=0.0)
    total_cargas_publicadas = Column(Integer, default=0)

    fecha_registro = Column(DateTime, server_default=func.now())
    activo = Column(Boolean, default=True)
    email_verificado = Column(Boolean, default=False)
    token_verificacion = Column(String(200), nullable=True)
    token_reset_password = Column(String(200), nullable=True)
    token_reset_expira = Column(DateTime, nullable=True)

    cargas_publicadas = relationship("Carga", back_populates="empresa")
    mensajes_enviados = relationship("Mensaje", foreign_keys="Mensaje.remitente_empresa_id", back_populates="remitente_empresa")


class Carga(Base):
    __tablename__ = "cargas"

    id = Column(Integer, primary_key=True, index=True)
    empresa_id = Column(Integer, ForeignKey("empresas.id"), nullable=False)
    transportista_id = Column(Integer, ForeignKey("transportistas.id"), nullable=True)

    titulo = Column(String(150), nullable=False)
    descripcion = Column(Text, nullable=True)
    tipo_mercancia = Column(String(100), nullable=False)
    peso_kg = Column(Float, nullable=False)
    volumen_m3 = Column(Float, nullable=True)
    requiere_refrigeracion = Column(Boolean, default=False)
    mercancia_peligrosa = Column(Boolean, default=False)

    origen_ciudad = Column(String(100), nullable=False)
    origen_estado = Column(String(50), nullable=False)
    origen_lat = Column(Float, nullable=True)
    origen_lng = Column(Float, nullable=True)
    destino_ciudad = Column(String(100), nullable=False)
    destino_estado = Column(String(50), nullable=False)
    destino_lat = Column(Float, nullable=True)
    destino_lng = Column(Float, nullable=True)

    fecha_recoleccion = Column(DateTime, nullable=False)
    fecha_entrega_estimada = Column(DateTime, nullable=True)
    tipo_vehiculo_requerido = Column(String(30), nullable=True)
    precio_ofrecido_mxn = Column(Float, nullable=False)
    precio_negociable = Column(Boolean, default=True)

    estado = Column(String(30), default=EstadoCarga.disponible)
    fecha_publicacion = Column(DateTime, server_default=func.now())
    fecha_asignacion = Column(DateTime, nullable=True)
    fecha_completada = Column(DateTime, nullable=True)

    carta_porte_generada = Column(Boolean, default=False)
    carta_porte_uuid = Column(String(100), nullable=True)
    carta_porte_xml = Column(Text, nullable=True)

    empresa = relationship("Empresa", back_populates="cargas_publicadas")
    transportista = relationship("Transportista", back_populates="cargas")
    mensajes = relationship("Mensaje", back_populates="carga")
    resenas = relationship("Resena", back_populates="carga")


class Mensaje(Base):
    __tablename__ = "mensajes"

    id = Column(Integer, primary_key=True, index=True)
    carga_id = Column(Integer, ForeignKey("cargas.id"), nullable=True)
    remitente_transportista_id = Column(Integer, ForeignKey("transportistas.id"), nullable=True)
    remitente_empresa_id = Column(Integer, ForeignKey("empresas.id"), nullable=True)
    contenido = Column(Text, nullable=False)
    leido = Column(Boolean, default=False)
    fecha_envio = Column(DateTime, server_default=func.now())

    carga = relationship("Carga", back_populates="mensajes")
    remitente_transportista = relationship("Transportista", foreign_keys=[remitente_transportista_id], back_populates="mensajes_enviados")
    remitente_empresa = relationship("Empresa", foreign_keys=[remitente_empresa_id], back_populates="mensajes_enviados")


class Resena(Base):
    __tablename__ = "resenas"

    id = Column(Integer, primary_key=True, index=True)
    carga_id = Column(Integer, ForeignKey("cargas.id"), nullable=False)
    transportista_id = Column(Integer, ForeignKey("transportistas.id"), nullable=False)
    empresa_id = Column(Integer, ForeignKey("empresas.id"), nullable=False)
    calificacion = Column(Integer, nullable=False)
    comentario = Column(Text, nullable=True)
    fecha = Column(DateTime, server_default=func.now())

    carga = relationship("Carga", back_populates="resenas")
    transportista = relationship("Transportista", back_populates="resenas")
    empresa = relationship("Empresa")


class Notificacion(Base):
    __tablename__ = "notificaciones"

    id = Column(Integer, primary_key=True, index=True)
    transportista_id = Column(Integer, ForeignKey("transportistas.id"), nullable=False)
    titulo = Column(String(200), nullable=False)
    mensaje = Column(Text, nullable=False)
    url = Column(String(200), default="/cargas")
    leida = Column(Boolean, default=False)
    fecha = Column(DateTime, server_default=func.now())

    transportista = relationship("Transportista", back_populates="notificaciones")


class RutaDisponible(Base):
    __tablename__ = "rutas_disponibles"

    id = Column(Integer, primary_key=True, index=True)
    transportista_id = Column(Integer, ForeignKey("transportistas.id"), nullable=False)

    origen_ciudad = Column(String(100), nullable=False)
    origen_estado = Column(String(50), nullable=False)
    destino_ciudad = Column(String(100), nullable=False)
    destino_estado = Column(String(50), nullable=False)

    fecha_salida = Column(DateTime, nullable=False)
    capacidad_disponible_kg = Column(Float, nullable=False)
    precio_por_kg = Column(Float, nullable=True)
    precio_fijo = Column(Float, nullable=True)
    precio_negociable = Column(Boolean, default=True)

    activa = Column(Boolean, default=True)
    fecha_publicacion = Column(DateTime, server_default=func.now())

    transportista = relationship("Transportista", back_populates="rutas_disponibles")
    mensajes = relationship("MensajeRuta", back_populates="ruta")


class MensajeRuta(Base):
    __tablename__ = "mensajes_ruta"

    id = Column(Integer, primary_key=True, index=True)
    ruta_id = Column(Integer, ForeignKey("rutas_disponibles.id"), nullable=False)
    remitente_transportista_id = Column(Integer, ForeignKey("transportistas.id"), nullable=True)
    remitente_empresa_id = Column(Integer, ForeignKey("empresas.id"), nullable=True)
    contenido = Column(Text, nullable=False)
    fecha_envio = Column(DateTime, server_default=func.now())

    ruta = relationship("RutaDisponible", back_populates="mensajes")