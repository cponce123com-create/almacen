import os
import logging
from logging.handlers import RotatingFileHandler
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate
from sqlalchemy import event as sa_event

db = SQLAlchemy()
login_manager = LoginManager()
migrate = Migrate()


def create_app(testing=False):
    app = Flask(__name__)
    app.config["TESTING"] = testing

    # ------------------------------------------------------------------
    # Logging (archivo rotativo útil para debug en Render)
    # ------------------------------------------------------------------
    if not app.debug and not testing:
        log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "logs")
        os.makedirs(log_dir, exist_ok=True)
        log_file = os.path.join(log_dir, "almacen.log")
        handler = RotatingFileHandler(log_file, maxBytes=5 * 1024 * 1024, backupCount=3)
        handler.setLevel(logging.INFO)
        formatter = logging.Formatter(
            "%(asctime)s %(levelname)s [%(module)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        app.logger.addHandler(handler)
        app.logger.setLevel(logging.INFO)
        app.logger.info("=== Almacén iniciado ===")

    # ------------------------------------------------------------------
    # Configuración de base de datos
    # SQLite por defecto (100% offline), PostgreSQL si DATABASE_URL existe
    # ------------------------------------------------------------------
    basedir = os.path.abspath(os.path.dirname(__file__))
    database_url = os.environ.get("DATABASE_URL")
    if database_url:
        if database_url.startswith("postgres://"):
            database_url = database_url.replace("postgres://", "postgresql://", 1)
        app.config["SQLALCHEMY_DATABASE_URI"] = database_url
        # Pool settings solo para PostgreSQL
        if not database_url.startswith("sqlite"):
            app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
                "pool_size": 5,
                "pool_recycle": 300,
                "pool_pre_ping": True,
            }
    else:
        app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{os.path.join(basedir, 'almacen.db')}"

    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY")
    if not app.config["SECRET_KEY"]:
        if app.debug or app.config.get("TESTING"):
            app.config["SECRET_KEY"] = "dev-secret-key-insecure"
        else:
            raise RuntimeError(
                "SECRET_KEY no está configurado. "
                "Define la variable de entorno SECRET_KEY antes de iniciar."
            )
    app.config["PERMANENT_SESSION_LIFETIME"] = 1800  # 30 minutos
    app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16 MB límite de subida

    # Inicializar extensiones
    db.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)

    login_manager.login_view = "routes.login"
    login_manager.login_message = "Por favor inicia sesión para acceder."
    login_manager.login_message_category = "warning"

    # Registrar blueprints
    from app.routes import routes_bp
    app.register_blueprint(routes_bp)

    # ------------------------------------------------------------------
    # Crear tablas y configurar SQLite WAL mode
    # ------------------------------------------------------------------
    with app.app_context():
        from app.models import User, Producto, Entrada, Salida, AuditLog, Familia, Almacen, OrdenCompra
        db.create_all()

        # ------------------------------------------------------------------
        # Migración segura: agregar columnas faltantes en tablas existentes
        # (db.create_all() no altera tablas ya creadas, solo crea nuevas)
        # ------------------------------------------------------------------
        from sqlalchemy import inspect as sa_inspect

        _MIGRACIONES = {
            "productos": [
                ("familia_id", "INTEGER"),
                ("almacen_id", "INTEGER"),
            ],
            "entradas": [
                ("oc_id", "INTEGER"),
            ],
        }

        try:
            inspector = sa_inspect(db.engine)
            for table_name, columns in _MIGRACIONES.items():
                try:
                    existing = {c["name"] for c in inspector.get_columns(table_name)}
                except Exception:
                    app.logger.warning("Migración: tabla %s no existe, se omite.", table_name)
                    continue
                for col_name, col_type in columns:
                    if col_name not in existing:
                        app.logger.info(
                            "Migración: agregando columna %s a %s...",
                            col_name, table_name,
                        )
                        db.session.execute(
                            db.text(
                                f"ALTER TABLE {table_name} ADD COLUMN {col_name} {col_type}"
                            )
                        )
                        db.session.commit()
                        app.logger.info(
                            "Migración: columna %s agregada a %s.",
                            col_name, table_name,
                        )
        except Exception as exc:
            app.logger.warning("Migración de columnas no aplicable: %s", exc)
            db.session.rollback()

        # Crear almacén por defecto si no existe ninguno
        if Almacen.query.count() == 0:
            default = Almacen(codigo="ALM-01", nombre="Almacén Principal", direccion="")
            db.session.add(default)
            db.session.commit()

        # Migrar familias existentes desde el campo texto al modelo Familia
        familias_existentes = {f.nombre for f in Familia.query.all()}
        familias_en_uso = set()
        for p in Producto.query.filter(Producto.familia.isnot(None), Producto.familia != "").all():
            if p.familia and p.familia not in familias_existentes:
                familias_en_uso.add(p.familia)
        for nombre in familias_en_uso:
            f = Familia(nombre=nombre)
            db.session.add(f)
            familias_existentes.add(nombre)
        if familias_en_uso:
            db.session.commit()
            # Vincular productos a las nuevas familias
            for p in Producto.query.filter(Producto.familia.isnot(None), Producto.familia != "", Producto.familia_id.is_(None)).all():
                f = Familia.query.filter_by(nombre=p.familia).first()
                if f:
                    p.familia_id = f.id
            db.session.commit()

        # Activar PRAGMA optimizados para SQLite (WAL mode = mejor concurrencia)
        if "sqlite" in app.config["SQLALCHEMY_DATABASE_URI"]:
            sa_event.listen(db.engine, "connect", _sqlite_connect_pragma)

    return app


def _sqlite_connect_pragma(dbapi_connection, connection_record):
    """Configurar PRAGMAs de SQLite al abrir cada conexión."""
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA foreign_keys=ON")
    finally:
        cursor.close()
