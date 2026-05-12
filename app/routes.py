import io
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
    query = query.order_by(Producto.descripcion.asc())
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
# Ruta: Importar productos desde Excel
# ---------------------------------------------------------------------------

@routes_bp.route("/productos/importar", methods=["GET", "POST"])
@login_required
def producto_importar():
    """Importar productos desde archivo Excel.
    
    Crea los que no existen, actualiza los existentes.
    Maneja duplicados internos, truncado de campos y transacción atómica.
    """
    if request.method == "POST":
        # --- Validación del archivo ---
        if "archivo" not in request.files:
            flash("No se seleccionó ningún archivo.", "danger")
            return redirect(url_for("routes.producto_importar"))

        file = request.files["archivo"]
        if not file or file.filename == "":
            flash("No se seleccionó ningún archivo.", "danger")
            return redirect(url_for("routes.producto_importar"))

        # Aceptar .xlsx y .xls (openpyxl maneja ambos)
        if not file.filename.lower().endswith((".xlsx", ".xls")):
            flash("El archivo debe ser .xlsx o .xls.", "danger")
            return redirect(url_for("routes.producto_importar"))

        try:
            import openpyxl
        except ImportError:
            flash("openpyxl no está instalado.", "danger")
            return redirect(url_for("routes.productos"))

        try:
            wb = openpyxl.load_workbook(file, data_only=True)
            ws = wb.active
        except Exception:
            flash("El archivo no es un Excel válido o está corrupto.", "danger")
            return redirect(url_for("routes.producto_importar"))

        # --- Leer encabezados ---
        first_row = list(ws.iter_rows(min_row=1, max_row=1, values_only=True))
        if not first_row or not any(c is not None for c in first_row[0]):
            flash("El archivo Excel está vacío.", "danger")
            return redirect(url_for("routes.producto_importar"))

        headers_raw = []
        for cell_val in first_row[0]:
            s = str(cell_val).strip().upper() if cell_val is not None else ""
            headers_raw.append(s)

        # Mapear columnas encontradas
        col_indices = {}
        for i, h in enumerate(headers_raw):
            for key, mapped in COL_MAP.items():
                if key.upper() == h:
                    col_indices[mapped] = i
                    break

        if "codigo" not in col_indices:
            flash("El Excel no tiene una columna 'CODIGO' reconocible. "
                  "Columnas encontradas: " + ", ".join(h for h in headers_raw if h), "danger")
            return redirect(url_for("routes.producto_importar"))

        # --- Leer filas y validar duplicados internos ---
        filas = []
        codigos_vistos = set()
        errores_duplicados = 0

        for row_idx, row in enumerate(ws.iter_rows(min_row=2, values_only=True), 2):
            if not any(cell is not None for cell in row):
                continue

            codigo = _excel_val(row, col_indices, "codigo").upper()
            if not codigo:
                continue

            descripcion = _excel_val(row, col_indices, "descripcion")
            if not descripcion:
                errores_duplicados += 1  # se cuenta como error
                continue

            # Detectar duplicados DENTRO del mismo Excel
            if codigo in codigos_vistos:
                errores_duplicados += 1
                continue
            codigos_vistos.add(codigo)

            cod_catalogo = _excel_val(row, col_indices, "cod_catalogo")
            um = _excel_val(row, col_indices, "um").upper() or "UND"
            familia = _excel_val(row, col_indices, "familia")

            # Leer stock_minimo si existe la columna
            stock_minimo = 0.0
            if "stock_minimo" in col_indices:
                raw_stock = _excel_val(row, col_indices, "stock_minimo")
                try:
                    stock_minimo = max(0.0, float(raw_stock.replace(",", ".")))
                except (ValueError, AttributeError):
                    stock_minimo = 0.0

            filas.append({
                "codigo": codigo,
                "cod_catalogo": cod_catalogo,
                "descripcion": descripcion,
                "um": um,
                "familia": familia,
                "stock_minimo": stock_minimo,
            })

        if not filas:
            flash("No se encontraron filas válidas para importar.", "warning")
            return redirect(url_for("routes.producto_importar"))

        # --- Ejecutar importación en transacción atómica ---
        creados = 0
        actualizados = 0
        errores_db = 0

        try:
            for f in filas:
                # Sanitizar campos
                codigo = _sanitize_field(f["codigo"], "codigo")
                descripcion = _sanitize_field(f["descripcion"], "descripcion")
                cod_catalogo = _sanitize_field(f["cod_catalogo"], "cod_catalogo")
                um = _sanitize_field(f["um"], "um") or "UND"
                familia = _sanitize_field(f["familia"], "familia")

                if not descripcion:
                    errores_db += 1
                    continue

                producto = Producto.query.filter_by(codigo=codigo).first()
                if producto:
                    producto.cod_catalogo = cod_catalogo
                    producto.descripcion = descripcion
                    producto.um = um
                    producto.familia = familia
                    if "stock_minimo" in col_indices:
                        producto.stock_minimo = f["stock_minimo"]
                    actualizados += 1
                else:
                    producto = Producto(
                        codigo=codigo,
                        cod_catalogo=cod_catalogo,
                        descripcion=descripcion,
                        um=um,
                        familia=familia,
                        stock_minimo=f["stock_minimo"] if "stock_minimo" in col_indices else 0.0,
                    )
                    db.session.add(producto)
                    creados += 1

            db.session.commit()
            total_errores = errores_duplicados + errores_db
            msg = f"Importación completada: {creados} creados, {actualizados} actualizados"
            if total_errores:
                msg += f", {total_errores} errores (duplicados omitidos)"
            flash(msg, "success" if total_errores == 0 else "warning")
            return redirect(url_for("routes.productos"))

        except Exception:
            db.session.rollback()
            flash("Error de base de datos durante la importación. "
                  "No se guardaron cambios. Verifica que los datos sean válidos.", "danger")
            return redirect(url_for("routes.producto_importar"))

    return render_template("producto_importar.html")


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
        familias=familias,
    )


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
