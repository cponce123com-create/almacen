import io
import os
import re
from datetime import datetime, timezone
from flask import Blueprint, render_template, request, redirect, url_for, flash, send_file
from flask_login import login_user, logout_user, login_required, current_user
from app import db
from app.models import User, Producto, Entrada, Salida

routes_bp = Blueprint("routes", __name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _init_admin_user():
    """Crea el usuario admin por defecto si no existe."""
    if not User.query.filter_by(username="admin").first():
        admin = User(username="admin")
        admin.set_password("admin")
        db.session.add(admin)
        db.session.commit()


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

@routes_bp.route("/login", methods=["GET", "POST"])
def login():
    _init_admin_user()
    if current_user.is_authenticated:
        return redirect(url_for("routes.dashboard"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user)
            next_page = request.args.get("next")
            flash("Inicio de sesión exitoso.", "success")
            return redirect(next_page or url_for("routes.dashboard"))
        flash("Usuario o contraseña incorrectos.", "danger")
    return render_template("login.html")


@routes_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Sesión cerrada correctamente.", "info")
    return redirect(url_for("routes.login"))


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

@routes_bp.route("/")
@login_required
def dashboard():
    total_productos = Producto.query.count()
    total_entradas = Entrada.query.count()
    total_salidas = Salida.query.count()
    stock_bajo = Producto.query.filter(
        Producto.stock_minimo > 0,
        Producto.stock_actual <= Producto.stock_minimo
    ).all()

    # Últimos 10 movimientos combinados
    entradas_recientes = Entrada.query.order_by(Entrada.fecha_ingreso.desc()).limit(10).all()
    salidas_recientes = Salida.query.order_by(Salida.fecha_salida.desc()).limit(10).all()

    movimientos = []
    for e in entradas_recientes:
        movimientos.append({
            "tipo": "ENTRADA",
            "fecha": e.fecha_ingreso,
            "producto": e.producto.descripcion if e.producto else "—",
            "cantidad": e.cantidad,
            "referencia": e.oc or e.guia_remision or "—",
        })
    for s in salidas_recientes:
        movimientos.append({
            "tipo": "SALIDA",
            "fecha": s.fecha_salida,
            "producto": s.producto.descripcion if s.producto else "—",
            "cantidad": s.cantidad,
            "referencia": s.nro_vale or s.oi or "—",
        })
    movimientos.sort(key=lambda m: m["fecha"], reverse=True)
    movimientos = movimientos[:10]

    return render_template(
        "index.html",
        total_productos=total_productos,
        total_entradas=total_entradas,
        total_salidas=total_salidas,
        stock_bajo=stock_bajo,
        movimientos=movimientos,
    )


# ---------------------------------------------------------------------------
# Productos CRUD
# ---------------------------------------------------------------------------

@routes_bp.route("/productos")
@login_required
def productos():
    search = request.args.get("search", "").strip()
    page = request.args.get("page", 1, type=int)
    per_page = 15

    query = Producto.query
    if search:
        query = query.filter(
            Producto.descripcion.ilike(f"%{search}%")
            | Producto.codigo.ilike(f"%{search}%")
            | Producto.familia.ilike(f"%{search}%")
        )
    query = query.order_by(Producto.codigo.asc())
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    return render_template("productos.html", pagination=pagination, search=search)


@routes_bp.route("/productos/nuevo", methods=["GET", "POST"])
@login_required
def producto_nuevo():
    return _producto_form()


@routes_bp.route("/productos/editar/<int:producto_id>", methods=["GET", "POST"])
@login_required
def producto_editar(producto_id):
    producto = db.session.get(Producto, producto_id)
    if not producto:
        flash("Producto no encontrado.", "danger")
        return redirect(url_for("routes.productos"))
    return _producto_form(producto)


@routes_bp.route("/productos/eliminar/<int:producto_id>", methods=["POST"])
@login_required
def producto_eliminar(producto_id):
    producto = db.session.get(Producto, producto_id)
    if not producto:
        flash("Producto no encontrado.", "danger")
        return redirect(url_for("routes.productos"))
    if producto.entradas.count() > 0 or producto.salidas.count() > 0:
        flash("No se puede eliminar: el producto tiene movimientos asociados.", "danger")
        return redirect(url_for("routes.productos"))
    db.session.delete(producto)
    db.session.commit()
    flash("Producto eliminado correctamente.", "success")
    return redirect(url_for("routes.productos"))


# ---------------------------------------------------------------------------
# Importar / Exportar productos en Excel
# ---------------------------------------------------------------------------

HEADERS_MAESTRA = [
    "CODIGO", "COD. CATALOGO", "DESCRIPCION DEL PRODUCTO", "U.M", "FAMILIA",
    "STOCK MINIMO",
]

COL_MAP = {
    "CODIGO": "codigo",
    "COD. CATALOGO": "cod_catalogo",
    "CATALOGO": "cod_catalogo",
    "DESCRIPCION DEL PRODUCTO": "descripcion",
    "DESCRIPCION": "descripcion",
    "DESCRIPCIÓN": "descripcion",
    "PRODUCTO": "descripcion",
    "U.M": "um",
    "UM": "um",
    "U.M.": "um",
    "FAMILIA": "familia",
    "STOCK MINIMO": "stock_minimo",
    "STOCK MÍNIMO": "stock_minimo",
    "STOCK_MINIMO": "stock_minimo",
}

COL_MAP_ENTRADA = {
    "CODIGO": "codigo",
    "COD. CATALOGO": "cod_catalogo",
    "CATALOGO": "cod_catalogo",
    "DESCRIPCION DEL PRODUCTO": "descripcion",
    "DESCRIPCION": "descripcion",
    "DESCRIPCIÓN": "descripcion",
    "CANTIDAD": "cantidad",
    "CANTIDA": "cantidad",
    "U.M2": "um",
    "U.M": "um",
    "UM": "um",
    "ZONA": "zona",
    "UBICACIÓN": "ubicacion",
    "UBICACION": "ubicacion",
    "ALM": "alm",
    "F.INGRESO": "fecha",
    "FECHA": "fecha",
    "FECHA INGRESO": "fecha",
    "OC": "oc",
    "G.REMISION": "guia",
    "GUIA": "guia",
    "GUIA REMISION": "guia",
    "FAMILIA": "familia",
}

COL_MAP_SALIDA = {
    "CODIGO": "codigo",
    "COD. CATALOGO": "cod_catalogo",
    "CATALOGO": "cod_catalogo",
    "DESCRIPCION DEL PRODUCTO": "descripcion",
    "DESCRIPCION": "descripcion",
    "DESCRIPCIÓN": "descripcion",
    "CANTIDAD": "cantidad",
    "U.M2": "um",
    "U.M": "um",
    "UM": "um",
    "F. SALIDA": "fecha",
    "FECHA": "fecha",
    "FECHA SALIDA": "fecha",
    "N° VALE": "nro_vale",
    "NRO VALE": "nro_vale",
    "VALE": "nro_vale",
    "OI": "oi",
    "C.COSTO": "c_costo",
    "C COSTO": "c_costo",
    "COSTO": "c_costo",
    "MAQUINA": "maquina",
    "CATEGORIA": "categoria",
    "CATEGPRIA": "categoria",
}

# Límites máximos según modelos.py
FIELD_MAXLEN = {
    "codigo": 50,
    "cod_catalogo": 50,
    "descripcion": 300,
    "um": 20,
    "familia": 100,
    "zona": 50,
    "ubicacion": 100,
    "alm": 50,
    "oc": 50,
    "guia_remision": 50,
    "nro_vale": 50,
    "oi": 50,
    "c_costo": 100,
    "maquina": 100,
    "categoria": 100,
}

# ---------------------------------------------------------------------------
# Helpers para Excel
# ---------------------------------------------------------------------------


def _excel_val(row, col_indices, col_name):
    """Extraer valor de una celda Excel, normalizado a string."""
    idx = col_indices.get(col_name)
    if idx is None or idx >= len(row):
        return ""
    v = row[idx]
    if v is None:
        return ""
    # Si es datetime, formatear como fecha
    if isinstance(v, (datetime,)):
        return v.strftime("%Y-%m-%d")
    if isinstance(v, (int, float)):
        # Convertir número a string sin decimales si es entero
        if v == int(v):
            return str(int(v))
        return str(v).replace(",", ".")
    return str(v).strip()


def _sanitize_field(valor, field_name):
    """Truncar un campo a su longitud máxima definida."""
    maxlen = FIELD_MAXLEN.get(field_name, 300)
    return str(valor).strip()[:maxlen] if valor else ""


def _make_excel_workbook():
    """Crear workbook con openpyxl y devolver hoja activa."""
    import openpyxl
    return openpyxl.Workbook()


# ---------------------------------------------------------------------------
# Ruta: Descargar plantilla
# ---------------------------------------------------------------------------

@routes_bp.route("/productos/plantilla")
@login_required
def producto_plantilla():
    """Descargar plantilla Excel vacía con estructura MAESTRA."""
    try:
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment
        from openpyxl.utils import get_column_letter
    except ImportError:
        flash("openpyxl no está instalado.", "danger")
        return redirect(url_for("routes.productos"))

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "MAESTRA"

    header_font = Font(bold=True, color="FFFFFF", size=11)
    header_fill = PatternFill(start_color="0D6EFD", end_color="0D6EFD", fill_type="solid")
    header_align = Alignment(horizontal="center", vertical="center")

    for col_idx, header in enumerate(HEADERS_MAESTRA, 1):
        cell = ws.cell(row=1, column=col_idx, value=header)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = header_align

    widths = [12, 14, 50, 10, 20, 14]
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w

    # Fila de ejemplo
    ejemplo = ["(Ej: P001)", "(Ej: CAT-001)", "(Ej: Tornillo M8x30)",
               "(Ej: UND)", "(Ej: FERRETERIA)", "(Ej: 10)"]
    for col_idx, val in enumerate(ejemplo, 1):
        cell = ws.cell(row=2, column=col_idx, value=val)
        cell.font = Font(italic=True, color="888888")

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)

    return send_file(
        output,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name="plantilla_maestra.xlsx",
    )


# ---------------------------------------------------------------------------
# API: Búsqueda en vivo de productos (JSON)
# ---------------------------------------------------------------------------

@routes_bp.route("/api/productos")
@login_required
def api_productos():
    """Retorna JSON con productos que coinciden con la búsqueda."""
    q = request.args.get("q", "").strip()
    limit = request.args.get("limit", 20, type=int)

    query = Producto.query
    if q:
        like = f"%{q}%"
        query = query.filter(
            Producto.codigo.ilike(like)
            | Producto.descripcion.ilike(like)
            | Producto.cod_catalogo.ilike(like)
            | Producto.familia.ilike(like)
        )
    productos = query.order_by(Producto.descripcion.asc()).limit(limit).all()

    return {
        "results": [
            {
                "id": p.id,
                "codigo": p.codigo,
                "cod_catalogo": p.cod_catalogo or "",
                "descripcion": p.descripcion,
                "um": p.um,
                "familia": p.familia or "",
                "stock_actual": p.stock_actual,
                "stock_minimo": p.stock_minimo,
            }
            for p in productos
        ],
        "total": len(productos),
    }


HEADERS_PLANTILLA_ENTRADA = [
    "CODIGO", "COD. CATALOGO", "DESCRIPCION DEL PRODUCTO", "CANTIDA",
    "U.M2", "ZONA", "UBICACIÓN", "ALM", "F.INGRESO", "OC", "G.REMISION", "FAMILIA",
]

HEADERS_PLANTILLA_SALIDA = [
    "CODIGO", "COD. CATALOGO", "DESCRIPCION DEL PRODUCTO", "CANTIDAD",
    "U.M2", "F. SALIDA", "N° VALE", "OI", "C.COSTO", "MAQUINA", "CATEGORIA",
]


def _generar_plantilla(headers, titulo, nombre_archivo, ejemplos):
    """Helper para generar una plantilla Excel descargable."""
    try:
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment
        from openpyxl.utils import get_column_letter
    except ImportError:
        return None, "openpyxl no está instalado."

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = titulo

    hf = Font(bold=True, color="FFFFFF", size=11)
    hfill = PatternFill(start_color="0D6EFD", end_color="0D6EFD", fill_type="solid")
    ha = Alignment(horizontal="center", vertical="center")

    for ci, h in enumerate(headers, 1):
        c = ws.cell(row=1, column=ci, value=h)
        c.font = hf; c.fill = hfill; c.alignment = ha

    widths = [max(12, len(h) + 2) for h in headers]
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = min(w, 40)

    if ejemplos:
        for ci, val in enumerate(ejemplos, 1):
            c = ws.cell(row=2, column=ci, value=val)
            c.font = Font(italic=True, color="888888")

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return output, None


@routes_bp.route("/entradas/plantilla")
@login_required
def entradas_plantilla():
    """Descargar plantilla Excel para importar entradas."""
    ejemplos = ["(Ej: P001)", "(Ej: CAT-001)", "(Ej: Tornillo M8x30)", "(Ej: 10)",
                "(Ej: UND)", "(Ej: ZONA-A)", "(Ej: EST-01)", "(Ej: ALM-01)",
                "(Ej: 01/01/2025)", "(Ej: OC-001)", "(Ej: GR-001)", "(Ej: FERRETERIA)"]
    output, error = _generar_plantilla(
        HEADERS_PLANTILLA_ENTRADA, "ENTRADA", "plantilla_entrada.xlsx", ejemplos
    )
    if error:
        flash(error, "danger")
        return redirect(url_for("routes.entradas_importar"))
    return send_file(output,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True, download_name="plantilla_entrada.xlsx")


@routes_bp.route("/salidas/plantilla")
@login_required
def salidas_plantilla():
    """Descargar plantilla Excel para importar salidas."""
    ejemplos = ["(Ej: P001)", "(Ej: CAT-001)", "(Ej: Tuerca M8)", "(Ej: 5)",
                "(Ej: UND)", "(Ej: 15/01/2025)", "(Ej: V-001)", "(Ej: OI-001)",
                "(Ej: CC-100)", "(Ej: MAQ-01)", "(Ej: GENERAL)"]
    output, error = _generar_plantilla(
        HEADERS_PLANTILLA_SALIDA, "SALIDA", "plantilla_salida.xlsx", ejemplos
    )
    if error:
        flash(error, "danger")
        return redirect(url_for("routes.salidas_importar"))
    return send_file(output,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True, download_name="plantilla_salida.xlsx")


# ---------------------------------------------------------------------------
# Ruta: Importar productos desde Excel (con previsualización)
# ---------------------------------------------------------------------------

MAX_IMPORT_ROWS = 5000
"""Número máximo de filas permitidas en una importación."""


def _parse_excel(file):
    """Parsea un archivo Excel y devuelve (headers, col_indices, filas, errores).

    ``file`` puede ser una ruta (str) o un objeto file-like.
    """
    errores_prev = []

    try:
        import openpyxl
    except ImportError:
        errores_prev.append("openpyxl no está instalado en el servidor.")
        return None, None, None, errores_prev

    try:
        wb = openpyxl.load_workbook(file, data_only=True)
        ws = wb.active
    except Exception:
        errores_prev.append("El archivo no es un Excel válido o está corrupto.")
        return None, None, None, errores_prev

    # Leer encabezados
    first_row = list(ws.iter_rows(min_row=1, max_row=1, values_only=True))
    if not first_row or not any(c is not None for c in first_row[0]):
        errores_prev.append("El archivo Excel está vacío.")
        return None, None, None, errores_prev

    headers_raw = []
    for cell_val in first_row[0]:
        s = str(cell_val).strip().upper() if cell_val is not None else ""
        headers_raw.append(s)

    col_indices = {}
    for i, h in enumerate(headers_raw):
        for key, mapped in COL_MAP.items():
            if key.upper() == h:
                col_indices[mapped] = i
                break

    if "codigo" not in col_indices:
        cols = ", ".join(h for h in headers_raw if h)
        errores_prev.append(
            f"No se encontró columna 'CODIGO'. Columnas del archivo: {cols}" if cols
            else "No se encontró la columna 'CODIGO'."
        )
        return headers_raw, None, None, errores_prev

    # Contar filas totales ANTES de procesar
    total_rows = sum(1 for _ in ws.iter_rows(min_row=2, values_only=True)
                     if any(c is not None for c in _))
    if total_rows > MAX_IMPORT_ROWS:
        errores_prev.append(
            f"El archivo tiene {total_rows} filas con datos. "
            f"Máximo permitido: {MAX_IMPORT_ROWS}."
        )
        return headers_raw, col_indices, None, errores_prev

    # Leer filas
    filas = []
    codigos_vistos = set()
    # Obtener todos los códigos existentes de una sola vez (rendimiento)
    codigos_existentes = {r[0] for r in db.session.query(Producto.codigo).all()}

    for excel_row in ws.iter_rows(min_row=2, values_only=True):
        if not any(cell is not None for cell in excel_row):
            continue

        codigo = _excel_val(excel_row, col_indices, "codigo").upper()
        if not codigo:
            continue

        descripcion = _excel_val(excel_row, col_indices, "descripcion")


        # Detectar duplicados internos
        if codigo in codigos_vistos:
            continue
        codigos_vistos.add(codigo)

        cod_catalogo = _excel_val(excel_row, col_indices, "cod_catalogo")
        um = _excel_val(excel_row, col_indices, "um").upper() or "UND"
        familia = _excel_val(excel_row, col_indices, "familia")

        stock_minimo = 0.0
        if "stock_minimo" in col_indices:
            raw = _excel_val(excel_row, col_indices, "stock_minimo")
            try:
                stock_minimo = max(0.0, float(raw.replace(",", ".")))
            except (ValueError, AttributeError):
                stock_minimo = 0.0

        filas.append({
            "codigo": codigo,
            "cod_catalogo": cod_catalogo,
            "descripcion": descripcion,
            "um": um,
            "familia": familia,
            "stock_minimo": stock_minimo,
            "accion": "ACTUALIZAR" if codigo in codigos_existentes else "CREAR",
        })

    return headers_raw, col_indices, filas, errores_prev


@routes_bp.route("/productos/importar", methods=["GET", "POST"])
@login_required
def producto_importar():
    """Importar productos desde archivo Excel.

    Flujo de dos pasos:
      1. POST sin confirmar → parsea el archivo, muestra vista previa.
      2. POST con confirmar  → ejecuta la importación real.
    """
    # ---------------------------------------------------------------
        # ---------------------------------------------------------------
    # Manejo de peticiones
    # ---------------------------------------------------------------
    # ---------------------------------------------------------------
    # Manejo de peticiones
    # ---------------------------------------------------------------
    import uuid as _uuid
    import tempfile as _tempfile

    if request.method == "POST":
        # --- Validación del archivo ---
        if "archivo" not in request.files:
            flash("No se seleccionó ningún archivo.", "danger")
            return redirect(url_for("routes.producto_importar"))

        file = request.files["archivo"]
        if not file or file.filename == "":
            flash("No se seleccionó ningún archivo.", "danger")
            return redirect(url_for("routes.producto_importar"))

        # Solo aceptar .xlsx (openpyxl NO soporta .xls antiguo)
        if not file.filename.lower().endswith(".xlsx"):
            flash("Solo se aceptan archivos .xlsx (Excel moderno). "
                  "Si tu archivo es .xls, ábrelo en Excel y guárdalo como .xlsx.", "warning")
            return redirect(url_for("routes.producto_importar"))

        # Guardar el archivo en un temporal para poder releerlo en confirmación
        tmp_suffix = _uuid.uuid4().hex[:12]
        tmp_path = os.path.join(_tempfile.gettempdir(), f"almacen_import_{tmp_suffix}.xlsx")
        file.save(tmp_path)

        try:
            headers_raw, col_indices, filas, errores_prev = _parse_excel(tmp_path)
        except Exception:
            errores_prev = ["Error inesperado al leer el archivo."]
            headers_raw = None
            filas = None

        if errores_prev:
            # Limpiar temp
            try:
                os.remove(tmp_path)
            except OSError:
                pass
            for e in errores_prev:
                flash(e, "danger")
            return redirect(url_for("routes.producto_importar"))

        if not filas:
            try:
                os.remove(tmp_path)
            except OSError:
                pass
            flash("No se encontraron filas válidas para importar.", "warning")
            return redirect(url_for("routes.producto_importar"))

        # Mostrar vista previa
        headers_mostrar = [h for h in headers_raw if h]
        return render_template(
            "producto_importar.html",
            preview=True,
            tmp_path=tmp_path,
            headers=headers_mostrar,
            filas=filas[:20],  # mostrar primeras 20 filas
            total_filas=len(filas),
            nombre_archivo=file.filename,
        )

    # GET → formulario normal
    return render_template("producto_importar.html")


# ---------------------------------------------------------------------------
# Ruta: Confirmar importación (POST separado para claridad)
# ---------------------------------------------------------------------------

@routes_bp.route("/productos/importar/confirmar", methods=["POST"])
@login_required
def producto_importar_confirmar():
    """Ejecutar la importación después de la previsualización."""
    tmp_path = request.form.get("tmp_path", "").strip()

    if not tmp_path or not os.path.exists(tmp_path):
        flash("Archivo temporal no encontrado. Vuelve a seleccionar el archivo.", "danger")
        return redirect(url_for("routes.producto_importar"))

    try:
        headers_raw, col_indices, filas, errores_prev = _parse_excel(tmp_path)
    except Exception:
        errores_prev = ["Error inesperado al leer el archivo temporal."]
        filas = None

    if errores_prev:
        try:
            os.remove(tmp_path)
        except OSError:
            pass
        for e in errores_prev:
            flash(e, "danger")
        return redirect(url_for("routes.producto_importar"))

    if not filas:
        try:
            os.remove(tmp_path)
        except OSError:
            pass
        flash("No se encontraron filas válidas para importar.", "warning")
        return redirect(url_for("routes.producto_importar"))

    # --- Ejecutar importación en transacción atómica ---
    creados = []
    actualizados = []
    errores_db = []

    try:
        # Cargar productos existentes de una sola vez
        codigos_a_importar = [f["codigo"] for f in filas]
        existentes_map = {
            p.codigo: p
            for p in Producto.query.filter(Producto.codigo.in_(codigos_a_importar)).all()
        }

        for f in filas:
            codigo = _sanitize_field(f["codigo"], "codigo")
            descripcion = _sanitize_field(f["descripcion"], "descripcion")
            cod_catalogo = _sanitize_field(f["cod_catalogo"], "cod_catalogo")
            um = _sanitize_field(f["um"], "um") or "UND"
            familia = _sanitize_field(f["familia"], "familia")

            producto = existentes_map.get(codigo)
            if producto:
                producto.cod_catalogo = cod_catalogo or producto.cod_catalogo
                producto.descripcion = descripcion or producto.descripcion
                producto.um = um or producto.um
                producto.familia = familia or producto.familia
                producto.stock_minimo = f["stock_minimo"]
                actualizados.append(codigo)
            else:
                producto = Producto(
                    codigo=codigo, cod_catalogo=cod_catalogo,
                    descripcion=descripcion or "", um=um, familia=familia,
                    stock_minimo=f["stock_minimo"],
                )
                db.session.add(producto)
                creados.append(codigo)

        db.session.commit()

        # Limpiar temp
        try:
            os.remove(tmp_path)
        except OSError:
            pass

        # Reporte detallado
        partes = []
        if creados:
            partes.append(f"✅ {len(creados)} creados")
        if actualizados:
            partes.append(f"📝 {len(actualizados)} actualizados")
        if errores_db:
            partes.append(f"⚠️ {len(errores_db)} errores")

        msg = "Importación completada: " + ", ".join(partes)

        if errores_db:
            msg += ". Detalles: " + "; ".join(errores_db[:5])
            if len(errores_db) > 5:
                msg += f" y {len(errores_db) - 5} más."
            flash(msg, "warning")
        else:
            flash(msg, "success")

        return redirect(url_for("routes.productos"))

    except Exception as exc:
        db.session.rollback()
        try:
            os.remove(tmp_path)
        except OSError:
            pass
        flash(
            f"Error de base de datos durante la importación: {exc}. "
            "No se guardaron cambios. Verifica que los datos sean válidos.",
            "danger",
        )
        return redirect(url_for("routes.producto_importar"))


# ---------------------------------------------------------------------------
# Helper: Parsear Excel de movimientos (entradas / salidas)
# ---------------------------------------------------------------------------


def _parse_excel_movimiento(tipo, file):
    """Parsea un archivo Excel de movimientos.

    ``tipo`` es 'entrada' o 'salida'.
    ``file`` puede ser ruta (str) o file-like.
    Retorna (headers_raw, col_indices, filas, errores).
    """
    errores = []
    col_map = COL_MAP_ENTRADA if tipo == "entrada" else COL_MAP_SALIDA

    try:
        import openpyxl
    except ImportError:
        errores.append("openpyxl no está instalado en el servidor.")
        return None, None, None, errores

    try:
        wb = openpyxl.load_workbook(file, data_only=True)
        ws = wb.active
    except Exception:
        errores.append("El archivo no es un Excel válido o está corrupto.")
        return None, None, None, errores

    first_row = list(ws.iter_rows(min_row=1, max_row=1, values_only=True))
    if not first_row or not any(c is not None for c in first_row[0]):
        errores.append("El archivo Excel está vacío.")
        return None, None, None, errores

    headers_raw = []
    for cell_val in first_row[0]:
        s = str(cell_val).strip().upper() if cell_val is not None else ""
        headers_raw.append(s)

    col_indices = {}
    for i, h in enumerate(headers_raw):
        for key, mapped in col_map.items():
            if key.upper() == h:
                col_indices[mapped] = i
                break

    if "codigo" not in col_indices:
        cols = ", ".join(h for h in headers_raw if h)
        errores.append(
            f"No se encontró columna 'CODIGO'. Columnas del archivo: {cols}" if cols
            else "No se encontró la columna 'CODIGO'."
        )
        return headers_raw, None, None, errores

    total_rows = sum(
        1 for _ in ws.iter_rows(min_row=2, values_only=True)
        if any(c is not None for c in _)
    )
    if total_rows > MAX_IMPORT_ROWS:
        errores.append(
            f"El archivo tiene {total_rows} filas con datos. "
            f"Máximo permitido: {MAX_IMPORT_ROWS}."
        )
        return headers_raw, col_indices, None, errores

    # Parsear fechas con varios formatos
    def _parse_fecha(val):
        if isinstance(val, datetime):
            return val
        if not val:
            return None
        s = str(val).strip()
        for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%d/%m/%y"):
            try:
                return datetime.strptime(s, fmt)
            except ValueError:
                continue
        return None

    filas = []
    for excel_row in ws.iter_rows(min_row=2, values_only=True):
        if not any(cell is not None for cell in excel_row):
            continue

        codigo = _excel_val(excel_row, col_indices, "codigo").upper()
        if not codigo:
            continue

        cantidad = 0.0
        if "cantidad" in col_indices:
            raw = _excel_val(excel_row, col_indices, "cantidad")
            try:
                cantidad = max(0.0, float(raw.replace(",", ".")))
            except (ValueError, AttributeError):
                cantidad = 0.0

        if cantidad <= 0:
            continue

        um = _excel_val(excel_row, col_indices, "um").upper() if "um" in col_indices else ""
        fecha = _parse_fecha(
            _excel_val(excel_row, col_indices, "fecha") if "fecha" in col_indices else ""
        )

        fila = {
            "codigo": codigo,
            "cantidad": cantidad,
            "um": um,
            "fecha": fecha,
        }

        # Campos comunes: catálogo y descripción (opcionales)
        fila["cod_catalogo"] = _sanitize_field(
            _excel_val(excel_row, col_indices, "cod_catalogo") if "cod_catalogo" in col_indices else "", "cod_catalogo"
        )
        fila["descripcion"] = _sanitize_field(
            _excel_val(excel_row, col_indices, "descripcion") if "descripcion" in col_indices else "", "descripcion"
        )

        if tipo == "entrada":
            fila["zona"] = _sanitize_field(
                _excel_val(excel_row, col_indices, "zona") if "zona" in col_indices else "", "zona"
            )
            fila["ubicacion"] = _sanitize_field(
                _excel_val(excel_row, col_indices, "ubicacion") if "ubicacion" in col_indices else "", "ubicacion"
            )
            fila["alm"] = _sanitize_field(
                _excel_val(excel_row, col_indices, "alm") if "alm" in col_indices else "", "alm"
            ) or "ALM-01"
            fila["oc"] = _sanitize_field(
                _excel_val(excel_row, col_indices, "oc") if "oc" in col_indices else "", "oc"
            )
            fila["guia"] = _sanitize_field(
                _excel_val(excel_row, col_indices, "guia") if "guia" in col_indices else "", "guia_remision"
            )
            fila["familia"] = _sanitize_field(
                _excel_val(excel_row, col_indices, "familia") if "familia" in col_indices else "", "familia"
            )
        else:
            fila["nro_vale"] = _sanitize_field(
                _excel_val(excel_row, col_indices, "nro_vale") if "nro_vale" in col_indices else "", "nro_vale"
            )
            fila["oi"] = _sanitize_field(
                _excel_val(excel_row, col_indices, "oi") if "oi" in col_indices else "", "oi"
            )
            fila["c_costo"] = _sanitize_field(
                _excel_val(excel_row, col_indices, "c_costo") if "c_costo" in col_indices else "", "c_costo"
            )
            fila["maquina"] = _sanitize_field(
                _excel_val(excel_row, col_indices, "maquina") if "maquina" in col_indices else "", "maquina"
            )
            fila["categoria"] = _sanitize_field(
                _excel_val(excel_row, col_indices, "categoria") if "categoria" in col_indices else "", "categoria"
            )

        filas.append(fila)

    return headers_raw, col_indices, filas, errores


# ---------------------------------------------------------------------------
# Importar Entradas desde Excel
# ---------------------------------------------------------------------------

@routes_bp.route("/entradas/importar", methods=["GET", "POST"])
@login_required
def entradas_importar():
    import uuid as _uuid
    import tempfile as _tempfile

    if request.method == "POST":
        if "archivo" not in request.files:
            flash("No se seleccionó ningún archivo.", "danger")
            return redirect(url_for("routes.entradas_importar"))

        file = request.files["archivo"]
        if not file or file.filename == "":
            flash("No se seleccionó ningún archivo.", "danger")
            return redirect(url_for("routes.entradas_importar"))

        if not file.filename.lower().endswith(".xlsx"):
            flash("Solo se aceptan archivos .xlsx (Excel moderno).", "warning")
            return redirect(url_for("routes.entradas_importar"))

        tmp_suffix = _uuid.uuid4().hex[:12]
        tmp_path = os.path.join(_tempfile.gettempdir(), f"almacen_entrada_{tmp_suffix}.xlsx")
        file.save(tmp_path)

        try:
            headers_raw, col_indices, filas, errores_prev = _parse_excel_movimiento("entrada", tmp_path)
        except Exception:
            errores_prev = ["Error inesperado al leer el archivo."]
            headers_raw = None
            filas = None

        if errores_prev:
            try:
                os.remove(tmp_path)
            except OSError:
                pass
            for e in errores_prev:
                flash(e, "danger")
            return redirect(url_for("routes.entradas_importar"))

        if not filas:
            try:
                os.remove(tmp_path)
            except OSError:
                pass
            flash("No se encontraron filas válidas para importar.", "warning")
            return redirect(url_for("routes.entradas_importar"))

        headers_mostrar = [h for h in headers_raw if h]
        return render_template(
            "entradas_importar.html",
            preview=True,
            tmp_path=tmp_path,
            headers=headers_mostrar,
            filas=filas[:20],
            total_filas=len(filas),
            nombre_archivo=file.filename,
        )

    return render_template("entradas_importar.html")


@routes_bp.route("/entradas/importar/confirmar", methods=["POST"])
@login_required
def entradas_importar_confirmar():
    tmp_path = request.form.get("tmp_path", "").strip()
    if not tmp_path or not os.path.exists(tmp_path):
        flash("Archivo temporal no encontrado. Vuelve a seleccionar el archivo.", "danger")
        return redirect(url_for("routes.entradas_importar"))

    try:
        headers_raw, col_indices, filas, errores_prev = _parse_excel_movimiento("entrada", tmp_path)
    except Exception:
        errores_prev = ["Error inesperado al leer el archivo temporal."]
        filas = None

    if errores_prev:
        try:
            os.remove(tmp_path)
        except OSError:
            pass
        for e in errores_prev:
            flash(e, "danger")
        return redirect(url_for("routes.entradas_importar"))

    if not filas:
        try:
            os.remove(tmp_path)
        except OSError:
            pass
        flash("No se encontraron filas válidas para importar.", "warning")
        return redirect(url_for("routes.entradas_importar"))

    insertadas = []
    errores = []

    try:
        for f in filas:
            producto = Producto.query.filter_by(codigo=f["codigo"]).first()
            if not producto:
                errores.append(f"'{f['codigo']}': producto no encontrado en BD")
                continue

            entrada = Entrada(
                producto_id=producto.id,
                cantidad=f["cantidad"],
                um=f.get("um") or producto.um,
                zona=f.get("zona", ""),
                ubicacion=f.get("ubicacion", ""),
                alm=f.get("alm", "ALM-01"),
                oc=f.get("oc", ""),
                guia_remision=f.get("guia", ""),
                familia=f.get("familia", ""),
                fecha_ingreso=f.get("fecha") or datetime.now(timezone.utc),
            )
            producto.stock_actual += f["cantidad"]
            db.session.add(entrada)
            insertadas.append(f["codigo"])

        db.session.commit()
        try:
            os.remove(tmp_path)
        except OSError:
            pass

        partes = [f"✅ {len(insertadas)} entradas registradas"]
        if errores:
            partes.append(f"⚠️ {len(errores)} errores")
        msg = "Importación completada: " + ", ".join(partes)
        if errores:
            msg += ". Detalles: " + "; ".join(errores[:5])
            if len(errores) > 5:
                msg += f" y {len(errores) - 5} más."
            flash(msg, "warning")
        else:
            flash(msg, "success")
        return redirect(url_for("routes.entradas"))

    except Exception as exc:
        db.session.rollback()
        try:
            os.remove(tmp_path)
        except OSError:
            pass
        flash(f"Error de base de datos: {exc}. No se guardaron cambios.", "danger")
        return redirect(url_for("routes.entradas_importar"))


# ---------------------------------------------------------------------------
# Importar Salidas desde Excel
# ---------------------------------------------------------------------------

@routes_bp.route("/salidas/importar", methods=["GET", "POST"])
@login_required
def salidas_importar():
    import uuid as _uuid
    import tempfile as _tempfile

    if request.method == "POST":
        if "archivo" not in request.files:
            flash("No se seleccionó ningún archivo.", "danger")
            return redirect(url_for("routes.salidas_importar"))

        file = request.files["archivo"]
        if not file or file.filename == "":
            flash("No se seleccionó ningún archivo.", "danger")
            return redirect(url_for("routes.salidas_importar"))

        if not file.filename.lower().endswith(".xlsx"):
            flash("Solo se aceptan archivos .xlsx (Excel moderno).", "warning")
            return redirect(url_for("routes.salidas_importar"))

        tmp_suffix = _uuid.uuid4().hex[:12]
        tmp_path = os.path.join(_tempfile.gettempdir(), f"almacen_salida_{tmp_suffix}.xlsx")
        file.save(tmp_path)

        try:
            headers_raw, col_indices, filas, errores_prev = _parse_excel_movimiento("salida", tmp_path)
        except Exception:
            errores_prev = ["Error inesperado al leer el archivo."]
            headers_raw = None
            filas = None

        if errores_prev:
            try:
                os.remove(tmp_path)
            except OSError:
                pass
            for e in errores_prev:
                flash(e, "danger")
            return redirect(url_for("routes.salidas_importar"))

        if not filas:
            try:
                os.remove(tmp_path)
            except OSError:
                pass
            flash("No se encontraron filas válidas para importar.", "warning")
            return redirect(url_for("routes.salidas_importar"))

        headers_mostrar = [h for h in headers_raw if h]
        return render_template(
            "salidas_importar.html",
            preview=True,
            tmp_path=tmp_path,
            headers=headers_mostrar,
            filas=filas[:20],
            total_filas=len(filas),
            nombre_archivo=file.filename,
        )

    return render_template("salidas_importar.html")


@routes_bp.route("/salidas/importar/confirmar", methods=["POST"])
@login_required
def salidas_importar_confirmar():
    tmp_path = request.form.get("tmp_path", "").strip()
    if not tmp_path or not os.path.exists(tmp_path):
        flash("Archivo temporal no encontrado. Vuelve a seleccionar el archivo.", "danger")
        return redirect(url_for("routes.salidas_importar"))

    try:
        headers_raw, col_indices, filas, errores_prev = _parse_excel_movimiento("salida", tmp_path)
    except Exception:
        errores_prev = ["Error inesperado al leer el archivo temporal."]
        filas = None

    if errores_prev:
        try:
            os.remove(tmp_path)
        except OSError:
            pass
        for e in errores_prev:
            flash(e, "danger")
        return redirect(url_for("routes.salidas_importar"))

    if not filas:
        try:
            os.remove(tmp_path)
        except OSError:
            pass
        flash("No se encontraron filas válidas para importar.", "warning")
        return redirect(url_for("routes.salidas_importar"))

    insertadas = []
    errores = []

    try:
        for f in filas:
            producto = Producto.query.filter_by(codigo=f["codigo"]).first()
            if not producto:
                errores.append(f"'{f['codigo']}': producto no encontrado en BD")
                continue

            if f["cantidad"] > producto.stock_actual:
                errores.append(
                    f"'{f['codigo']}': stock insuficiente "
                    f"(disponible {producto.stock_actual:.2f}, solicitado {f['cantidad']:.2f})"
                )
                continue

            salida = Salida(
                producto_id=producto.id,
                cantidad=f["cantidad"],
                um=f.get("um") or producto.um,
                nro_vale=f.get("nro_vale", ""),
                oi=f.get("oi", ""),
                c_costo=f.get("c_costo", ""),
                maquina=f.get("maquina", ""),
                categoria=f.get("categoria", ""),
                fecha_salida=f.get("fecha") or datetime.now(timezone.utc),
            )
            producto.stock_actual -= f["cantidad"]
            db.session.add(salida)
            insertadas.append(f["codigo"])

        db.session.commit()
        try:
            os.remove(tmp_path)
        except OSError:
            pass

        partes = [f"✅ {len(insertadas)} salidas registradas"]
        if errores:
            partes.append(f"⚠️ {len(errores)} errores")
        msg = "Importación completada: " + ", ".join(partes)
        if errores:
            msg += ". Detalles: " + "; ".join(errores[:5])
            if len(errores) > 5:
                msg += f" y {len(errores) - 5} más."
            flash(msg, "warning")
        else:
            flash(msg, "success")
        return redirect(url_for("routes.salidas"))

    except Exception as exc:
        db.session.rollback()
        try:
            os.remove(tmp_path)
        except OSError:
            pass
        flash(f"Error de base de datos: {exc}. No se guardaron cambios.", "danger")
        return redirect(url_for("routes.salidas_importar"))


# ---------------------------------------------------------------------------
# Ruta: Exportar productos a Excel
# ---------------------------------------------------------------------------

@routes_bp.route("/productos/exportar")
@login_required
def producto_exportar():
    """Exportar todos los productos a un archivo Excel."""
    try:
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
        from openpyxl.utils import get_column_letter
    except ImportError:
        flash("openpyxl no está instalado.", "danger")
        return redirect(url_for("routes.productos"))

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "MAESTRA"

    headers = [
        "CODIGO", "COD. CATALOGO", "DESCRIPCION DEL PRODUCTO",
        "U.M", "FAMILIA", "STOCK ACTUAL", "STOCK MINIMO"
    ]

    header_font = Font(bold=True, color="FFFFFF", size=11)
    header_fill = PatternFill(start_color="0D6EFD", end_color="0D6EFD", fill_type="solid")
    header_align = Alignment(horizontal="center", vertical="center")
    thin_border = Border(
        left=Side(style="thin"), right=Side(style="thin"),
        top=Side(style="thin"), bottom=Side(style="thin"),
    )

    for col_idx, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col_idx, value=header)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = header_align
        cell.border = thin_border

    productos = Producto.query.order_by(Producto.codigo.asc()).all()
    for row_idx, p in enumerate(productos, 2):
        values = [
            p.codigo, p.cod_catalogo, p.descripcion,
            p.um, p.familia, p.stock_actual, p.stock_minimo,
        ]
        for col_idx, val in enumerate(values, 1):
            cell = ws.cell(row=row_idx, column=col_idx, value=val)
            cell.border = thin_border

    widths = [12, 14, 55, 10, 22, 14, 14]
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)

    from datetime import date
    today = date.today().strftime("%Y%m%d")

    return send_file(
        output,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name=f"productos_{today}.xlsx",
    )

def _producto_form(producto=None):
    if request.method == "POST":
        codigo = request.form.get("codigo", "").strip().upper()
        cod_catalogo = request.form.get("cod_catalogo", "").strip()
        descripcion = request.form.get("descripcion", "").strip()
        um = request.form.get("um", "").strip().upper() or "UND"
        familia = request.form.get("familia", "").strip()
        stock_minimo_str = request.form.get("stock_minimo", "0").strip()
        try:
            stock_minimo = float(stock_minimo_str) if stock_minimo_str else 0.0
        except ValueError:
            stock_minimo = 0.0

        errores = []
        if not codigo:
            errores.append("El campo CÓDIGO es obligatorio.")
        if not descripcion:
            errores.append("El campo DESCRIPCIÓN es obligatorio.")

        # Validar código único
        existente = Producto.query.filter(Producto.codigo == codigo).first()
        if existente and (producto is None or existente.id != producto.id):
            errores.append(f"El código '{codigo}' ya está registrado.")

        if errores:
            for e in errores:
                flash(e, "danger")
            return render_template("producto_form.html", producto=producto, valores=request.form)

        if producto is None:
            producto = Producto()
            db.session.add(producto)

        producto.codigo = codigo
        producto.cod_catalogo = cod_catalogo
        producto.descripcion = descripcion
        producto.um = um
        producto.familia = familia
        producto.stock_minimo = stock_minimo

        db.session.commit()
        flash("Producto guardado correctamente.", "success")
        return redirect(url_for("routes.productos"))

    return render_template("producto_form.html", producto=producto)


# ---------------------------------------------------------------------------
# Registrar Entrada
# ---------------------------------------------------------------------------

@routes_bp.route("/entradas", methods=["GET", "POST"])
@login_required
def entradas():
    productos_list = Producto.query.order_by(Producto.descripcion.asc()).all()

    if request.method == "POST":
        producto_id = request.form.get("producto_id")
        cantidad_str = request.form.get("cantidad", "0").strip()
        zona = request.form.get("zona", "").strip()
        ubicacion = request.form.get("ubicacion", "").strip()
        alm = request.form.get("alm", "ALM-01").strip()
        oc = request.form.get("oc", "").strip()
        guia_remision = request.form.get("guia_remision", "").strip()
        familia = request.form.get("familia", "").strip()
        fecha_str = request.form.get("fecha_ingreso", "").strip()

        errores = []
        if not producto_id:
            errores.append("Debe seleccionar un producto.")
        try:
            cantidad = float(cantidad_str) if cantidad_str else 0.0
        except ValueError:
            cantidad = 0.0
            errores.append("La cantidad debe ser un número válido.")
        if cantidad <= 0:
            errores.append("La cantidad debe ser mayor a 0.")

        # Parsear fecha
        fecha_ingreso = datetime.now(timezone.utc)
        if fecha_str:
            try:
                fecha_ingreso = datetime.strptime(fecha_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            except ValueError:
                errores.append("Formato de fecha inválido (use YYYY-MM-DD).")

        if errores:
            for e in errores:
                flash(e, "danger")
            return render_template("entrada_form.html", productos=productos_list, valores=request.form)

        producto = db.session.get(Producto, int(producto_id))
        if not producto:
            flash("Producto no encontrado.", "danger")
            return redirect(url_for("routes.entradas"))

        entrada = Entrada(
            producto_id=producto.id,
            cantidad=cantidad,
            um=producto.um,
            zona=zona,
            ubicacion=ubicacion,
            alm=alm,
            fecha_ingreso=fecha_ingreso,
            oc=oc,
            guia_remision=guia_remision,
            familia=familia or producto.familia,
        )
        producto.stock_actual += cantidad

        db.session.add(entrada)
        db.session.commit()
        flash(f"Entrada registrada. Stock actualizado: {producto.descripcion} → {producto.stock_actual:.2f} {producto.um}", "success")
        return redirect(url_for("routes.entradas"))

    return render_template("entrada_form.html", productos=productos_list)


# ---------------------------------------------------------------------------
# Registrar Salida
# ---------------------------------------------------------------------------

@routes_bp.route("/salidas", methods=["GET", "POST"])
@login_required
def salidas():
    productos_list = Producto.query.order_by(Producto.descripcion.asc()).all()

    if request.method == "POST":
        producto_id = request.form.get("producto_id")
        cantidad_str = request.form.get("cantidad", "0").strip()
        nro_vale = request.form.get("nro_vale", "").strip()
        oi = request.form.get("oi", "").strip()
        c_costo = request.form.get("c_costo", "").strip()
        maquina = request.form.get("maquina", "").strip()
        categoria = request.form.get("categoria", "").strip()
        fecha_str = request.form.get("fecha_salida", "").strip()

        errores = []
        if not producto_id:
            errores.append("Debe seleccionar un producto.")
        try:
            cantidad = float(cantidad_str) if cantidad_str else 0.0
        except ValueError:
            cantidad = 0.0
            errores.append("La cantidad debe ser un número válido.")
        if cantidad <= 0:
            errores.append("La cantidad debe ser mayor a 0.")

        fecha_salida = datetime.now(timezone.utc)
        if fecha_str:
            try:
                fecha_salida = datetime.strptime(fecha_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            except ValueError:
                errores.append("Formato de fecha inválido (use YYYY-MM-DD).")

        if errores:
            for e in errores:
                flash(e, "danger")
            return render_template("salida_form.html", productos=productos_list, valores=request.form)

        producto = db.session.get(Producto, int(producto_id))
        if not producto:
            flash("Producto no encontrado.", "danger")
            return redirect(url_for("routes.salidas"))

        if cantidad > producto.stock_actual:
            flash(f"Stock insuficiente. Disponible: {producto.stock_actual:.2f} {producto.um}", "danger")
            return render_template("salida_form.html", productos=productos_list, valores=request.form)

        salida = Salida(
            producto_id=producto.id,
            cantidad=cantidad,
            um=producto.um,
            fecha_salida=fecha_salida,
            nro_vale=nro_vale,
            oi=oi,
            c_costo=c_costo,
            maquina=maquina,
            categoria=categoria,
        )
        producto.stock_actual -= cantidad

        db.session.add(salida)
        db.session.commit()
        flash(f"Salida registrada. Stock actualizado: {producto.descripcion} → {producto.stock_actual:.2f} {producto.um}", "success")
        return redirect(url_for("routes.salidas"))

    return render_template("salida_form.html", productos=productos_list)


# ---------------------------------------------------------------------------
# Consulta de Existencias
# ---------------------------------------------------------------------------

@routes_bp.route("/existencias")
@login_required
def existencias():
    search = request.args.get("search", "").strip()
    familia = request.args.get("familia", "").strip()
    solo_bajo = request.args.get("solo_bajo", "").strip()
    con_saldo = request.args.get("con_saldo", "1").strip()  # default: solo con saldo
    page = request.args.get("page", 1, type=int)
    per_page = 20

    query = Producto.query
    if search:
        query = query.filter(
            Producto.descripcion.ilike(f"%{search}%")
            | Producto.codigo.ilike(f"%{search}%")
        )
    if familia:
        query = query.filter(Producto.familia.ilike(f"%{familia}%"))
    if solo_bajo == "1":
        query = query.filter(
            Producto.stock_minimo > 0,
            Producto.stock_actual <= Producto.stock_minimo
        )
    if con_saldo == "1":
        query = query.filter(Producto.stock_actual > 0)

    query = query.order_by(Producto.descripcion.asc())
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    # Obtener lista de familias para el filtro
    familias = sorted(set(
        f[0] for f in db.session.query(Producto.familia).filter(Producto.familia != "").distinct().all()
    ))

    return render_template(
        "existencias.html",
        pagination=pagination,
        search=search,
        familia=familia,
        solo_bajo=solo_bajo,
        con_saldo=con_saldo,
        familias=familias,
    )


@routes_bp.route("/existencias/exportar")
@login_required
def existencias_exportar():
    """Exportar existencias filtradas a Excel."""
    try:
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
        from openpyxl.utils import get_column_letter
    except ImportError:
        flash("openpyxl no está instalado.", "danger")
        return redirect(url_for("routes.existencias"))

    search = request.args.get("search", "").strip()
    familia = request.args.get("familia", "").strip()
    solo_bajo = request.args.get("solo_bajo", "").strip()
    con_saldo = request.args.get("con_saldo", "1").strip()

    query = Producto.query
    if search:
        query = query.filter(
            Producto.descripcion.ilike(f"%{search}%")
            | Producto.codigo.ilike(f"%{search}%")
        )
    if familia:
        query = query.filter(Producto.familia.ilike(f"%{familia}%"))
    if solo_bajo == "1":
        query = query.filter(
            Producto.stock_minimo > 0,
            Producto.stock_actual <= Producto.stock_minimo
        )
    if con_saldo == "1":
        query = query.filter(Producto.stock_actual > 0)
    productos = query.order_by(Producto.descripcion.asc()).all()

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "EXISTENCIAS"

    headers = ["CÓDIGO", "COD. CATÁLOGO", "DESCRIPCIÓN", "U.M",
               "FAMILIA", "STOCK ACTUAL", "STOCK MÍNIMO", "ESTADO"]
    header_font = Font(bold=True, color="FFFFFF", size=11)
    header_fill = PatternFill(start_color="0D6EFD", end_color="0D6EFD", fill_type="solid")
    thin_border = Border(
        left=Side(style="thin"), right=Side(style="thin"),
        top=Side(style="thin"), bottom=Side(style="thin"),
    )

    for ci, h in enumerate(headers, 1):
        c = ws.cell(row=1, column=ci, value=h)
        c.font = header_font; c.fill = header_fill; c.border = thin_border

    for ri, p in enumerate(productos, 2):
        estado = "STOCK BAJO" if (p.stock_bajo and p.stock_minimo > 0) else \
                 "SIN STOCK" if p.stock_actual == 0 else "OK"
        vals = [p.codigo, p.cod_catalogo, p.descripcion, p.um,
                p.familia, p.stock_actual, p.stock_minimo, estado]
        for ci, v in enumerate(vals, 1):
            c = ws.cell(row=ri, column=ci, value=v)
            c.border = thin_border

    widths = [12, 14, 55, 10, 22, 14, 14, 14]
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w

    output = io.BytesIO()
    wb.save(output); output.seek(0)
    from datetime import date
    return send_file(output,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True, download_name=f"existencias_{date.today().strftime('%Y%m%d')}.xlsx")


# ---------------------------------------------------------------------------
# Historial de Movimientos
# ---------------------------------------------------------------------------

@routes_bp.route("/historial")
@login_required
def historial():
    producto_search = request.args.get("producto", "").strip()
    fecha_desde = request.args.get("fecha_desde", "").strip()
    fecha_hasta = request.args.get("fecha_hasta", "").strip()
    tipo = request.args.get("tipo", "").strip()
    page = request.args.get("page", 1, type=int)
    per_page = 20

    # Construir lista combinada
    movimientos = []

    # Entradas
    entradas_query = Entrada.query
    if producto_search:
        entradas_query = entradas_query.join(Producto).filter(
            Producto.descripcion.ilike(f"%{producto_search}%")
            | Producto.codigo.ilike(f"%{producto_search}%")
        )
    if fecha_desde:
        try:
            fd = datetime.strptime(fecha_desde, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            entradas_query = entradas_query.filter(Entrada.fecha_ingreso >= fd)
        except ValueError:
            pass
    if fecha_hasta:
        try:
            fh = datetime.strptime(fecha_hasta, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            entradas_query = entradas_query.filter(Entrada.fecha_ingreso <= fh)
        except ValueError:
            pass

    salidas_query = Salida.query
    if producto_search:
        salidas_query = salidas_query.join(Producto).filter(
            Producto.descripcion.ilike(f"%{producto_search}%")
            | Producto.codigo.ilike(f"%{producto_search}%")
        )
    if fecha_desde:
        try:
            fd = datetime.strptime(fecha_desde, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            salidas_query = salidas_query.filter(Salida.fecha_salida >= fd)
        except ValueError:
            pass
    if fecha_hasta:
        try:
            fh = datetime.strptime(fecha_hasta, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            salidas_query = salidas_query.filter(Salida.fecha_salida <= fh)
        except ValueError:
            pass

    if tipo != "SALIDA":
        for e in entradas_query.all():
            movimientos.append({
                "id": f"E-{e.id}",
                "tipo": "ENTRADA",
                "fecha": e.fecha_ingreso,
                "producto": e.producto.descripcion if e.producto else "—",
                "codigo": e.producto.codigo if e.producto else "—",
                "cantidad": e.cantidad,
                "um": e.um,
                "referencia": e.oc or e.guia_remision or "—",
                "detalle": f"OC: {e.oc}, Guía: {e.guia_remision}, Zona: {e.zona}, Ubic: {e.ubicacion}",
            })
    if tipo != "ENTRADA":
        for s in salidas_query.all():
            movimientos.append({
                "id": f"S-{s.id}",
                "tipo": "SALIDA",
                "fecha": s.fecha_salida,
                "producto": s.producto.descripcion if s.producto else "—",
                "codigo": s.producto.codigo if s.producto else "—",
                "cantidad": s.cantidad,
                "um": s.um,
                "referencia": s.nro_vale or s.oi or "—",
                "detalle": f"Vale: {s.nro_vale}, OI: {s.oi}, C.Costo: {s.c_costo}, Máq: {s.maquina}",
            })

    movimientos.sort(key=lambda m: m["fecha"], reverse=True)

    # Paginación manual
    total = len(movimientos)
    start = (page - 1) * per_page
    end = start + per_page
    movimientos_paginados = movimientos[start:end]

    # Objeto de paginación simple
    class SimplePagination:
        def __init__(self, items, total, page, per_page):
            self.items = items
            self.total = total
            self.page = page
            self.per_page = per_page
            self.pages = max(1, (total + per_page - 1) // per_page)

        @property
        def has_prev(self):
            return self.page > 1

        @property
        def has_next(self):
            return self.page < self.pages

        @property
        def prev_num(self):
            return self.page - 1

        @property
        def next_num(self):
            return self.page + 1

        def iter_pages(self, left_edge=1, left_current=2, right_current=3, right_edge=1):
            last = 0
            for num in range(1, self.pages + 1):
                if (
                    num <= left_edge
                    or (num > self.page - left_current - 1 and num < self.page + right_current)
                    or num > self.pages - right_edge
                ):
                    if last + 1 != num:
                        yield None
                    yield num
                    last = num

    pagination = SimplePagination(movimientos_paginados, total, page, per_page)

    return render_template(
        "historial.html",
        pagination=pagination,
        producto=producto_search,
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
        tipo=tipo,
    )


@routes_bp.route("/historial/exportar")
@login_required
def historial_exportar():
    """Exportar historial de movimientos filtrado a Excel."""
    try:
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
        from openpyxl.utils import get_column_letter
    except ImportError:
        flash("openpyxl no está instalado.", "danger")
        return redirect(url_for("routes.historial"))

    producto_search = request.args.get("producto", "").strip()
    fecha_desde = request.args.get("fecha_desde", "").strip()
    fecha_hasta = request.args.get("fecha_hasta", "").strip()
    tipo = request.args.get("tipo", "").strip()

    # Construir datos igual que en historial() pero sin paginar
    movimientos = []

    entradas_query = Entrada.query
    salidas_query = Salida.query

    if producto_search:
        entradas_query = entradas_query.join(Producto).filter(
            Producto.descripcion.ilike(f"%{producto_search}%")
            | Producto.codigo.ilike(f"%{producto_search}%")
        )
        salidas_query = salidas_query.join(Producto).filter(
            Producto.descripcion.ilike(f"%{producto_search}%")
            | Producto.codigo.ilike(f"%{producto_search}%")
        )
    if fecha_desde:
        try:
            fd = datetime.strptime(fecha_desde, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            entradas_query = entradas_query.filter(Entrada.fecha_ingreso >= fd)
            salidas_query = salidas_query.filter(Salida.fecha_salida >= fd)
        except ValueError:
            pass
    if fecha_hasta:
        try:
            fh = datetime.strptime(fecha_hasta, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            entradas_query = entradas_query.filter(Entrada.fecha_ingreso <= fh)
            salidas_query = salidas_query.filter(Salida.fecha_salida <= fh)
        except ValueError:
            pass

    if tipo != "SALIDA":
        for e in entradas_query.order_by(Entrada.fecha_ingreso.desc()).all():
            movimientos.append([
                e.fecha_ingreso.strftime("%Y-%m-%d %H:%M") if e.fecha_ingreso else "",
                "ENTRADA",
                e.producto.codigo if e.producto else "",
                e.producto.descripcion if e.producto else "",
                e.cantidad, e.um or "",
                e.oc or "", e.guia_remision or "", e.zona or "",
                e.ubicacion or "", e.alm or "", e.familia or "",
            ])
    if tipo != "ENTRADA":
        for s in salidas_query.order_by(Salida.fecha_salida.desc()).all():
            movimientos.append([
                s.fecha_salida.strftime("%Y-%m-%d %H:%M") if s.fecha_salida else "",
                "SALIDA",
                s.producto.codigo if s.producto else "",
                s.producto.descripcion if s.producto else "",
                s.cantidad, s.um or "",
                s.nro_vale or "", s.oi or "", s.c_costo or "",
                s.maquina or "", s.categoria or "", "",
            ])

    movimientos.sort(key=lambda r: r[0], reverse=True)

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "MOVIMIENTOS"

    headers = ["FECHA", "TIPO", "CÓDIGO", "PRODUCTO", "CANTIDAD", "U.M",
               "OC/VALE", "GUÍA/OI", "ZONA/C.COSTO", "UBIC/MÁQ", "ALM/CAT", "FAMILIA"]
    hf = Font(bold=True, color="FFFFFF", size=11)
    hfill = PatternFill(start_color="0D6EFD", end_color="0D6EFD", fill_type="solid")
    tb = Border(left=Side(style="thin"), right=Side(style="thin"),
                top=Side(style="thin"), bottom=Side(style="thin"))

    for ci, h in enumerate(headers, 1):
        c = ws.cell(row=1, column=ci, value=h)
        c.font = hf; c.fill = hfill; c.border = tb

    for ri, row in enumerate(movimientos, 2):
        for ci, v in enumerate(row, 1):
            c = ws.cell(row=ri, column=ci, value=v)
            c.border = tb

    widths = [18, 10, 12, 50, 10, 8, 14, 14, 14, 14, 14, 18]
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w

    output = io.BytesIO()
    wb.save(output); output.seek(0)
    from datetime import date
    return send_file(output,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True, download_name=f"historial_{date.today().strftime('%Y%m%d')}.xlsx")


# ===========================================================================
# Administración de Usuarios
# ===========================================================================

@routes_bp.route("/admin/usuarios")
@login_required
def admin_usuarios():
    """Lista de usuarios del sistema."""
    usuarios = User.query.order_by(User.username.asc()).all()
    return render_template("admin_usuarios.html", usuarios=usuarios)


@routes_bp.route("/admin/usuarios/nuevo", methods=["GET", "POST"])
@login_required
def admin_usuario_nuevo():
    """Crear nuevo usuario."""
    if request.method == "POST":
        username = request.form.get("username", "").strip().lower()
        password = request.form.get("password", "")
        password2 = request.form.get("password2", "")

        errores = []
        if not username or len(username) < 3:
            errores.append("El usuario debe tener al menos 3 caracteres.")
        if User.query.filter_by(username=username).first():
            errores.append(f"El usuario '{username}' ya existe.")
        if len(password) < 4:
            errores.append("La contraseña debe tener al menos 4 caracteres.")
        if password != password2:
            errores.append("Las contraseñas no coinciden.")

        if errores:
            for e in errores:
                flash(e, "danger")
            return render_template("admin_usuario_form.html", valores=request.form)

        user = User(username=username)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        flash(f"Usuario '{username}' creado correctamente.", "success")
        return redirect(url_for("routes.admin_usuarios"))

    return render_template("admin_usuario_form.html")


@routes_bp.route("/admin/usuarios/editar/<int:user_id>", methods=["GET", "POST"])
@login_required
def admin_usuario_editar(user_id):
    """Editar usuario existente."""
    user = db.session.get(User, user_id)
    if not user:
        flash("Usuario no encontrado.", "danger")
        return redirect(url_for("routes.admin_usuarios"))

    if request.method == "POST":
        password = request.form.get("password", "")
        password2 = request.form.get("password2", "")

        errores = []
        if password:
            if len(password) < 4:
                errores.append("La contraseña debe tener al menos 4 caracteres.")
            if password != password2:
                errores.append("Las contraseñas no coinciden.")

        if errores:
            for e in errores:
                flash(e, "danger")
            return render_template("admin_usuario_form.html", usuario=user, valores=request.form)

        if password:
            user.set_password(password)
            db.session.commit()
            flash(f"Contraseña de '{user.username}' actualizada.", "success")
        else:
            flash("No se realizaron cambios (dejar contraseña en blanco).", "info")

        return redirect(url_for("routes.admin_usuarios"))

    return render_template("admin_usuario_form.html", usuario=user)


@routes_bp.route("/admin/usuarios/eliminar/<int:user_id>", methods=["POST"])
@login_required
def admin_usuario_eliminar(user_id):
    """Eliminar usuario."""
    user = db.session.get(User, user_id)
    if not user:
        flash("Usuario no encontrado.", "danger")
        return redirect(url_for("routes.admin_usuarios"))

    if user.username == "admin":
        flash("No se puede eliminar al usuario administrador principal.", "danger")
        return redirect(url_for("routes.admin_usuarios"))

    if user.id == current_user.id:
        flash("No puedes eliminar tu propio usuario.", "danger")
        return redirect(url_for("routes.admin_usuarios"))

    db.session.delete(user)
    db.session.commit()
    flash(f"Usuario '{user.username}' eliminado.", "success")
    return redirect(url_for("routes.admin_usuarios"))
