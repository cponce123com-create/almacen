"""
ALMACENERO - Build para Windows Portable (.exe)
=================================================
Empaqueta la aplicacion Flask + Python + dependencias en un
ejecutable portatil para Windows usando PyInstaller.

REQUISITOS:
    pip install pyinstaller

USO (en Windows):
    python build_exe.py              # Build normal (con consola)
    python build_exe.py --no-console # Build sin consola (ventana oculta)
    python build_exe.py --clean      # Limpiar builds anteriores

El ejecutable se genera en:  dist/ALMACENERO/ALMACENERO.exe
Puedes copiar toda la carpeta dist/ALMACENERO/ a cualquier PC sin Python.
"""

import os
import sys
import shutil
import subprocess
import argparse

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
APP_DIR = os.path.join(PROJECT_DIR, "app")
DIST_DIR = os.path.join(PROJECT_DIR, "dist", "ALMACENERO")


def _check_pyinstaller():
    try:
        import PyInstaller
        return True
    except ImportError:
        return False


def _install_pyinstaller():
    print("Instalando PyInstaller...")
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "pyinstaller", "--quiet"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        print("ERROR: No se pudo instalar PyInstaller: " + result.stderr)
        print("Instalalo manualmente: pip install pyinstaller")
        sys.exit(1)
    print("PyInstaller instalado.")


def _clean_builds():
    """Limpia carpetas de builds anteriores."""
    for folder in ["build", "dist", "__pycache__"]:
        path = os.path.join(PROJECT_DIR, folder)
        if os.path.exists(path):
            print("Limpiando: " + folder)
            shutil.rmtree(path, ignore_errors=True)
    # Tambien limpiar .spec
    for f in os.listdir(PROJECT_DIR):
        if f.endswith(".spec"):
            os.remove(os.path.join(PROJECT_DIR, f))
    print("Builds anteriores eliminados.")


def _build_exe(console=True):
    """Ejecuta PyInstaller para compilar el .exe."""
    print("=" * 55)
    print("  Compilando ALMACENERO para Windows Portable...")
    print("=" * 55)

    # Colectar archivos estaticos y templates como datos
    # Paths: origen -> destino dentro del .exe
    data_files = []

    # Templates
    templates_dir = os.path.join(APP_DIR, "templates")
    for root, dirs, files in os.walk(templates_dir):
        for f in files:
            rel_path = os.path.relpath(os.path.join(root, f), APP_DIR)
            data_files.append((os.path.join(root, f), os.path.join("app", os.path.dirname(rel_path))))

    # Static (CSS, JS, vendor, favicon)
    static_dir = os.path.join(APP_DIR, "static")
    for root, dirs, files in os.walk(static_dir):
        for f in files:
            rel_path = os.path.relpath(os.path.join(root, f), APP_DIR)
            data_files.append((os.path.join(root, f), os.path.join("app", os.path.dirname(rel_path))))

    # Archivo requirements-lite.txt (para referencia)
    data_files.append((os.path.join(PROJECT_DIR, "requirements-lite.txt"), "."))

    # Construir argumento --add-data
    add_data_args = []
    for src, dst in data_files:
        add_data_args.append("--add-data")
        add_data_args.append("{}:{}".format(src, dst))

    # Configuracion de PyInstaller
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name", "ALMACENERO",
        "--icon", os.path.join(APP_DIR, "static", "favicon.svg") if os.path.exists(os.path.join(APP_DIR, "static", "favicon.svg")) else "NONE",
        "--distpath", os.path.join(PROJECT_DIR, "dist"),
        "--workpath", os.path.join(PROJECT_DIR, "build"),
        "--specpath", PROJECT_DIR,
    ]

    # Modo sin consola (para usuarios finales)
    if not console:
        cmd.append("--noconsole")
        cmd.append("--uac-admin")  # No necesita admin realmente, pero evita warnings

    # Agregar hidden imports necesarios para Flask
    hidden_imports = [
        "--hidden-import", "flask",
        "--hidden-import", "flask_sqlalchemy",
        "--hidden-import", "flask_login",
        "--hidden-import", "flask_migrate",
        "--hidden-import", "flask_wtf",
        "--hidden-import", "flask_wtf.csrf",
        "--hidden-import", "werkzeug",
        "--hidden-import", "jinja2",
        "--hidden-import", "markupsafe",
        "--hidden-import", "itsdangerous",
        "--hidden-import", "click",
        "--hidden-import", "openpyxl",
        "--hidden-import", "sqlalchemy",
        "--hidden-import", "alembic",
        "--hidden-import", "email_validator",
        "--hidden-import", "python_magic",
    ]
    cmd.extend(hidden_imports)

    # Excluir modulos innecesarios para reducir tamano
    excludes = [
        "--exclude-module", "tkinter",
        "--exclude-module", "matplotlib",
        "--exclude-module", "numpy",
        "--exclude-module", "pandas",
        "--exclude-module", "scipy",
        "--exclude-module", "PIL",
        "--exclude-module", "curses",
        "--exclude-module", "test",
        "--exclude-module", "unittest",
        "--exclude-module", "distutils",
        "--exclude-module", "setuptools",
        "--exclude-module", "pip",
        "--exclude-module", "psycopg2",
        "--exclude-module", "psycopg2_binary",
        "--exclude-module", "gunicorn",
    ]
    cmd.extend(excludes)

    # Agregar data files
    cmd.extend(add_data_args)

    # Archivo principal
    cmd.append(os.path.join(APP_DIR, "app.py"))

    print("Ejecutando PyInstaller...")
    print("  (Esto puede tomar varios minutos)")
    print("")

    result = subprocess.run(cmd)
    if result.returncode != 0:
        print("ERROR: PyInstaller fallo con codigo " + str(result.returncode))
        sys.exit(1)

    # Copiar archivos adicionales utiles al directorio de salida
    _copy_extra_files()

    print("")
    print("=" * 55)
    print("  BUILD COMPLETADO!")
    print("=" * 55)
    print("  El ejecutable esta en:")
    print("    " + os.path.join(DIST_DIR, "ALMACENERO.exe"))
    print("")
    print("  Para usarlo:")
    print("    1. Copia toda la carpeta 'dist/ALMACENERO/' a tu USB")
    print("    2. Ejecuta ALMACENERO.exe")
    print("    3. Se abrira el navegador en http://127.0.0.1:5000")
    print("")
    print("  TAMANO DEL PAQUETE: " + _get_folder_size(DIST_DIR))
    print("=" * 55)


def _copy_extra_files():
    """Copia archivos utiles al directorio de salida."""
    os.makedirs(DIST_DIR, exist_ok=True)

    # Copiar README
    readme_src = os.path.join(PROJECT_DIR, "README.md")
    if os.path.exists(readme_src):
        shutil.copy2(readme_src, os.path.join(DIST_DIR, "README.md"))

    # Copiar datos_iniciales.xlsx (para seed)
    excel_src = os.path.join(PROJECT_DIR, "datos_iniciales.xlsx")
    if os.path.exists(excel_src):
        shutil.copy2(excel_src, os.path.join(DIST_DIR, "datos_iniciales.xlsx"))

    print("Archivos adicionales copiados.")


def _get_folder_size(folder_path):
    """Calcula el tamano de una carpeta en formato legible."""
    total = 0
    for dirpath, dirnames, filenames in os.walk(folder_path):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            try:
                total += os.path.getsize(fp)
            except OSError:
                pass
    for unit in ["B", "KB", "MB", "GB"]:
        if total < 1024:
            return "{:.1f} {}".format(total, unit)
        total /= 1024
    return "{:.1f} GB".format(total)


def main():
    parser = argparse.ArgumentParser(
        description="ALMACENERO - Build para Windows Portable (.exe)"
    )
    parser.add_argument("--no-console", action="store_true",
                        help="Build sin consola (ventana oculta)")
    parser.add_argument("--clean", action="store_true",
                        help="Limpiar builds anteriores")
    args = parser.parse_args()

    # Verificar/instalar PyInstaller
    if not _check_pyinstaller():
        _install_pyinstaller()

    # Clean si se solicita
    if args.clean:
        _clean_builds()

    # Ejecutar build
    _build_exe(console=not args.no_console)


if __name__ == "__main__":
    main()
