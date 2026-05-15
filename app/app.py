import os
import sys
import webbrowser
from app import create_app

app = create_app()

if __name__ == "__main__":
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    port = int(os.environ.get("FLASK_PORT", "5000"))

    # En modo PyInstaller (frozen), abrir navegador automaticamente
    if getattr(sys, "frozen", False):
        url = "http://127.0.0.1:{}".format(port)
        print("=" * 50)
        print("  ALMACENERO - Control de Inventarios")
        print("  Modo Portable (Windows)")
        print("=" * 50)
        print("  Abriendo navegador en: " + url)
        print("  Usuario admin: cponce123.com@gmail.com")
        print("  Contrasena: Hadrones456%")
        print("  Presiona Ctrl+C para cerrar")
        print("=" * 50)
        # Abrir navegador despues de un breve retardo
        import threading
        def _open():
            import time
            time.sleep(1.5)
            try:
                webbrowser.open(url)
            except Exception:
                pass
        threading.Thread(target=_open, daemon=True).start()

    app.run(debug=debug, host="127.0.0.1", port=port)
