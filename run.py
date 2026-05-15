#!/usr/bin/env python3
"""
ALMACENERO - Lanzador Portable (Offline)
==========================================
Inicia la aplicacion Flask con SQLite, auto-configura el entorno
virtual, instala dependencias y abre el navegador.

Uso:
    python run.py              # Inicia con puerto por defecto (5000)
    python run.py --port 8080  # Puerto personalizado
    python run.py --seed       # Recargar datos de demostracion
    python run.py --reset      # Resetear BD y cargar datos demo
    python run.py --no-browser # No abrir navegador automaticamente
"""

import os
import sys
import subprocess
import argparse
import platform
import time

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
VENV_DIR = os.path.join(PROJECT_DIR, ".venv")
REQUIREMENTS_FILE = os.path.join(PROJECT_DIR, "requirements-lite.txt")
REQUIREMENTS_FILE_FALLBACK = os.path.join(PROJECT_DIR, "requirements.txt")
DB_PATH = os.path.join(PROJECT_DIR, "app", "almacen.db")
ENV_FILE = os.path.join(PROJECT_DIR, ".env")

# Ejecutables segun SO
if platform.system() == "Windows":
    PYTHON = os.path.join(VENV_DIR, "Scripts", "python.exe")
    PIP = os.path.join(VENV_DIR, "Scripts", "pip.exe")
else:
    PYTHON = os.path.join(VENV_DIR, "bin", "python")
    PIP = os.path.join(VENV_DIR, "bin", "pip")


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------

def _log(msg):
    print("  >> " + msg)


def _check_python_version():
    if sys.version_info < (3, 9):
        print("  ERROR: Se requiere Python >= 3.9 (tienes {}.{})".format(
            sys.version_info[0], sys.version_info[1]))
        sys.exit(1)


def _venv_exists():
    return os.path.isfile(PYTHON)


def _create_venv():
    _log("Creando entorno virtual...")
    result = subprocess.run(
        [sys.executable, "-m", "venv", VENV_DIR],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        print("  ERROR al crear el entorno virtual: {}".format(result.stderr))
        sys.exit(1)
    _log("Entorno virtual creado.")


def _install_dependencies():
    req_file = REQUIREMENTS_FILE
    if not os.path.exists(req_file):
        req_file = REQUIREMENTS_FILE_FALLBACK
        if not os.path.exists(req_file):
            print("  ERROR: No se encontro ningun archivo requirements*.txt")
            sys.exit(1)

    _log("Instalando dependencias desde {}...".format(os.path.basename(req_file)))
    result = subprocess.run(
        [PIP, "install", "--quiet", "-r", req_file],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        print("  ERROR al instalar dependencias: {}".format(result.stderr))
        print("  Asegurate de tener conexion a internet la PRIMERA vez.")
        sys.exit(1)
    _log("Dependencias instaladas.")


def _ensure_env_file():
    if not os.path.exists(ENV_FILE):
        with open(ENV_FILE, "w") as f:
            f.write("# Archivo de configuracion local (generado por run.py)" + os.linesep)
            f.write("# SECRET_KEY se genera automaticamente si no esta definida" + os.linesep)
        _log("Archivo .env creado (usar SECRET_KEY autogenerada).")


def _seed_data():
    _log("Cargando datos de demostracion...")
    result = subprocess.run(
        [PYTHON, "-m", "app.seed", "--demo"],
        capture_output=True, text=True,
    )
    print(result.stdout)
    if result.returncode != 0:
        print("  ERROR en seed: {}".format(result.stderr))
    else:
        _log("Datos de demostracion cargados.")


def _reset_db():
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
        _log("Base de datos eliminada.")
    else:
        _log("No existia base de datos previa.")
    _seed_data()


def _open_browser(url, delay=2.0):
    _log("Abriendo navegador en {} ...".format(url))
    try:
        time.sleep(delay)
        if platform.system() == "Windows":
            os.system("start " + url)
        elif platform.system() == "Darwin":
            subprocess.Popen(["open", url])
        else:
            try:
                subprocess.Popen(
                    ["xdg-open", url],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            except FileNotFoundError:
                import webbrowser
                webbrowser.open(url)
    except Exception:
        _log("No se pudo abrir el navegador. Accede manualmente a: " + url)


def _find_free_port(start=5000):
    import socket
    for port in range(start, start + 100):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    _log("  ADVERTENCIA: No se encontro puerto libre. Usando {}.".format(start))
    return start


# ---------------------------------------------------------------------------
# Punto de entrada principal
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="ALMACENERO - Lanzador Portable")
    parser.add_argument("--port", type=int, default=0,
                        help="Puerto del servidor (0 = auto, default: 5000)")
    parser.add_argument("--seed", action="store_true",
                        help="Cargar datos de demostracion")
    parser.add_argument("--reset", action="store_true",
                        help="Resetear base de datos y cargar datos demo")
    parser.add_argument("--no-browser", action="store_true",
                        help="No abrir el navegador automaticamente")
    parser.add_argument("--host", type=str, default="127.0.0.1",
                        help="Host de escucha (default: 127.0.0.1)")
    args = parser.parse_args()

    _NL = os.linesep
    print("=" * 55)
    print("  ALMACENERO - Control de Inventarios")
    print("  Modo Portable (Offline)")
    print("=" * 55)

    # --- 1. Verificar Python ---
    _check_python_version()
    _log("Python {}.{}.{}".format(
        sys.version_info[0], sys.version_info[1], sys.version_info[2]))

    # --- 2. Entorno virtual ---
    if not _venv_exists():
        _create_venv()
        _install_dependencies()
    else:
        result = subprocess.run(
            [PYTHON, "-c", "import flask"],
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            _log("Dependencias no encontradas. Instalando...")
            _install_dependencies()

    # --- 3. Asegurar .env ---
    _ensure_env_file()

    # --- 4. Seed / Reset ---
    if args.reset:
        _reset_db()
    elif args.seed:
        _seed_data()

    # --- 5. Determinar puerto ---
    port = args.port
    if port == 0:
        port = _find_free_port(5000)

    url = "http://{}:{}".format(args.host, port)

    # --- 6. Variables de entorno ---
    env = os.environ.copy()
    env["FLASK_DEBUG"] = "0"
    env["SECRET_KEY"] = env.get("SECRET_KEY", "")
    env.pop("DATABASE_URL", None)

    # --- 7. Iniciar servidor ---
    server_cmd = [
        PYTHON, "-m", "flask", "run",
        "--host", args.host,
        "--port", str(port),
        "--no-reload",
    ]

    _log("Iniciando servidor en " + url)
    print("-" * 55)
    print("  Abre tu navegador en: " + url)
    print("  Usuario admin: cponce123.com@gmail.com")
    print("  Contrasena: Hadrones456%")
    print("  Presiona Ctrl+C para detener el servidor")
    print("-" * 55)

    # --- 8. Iniciar y abrir navegador ---
    process = subprocess.Popen(server_cmd, cwd=PROJECT_DIR, env=env)
    if not args.no_browser:
        _open_browser(url)

    # --- 9. Esperar senal de interrupcion ---
    try:
        process.wait()
    except KeyboardInterrupt:
        _log("Deteniendo servidor...")
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
        _log("Servidor detenido.")


if __name__ == "__main__":
    main()
