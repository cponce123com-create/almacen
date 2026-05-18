import os
import sys
import logging
from logging.handlers import RotatingFileHandler
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_wtf.csrf import CSRFProtect
from sqlalchemy import event as sa_event

db = SQLAlchemy()
login_manager = LoginManager()
migrate = Migrate()
csrf = CSRFProtect()


def create_app(testing=False):
    app = Flask(__name__)
    app.config["TESTING"] = testing

    # ------------------------------------------------------------------
    # Logging rotativo (siempre activo excepto en tests)
    # ------------------------------------------------------------------
    if not testing:
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
        if app.config.get("TESTING"):
            app.config["SECRET_KEY"] = "test-secret-key-insecure"
            app.logger.warning(
                "SECRET_KEY no configurado. Usando clave insegura para TESTING."
            )
        else:
            # Modo portable: generar automáticamente si no está configurado
            import secrets as _secrets
            app.config["SECRET_KEY"] = _secrets.token_hex(32)
            app.logger.info(
                "SECRET_KEY generado automáticamente (modo portable)."
            )
            # Guardarlo en .env para sesiones persistentes
            _dotenv_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"
            )
            try:
                with open(_dotenv_path, "a") as _f:
                    _f.write(f"\n# Generado automáticamente por el modo portable\nSECRET_KEY={app.config['SECRET_KEY']}\n")
            except OSError:
                pass  # Si no se puede escribir, no importa, la clave está en memoria
    elif not app.config.get("TESTING") and len(app.config["SECRET_KEY"]) < 16:
        app.logger.warning(
            "SECRET_KEY es muy corta (%d caracteres). "
            "Usa al menos 16 caracteres para mayor seguridad.",
            len(app.config["SECRET_KEY"]),
        )
    app.config["PERMANENT_SESSION_LIFETIME"] = 1800  # 30 minutos
    app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16 MB límite de subida
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["WTF_CSRF_ENABLED"] = not testing
    app.config["WTF_CSRF_TIME_LIMIT"] = 3600  # 1 hora

    # Inicializar extensiones
    db.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)

    login_manager.login_view = "routes.login"
    login_manager.login_message = "Por favor inicia sesión para acceder."
    login_manager.login_message_category = "warning"

    # Registrar blueprints
    from app.routes import routes_bp
    app.register_blueprint(routes_bp)

    # ------------------------------------------------------------------
    # Content Security Policy (CSP)
    # ------------------------------------------------------------------
    if not testing:
        @app.after_request
        def _add_security_headers(response):
            csp = (
                "default-src 'self'; "
                "script-src 'self'; "
                "style-src 'self' 'unsafe-inline'; "
                "img-src 'self' data:; "
                "connect-src 'self'; "
                "frame-ancestors 'none'; "
                "form-action 'self'"
            )
            response.headers["Content-Security-Policy"] = csp
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["X-Frame-Options"] = "DENY"
            response.headers["X-XSS-Protection"] = "0"  # Obsoleto pero seguro
            return response

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
                ("revisado", "VARCHAR(20)"),
                ("locacion", "VARCHAR(100)"),
                ("cod_ant", "VARCHAR(50)"),
            ],
            "entradas": [
                ("oc_id", "INTEGER"),
            ],
        }

        inspector = sa_inspect(db.engine)
        for table_name, columns in _MIGRACIONES.items():
            try:
                existing = {c["name"] for c in inspector.get_columns(table_name)}
            except Exception:
                app.logger.info("Migración: tabla '%s' no existe, se omite.", table_name)
                continue
            for col_name, col_type in columns:
                if col_name in existing:
                    continue
                try:
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
                        "Migración: columna %s agregada a %s.", col_name, table_name,
                    )
                except Exception as exc:
                    app.logger.warning(
                        "Migración: no se pudo agregar %s a %s: %s",
                        col_name, table_name, exc,
                    )
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
