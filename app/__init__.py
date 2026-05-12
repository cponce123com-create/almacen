import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate

db = SQLAlchemy()
login_manager = LoginManager()
migrate = Migrate()


def create_app():
    app = Flask(__name__)

    # Configuración de base de datos: SQLite por defecto, PostgreSQL si DATABASE_URL existe
    basedir = os.path.abspath(os.path.dirname(__file__))
    database_url = os.environ.get("DATABASE_URL")
    if database_url:
        # Para Render/Neon: reemplazar postgres:// por postgresql:// si es necesario
        if database_url.startswith("postgres://"):
            database_url = database_url.replace("postgres://", "postgresql://", 1)
        app.config["SQLALCHEMY_DATABASE_URI"] = database_url
    else:
        app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{os.path.join(basedir, 'almacen.db')}"

    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "clave-secreta-desarrollo-2024")

    db.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)

    login_manager.login_view = "routes.login"
    login_manager.login_message = "Por favor inicia sesión para acceder."
    login_manager.login_message_category = "warning"

    from app.routes import routes_bp
    app.register_blueprint(routes_bp)

    with app.app_context():
        from app.models import User, Producto, Entrada, Salida
        db.create_all()

    return app
