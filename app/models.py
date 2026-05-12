from datetime import datetime, timezone
from app import db, login_manager
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash


class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f"<User {self.username}>"


class Producto(db.Model):
    __tablename__ = "productos"
    id = db.Column(db.Integer, primary_key=True)
    codigo = db.Column(db.String(50), unique=True, nullable=False, index=True)
    cod_catalogo = db.Column(db.String(50), nullable=True, default="")
    descripcion = db.Column(db.String(300), nullable=False)
    um = db.Column(db.String(20), nullable=False, default="UND")
    familia = db.Column(db.String(100), nullable=True, default="")
    stock_actual = db.Column(db.Float, nullable=False, default=0.0)
    stock_minimo = db.Column(db.Float, nullable=False, default=0.0)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    entradas = db.relationship("Entrada", backref="producto", lazy="dynamic")
    salidas = db.relationship("Salida", backref="producto", lazy="dynamic")

    def __repr__(self):
        return f"<Producto {self.codigo} - {self.descripcion}>"

    @property
    def stock_bajo(self):
        return self.stock_actual <= self.stock_minimo


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
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

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


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))
