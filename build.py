from app.app import app
from app import db

def main():
    with app.app_context():
        print("Creando todas las tablas en la base de datos...")
        db.create_all()
        print("Tablas creadas exitosamente.")
        # Opcional: si quieres que los datos de ejemplo se carguen automáticamente la primera vez,
        # puedes añadir aquí la llamada a tu función de seed.
        # from app.seed import run_seed
        # run_seed()

if __name__ == "__main__":
    main()
