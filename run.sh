#!/usr/bin/env bash
#
# ALMACENERO — Lanzador Portable (Shell Wrapper)
# ================================================
# Uso:  ./run.sh              # Iniciar
#       ./run.sh --seed       # Recargar datos demo
#       ./run.sh --reset      # Resetear BD
#       ./run.sh --port 8080  # Puerto personalizado
#
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo ""
echo "======================================================="
echo "  ALMACENERO — Control de Inventarios"
echo "  Modo Portable (Offline)"
echo "======================================================="

# Verificar que Python esté instalado
if ! command -v python3 &> /dev/null; then
    echo "  ERROR: python3 no está instalado."
    echo "  Instálalo desde: https://www.python.org/downloads/"
    exit 1
fi

# Verificar versión de Python
PY_MAJOR=$(python3 -c "import sys; print(sys.version_info[0])")
PY_MINOR=$(python3 -c "import sys; print(sys.version_info[1])")
if [ "$PY_MAJOR" -lt 3 ] || { [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 9 ]; }; then
    echo "  ERROR: Se requiere Python >= 3.9 (tienes $PY_MAJOR.$PY_MINOR)"
    exit 1
fi

echo "  Python $PY_MAJOR.$PY_MINOR encontrado."

# Ejecutar el lanzador portable
exec python3 run.py "$@"
