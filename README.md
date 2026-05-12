# Almacén - Sistema de Control de Inventarios

Aplicación web para control de inventarios (almacén) desarrollada con Flask, SQLAlchemy y Bootstrap 5.

## Características

- 🔐 **Autenticación** de usuario (admin/admin por defecto)
- 📦 **CRUD de productos** del catálogo
- 📥 **Registro de entradas** (ingresos/compras) con actualización automática de stock
- 📤 **Registro de salidas** (consumos/despachos) con validación de stock suficiente
- 📊 **Dashboard** con resumen de productos, movimientos recientes y alertas de stock bajo
- 🔍 **Consulta de existencias** con filtros por producto, familia y stock bajo
- 📋 **Historial de movimientos** combinado (entradas + salidas) con filtros por fecha, producto y tipo
- ⚠️ **Alertas de stock mínimo** configurables por producto
- 📱 **Diseño responsive** con Bootstrap 5 (funciona en PC, tablet y móvil)
- 🗄️ **SQLite** por defecto (100% offline), preparado para **PostgreSQL** (Neon/Render) vía variable `DATABASE_URL`

## Estructura del proyecto

```
almacen/
├── app/
│   ├── __init__.py          # Factory y configuración de la app
│   ├── app.py               # Punto de entrada
│   ├── models.py            # Modelos SQLAlchemy
│   ├── routes.py            # Rutas y lógica de negocio
│   ├── seed.py              # Carga inicial de datos
│   ├── templates/           # Plantillas Jinja2
│   │   ├── base.html        # Layout base con sidebar
│   │   ├── login.html       # Página de inicio de sesión
│   │   ├── index.html       # Dashboard
│   │   ├── productos.html   # Listado de productos
│   │   ├── producto_form.html # Formulario crear/editar producto
│   │   ├── entrada_form.html  # Formulario registrar entrada
│   │   ├── salida_form.html   # Formulario registrar salida
│   │   ├── existencias.html   # Consulta de stock
│   │   └── historial.html     # Historial de movimientos
│   └── static/
│       └── css/
│           └── style.css    # Estilos personalizados
├── requirements.txt
├── Procfile                 # Para despliegue en Render
└── README.md
```

## Requisitos

- Python 3.9 o superior
- pip (gestor de paquetes de Python)

## Instalación y ejecución local

### 1. Clonar o copiar el proyecto

```bash
cd almacen
```

### 2. Crear entorno virtual (recomendado)

```bash
python -m venv venv
source venv/bin/activate      # Linux/Mac
# venv\Scripts\activate       # Windows
```

### 3. Instalar dependencias

```bash
pip install -r requirements.txt
```

### 4. (Opcional) Cargar datos de demostración

Si no tienes un archivo Excel, carga 30 productos de ejemplo con movimientos:

```bash
python -m app.seed --demo
```

Si tienes un archivo `datos_iniciales.xlsx` con hojas MAESTRA, ENTRADA y SALIDAS:

```bash
python -m app.seed --excel ruta/a/tu/archivo.xlsx
```

Para reiniciar los datos desde cero:

```bash
python -m app.seed --reset --demo
```

### 5. Ejecutar la aplicación

```bash
python -m app.app
# O también:
python app/app.py
```

La aplicación se ejecutará en `http://localhost:5000`.

> **Credenciales por defecto:** Usuario: `admin` / Contraseña: `admin`

## Uso de la aplicación

1. **Iniciar sesión** con las credenciales predeterminadas.
2. **Dashboard**: vista general con resumen de productos, movimientos recientes y alertas de stock bajo.
3. **Productos**: gestionar el catálogo (crear, editar, eliminar productos).
4. **Registrar Entrada**: ingresar compras o ingresos al almacén. El stock se actualiza automáticamente.
5. **Registrar Salida**: registrar consumos o despachos. Valida que haya stock suficiente.
6. **Existencias**: consultar el stock actual con filtros.
7. **Historial**: ver todos los movimientos combinados con filtros avanzados.

## Despliegue en Render

### Configuración de base de datos PostgreSQL (Neon)

1. Crea una base de datos en [Neon](https://neon.tech) (gratis).
2. Obtén la URL de conexión (formato: `postgresql://user:pass@host/dbname`).
3. En Render, configura la variable de entorno:
   - **Key**: `DATABASE_URL`
   - **Value**: la URL de conexión de Neon

La aplicación detecta automáticamente `DATABASE_URL` y usa PostgreSQL en lugar de SQLite.

### Pasos para desplegar en Render

1. Sube el código a un repositorio en GitHub/GitLab.
2. En Render, crea un nuevo **Web Service**.
3. Configura:
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn app.app:app`
   - **Environment Variables**:
     - `DATABASE_URL`: tu URL de PostgreSQL (opcional, si no se usa SQLite)
     - `SECRET_KEY`: una clave secreta aleatoria (ej: generar con `python -c "import secrets; print(secrets.token_hex(32))"`)

El `Procfile` incluido ya tiene la configuración necesaria.

### Cargar datos iniciales en Render

Después del despliegue, puedes cargar datos de demostración ejecutando en la consola de Render:

```bash
python -m app.seed --demo
```

## Importación desde Excel

El script `seed.py` puede leer archivos Excel con la siguiente estructura de hojas:

- **MAESTRA**: CODIGO, COD. CATALOGO, DESCRIPCION DEL PRODUCTO, U.M, FAMILIA
- **ENTRADA**: CODIGO, COD. CATALOGO, DESCRIPCION, CANTIDA, U.M2, ZONA, UBICACIÓN, ALM, F.INGRESO, OC, G.REMISION, FAMILIA
- **SALIDAS**: CODIGO, COD. CATALOGO, DESCRIPCION, CANTIDAD, U.M2, F. SALIDA, N° VALE, OI, C.COSTO, MAQUINA, CATEGPRIA

Coloca tu archivo como `datos_iniciales.xlsx` en la raíz del proyecto y ejecuta:

```bash
python -m app.seed
```

## Licencia

Uso interno / Propietario.
