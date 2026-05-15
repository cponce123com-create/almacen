@echo off
title ALMACENERO - Control de Inventarios
chcp 65001 >nul

echo =======================================================
echo   ALMACENERO - Control de Inventarios
echo   Modo Portable (Windows)
echo =======================================================
echo.

REM Verificar si Python esta instalado
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python no esta instalado o no esta en el PATH.
    echo.
    echo Para usar esta version necesitas:
    echo   Opcion A) Instalar Python desde: https://www.python.org/downloads/
    echo   Opcion B) Usar la version compilada (.exe) - ejecuta build_exe.py
    echo.
    echo Presiona cualquier tecla para salir...
    pause >nul
    exit /b 1
)

REM Verificar version de Python
python -c "import sys; sys.exit(0 if sys.version_info >= (3,9) else 1)" >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Se requiere Python 3.9 o superior.
    echo.
    python --version
    echo.
    pause
    exit /b 1
)

echo  Python detectado correctamente.
echo.

REM Verificar si existe el entorno virtual
if not exist ".venv\Scripts\python.exe" (
    echo [1/3] Creando entorno virtual...
    python -m venv .venv
    if %errorlevel% neq 0 (
        echo [ERROR] No se pudo crear el entorno virtual.
        pause
        exit /b 1
    )
    echo  Entorno virtual creado.
    
    echo [2/3] Instalando dependencias...
    .venv\Scripts\pip.exe install --quiet -r requirements-lite.txt
    if %errorlevel% neq 0 (
        echo [ERROR] No se pudieron instalar las dependencias.
        echo Asegurate de tener conexion a internet la primera vez.
        pause
        exit /b 1
    )
    echo  Dependencias instaladas.
) else (
    REM Verificar que flask este instalado
    .venv\Scripts\python.exe -c "import flask" >nul 2>&1
    if %errorlevel% neq 0 (
        echo [*] Instalando dependencias faltantes...
        .venv\Scripts\pip.exe install --quiet -r requirements-lite.txt
    )
)

echo [3/3] Iniciando servidor...
echo.

REM Configurar variables de entorno
set FLASK_DEBUG=0
set FLASK_PORT=5000

REM Iniciar la aplicacion
.venv\Scripts\python.exe app\app.py

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] La aplicacion se cerro inesperadamente.
    pause
)
