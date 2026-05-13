import os
from datetime import datetime, timezone
from app import db, login_manager
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash


class Almacen(db.Model):
    __tablename__ = "almacenes"
    id = db.Column(db.Integer, primary_key=True)
    codigo = db.Column(db.String(20), unique=True, nullable=False)
    nombre = db.Column(db.String(100), nullable=False)
    direccion = db.Column(db.String(200), default="")

    def __repr__(self):
        return f"<Almacen {self.codigo}>"


class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)

    ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "cponce123.com@gmail.com")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def is_admin(self):
        return self.username == self.ADMIN_USERNAME

    def __repr__(self):
        return f"<User {self.username}>"


class Familia(db.Model):
    __tablename__ = "familias"
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), unique=True, nullable=False, index=True)
    color = db.Column(db.String(7), nullable=False, default="#6c757d")

    productos = db.relationship("Producto", backref="familia_rel", lazy="dynamic")

    def __repr__(self):
        return f"<Familia {self.nombre}>"


class Producto(db.Model):
    __tablename__ = "productos"
    id = db.Column(db.Integer, primary_key=True)
    codigo = db.Column(db.String(50), unique=True, nullable=False, index=True)
    cod_catalogo = db.Column(db.String(50), nullable=True, default="")
    descripcion = db.Column(db.String(300), nullable=False)
    um = db.Column(db.String(20), nullable=False, default="UND")
    familia = db.Column(db.String(100), nullable=True, default="")
    familia_id = db.Column(db.Integer, db.ForeignKey("familias.id"), nullable=True, index=True)
    almacen_id = db.Column(db.Integer, db.ForeignKey("almacenes.id"), nullable=True)
    stock_actual = db.Column(db.Float, nullable=False, default=0.0)
    stock_minimo = db.Column(db.Float, nullable=False, default=0.0)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    entradas = db.relationship("Entrada", backref="producto", lazy="dynamic")
    salidas = db.relationship("Salida", backref="producto", lazy="dynamic")
    almacen = db.relationship("Almacen", backref="productos")

    def __repr__(self):
        return f"<Producto {self.codigo} - {self.descripcion}>"

    @property
    def stock_bajo(self):
        return self.stock_actual <= self.stock_minimo

    @property
    def familia_nombre(self):
        """Retorna el nombre de la familia (desde FK o campo texto)."""
        if self.familia_rel:
            return self.familia_rel.nombre
        return self.familia or "—"


class OrdenCompra(db.Model):
    __tablename__ = "ordenes_compra"
    id = db.Column(db.Integer, primary_key=True)
    numero = db.Column(db.String(50), unique=True, nullable=False)
    proveedor = db.Column(db.String(200), default="")
    estado = db.Column(db.String(20), default="PENDIENTE")  # PENDIENTE, PARCIAL, CERRADA
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def __repr__(self):
        return f"<OC {self.numero} ({self.estado})>"


class Entrada(db.Model):
    __tablename__ = "entradas"
    id = db.Column(db.Integer, primary_key=True)
    producto_id = db.Column(db.Integer, db.ForeignKey("productos.id"), nullable=False)
    cantidad = db.Column(db.Float, nullable=False, default=0.0)
    um = db.Column(db.String(20), nullable=True, default="UND")
    zona = db.Column(db.String(50), nullable=True, default="")
    ubicacion = db.Column(db.String(100), nullable=True, default="")
    alm = db.Column(db.String(50), nullable=True, default="ALM-01")
    fecha_ingreso = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    oc = db.Column(db.String(50), nullable=True, default="")
    guia_remision = db.Column(db.String(50), nullable=True, default="")
    familia = db.Column(db.String(100), nullable=True, default="")
    oc_id = db.Column(db.Integer, db.ForeignKey("ordenes_compra.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    orden_compra = db.relationship("OrdenCompra", backref="entradas")

    def __repr__(self):
        return f"<Entrada {self.id} - Prod:{self.producto_id} Cant:{self.cantidad}>"


class Salida(db.Model):
    __tablename__ = "salidas"
    id = db.Column(db.Integer, primary_key=True)
    producto_id = db.Column(db.Integer, db.ForeignKey("productos.id"), nullable=False)
    cantidad = db.Column(db.Float, nullable=False, default=0.0)
    um = db.Column(db.String(20), nullable=True, default="UND")
    fecha_salida = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    nro_vale = db.Column(db.String(50), nullable=True, default="")
    oi = db.Column(db.String(50), nullable=True, default="")
    c_costo = db.Column(db.String(100), nullable=True, default="")
    maquina = db.Column(db.String(100), nullable=True, default="")
    categoria = db.Column(db.String(100), nullable=True, default="")
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def __repr__(self):
        return f"<Salida {self.id} - Prod:{self.producto_id} Cant:{self.cantidad}>"


class AuditLog(db.Model):
    __tablename__ = "audit_log"
    id = db.Column(db.Integer, primary_key=True)
    tabla = db.Column(db.String(50), nullable=False, index=True)
    registro_id = db.Column(db.Integer, nullable=False)
    campo = db.Column(db.String(50), nullable=False)
    valor_anterior = db.Column(db.Text, default="")
    valor_nuevo = db.Column(db.Text, default="")
    usuario = db.Column(db.String(80), nullable=False)
    timestamp = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)

    def __repr__(self):
        return f"<AuditLog {self.tabla}#{self.registro_id} {self.campo}>"


def audit_log(tabla, registro_id, campo, valor_anterior, valor_nuevo, usuario=None):
    """Helper para registrar un cambio en el log de auditoría."""
    if valor_anterior == valor_nuevo:
        return
    entry = AuditLog(
        tabla=tabla,
        registro_id=registro_id,
        campo=campo,
        valor_anterior=str(valor_anterior) if valor_anterior is not None else "",
        valor_nuevo=str(valor_nuevo) if valor_nuevo is not None else "",
        usuario=usuario or "sistema",
    )
    db.session.add(entry)


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))
