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


def create_app():
    app = Flask(__name__)

    # ------------------------------------------------------------------
    # Logging (archivo rotativo útil para debug en Render)
    # ------------------------------------------------------------------
    if not app.debug:
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
        app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
            "pool_size": 5,
            "pool_recycle": 300,
            "pool_pre_ping": True,
        }
    else:
        app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{os.path.join(basedir, 'almacen.db')}"

    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "clave-secreta-desarrollo-2024")
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
        from app.models import User, Producto, Entrada, Salida
        db.create_all()

        # Activar PRAGMA optimizados para SQLite (WAL mode = mejor concurrencia)
        if "sqlite" in app.config["SQLALCHEMY_DATABASE_URI"]:
            engine = db.get_engine()
            sa_event.listen(engine, "connect", _sqlite_connect_pragma)

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
