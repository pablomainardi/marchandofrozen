from flask import Flask, Blueprint, render_template, request, redirect, url_for, session, flash, send_file, jsonify
import sqlite3
from functools import wraps
from datetime import datetime, timedelta
import pandas as pd
import io
import os
from collections import defaultdict
import zipfile
import mysql.connector

app = Flask(__name__)
#app.secret_key = os.environ.get('SECRET_KEY', 'esta_es_una_clave_secreta_para_desarrollo') # PRUEBAS LOCALES
#ACCESS_CODE = os.environ.get('ACCESS_CODE', '1111')  # o el código que quieras por defecto - # PRUEBAS LOCALES 
app.secret_key = os.environ.get('SECRET_KEY')  # ideal no usar valor por defecto en producción
ACCESS_CODE = os.environ.get('ACCESS_CODE')  # o el código que quieras por defecto

DB_NAME = 'marchando_base.db'

LOGIN_REQUIRED = False  # Cambiar a True para activar validación

bp_backups = Blueprint('backups', __name__)

BACKUP_DIR = os.path.join('static', 'backups')
DB_PATH = os.path.join('marchando_base.db')  # Ajusta si tu DB está en otro lugar

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'): # PRUEBAS LOCALES
#        if LOGIN_REQUIRED and not session.get('logged_in'):
            return redirect(url_for('login', next=request.path))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/backup/download_db')
def download_db():
    if os.path.exists(DB_FILE):
        return send_file(DB_FILE, as_attachment=True)
    else:
        return "Base de datos no encontrada", 404
    
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        code = request.form.get('code', '')
        if code == ACCESS_CODE:
            session['logged_in'] = True
            next_page = request.args.get('next') or url_for('index')
            return redirect(next_page)
        else:
            flash('Código incorrecto, intenta otra vez.', 'danger')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Has cerrado sesión.', 'info')
    return redirect(url_for('login'))
# para habilitar local
#def get_conn():
#    conn = sqlite3.connect(DB_NAME)
#    conn.row_factory = sqlite3.Row
#    return conn

def get_conn():
    # Conexión directa al hosting remoto
    conn = mysql.connector.connect(
        host="97j8os.h.filess.io",
        user="marchando_base_swunggoose",
        password="947e5010d57e22b4a674fc5e72c57332aeaab83a",
        database="marchando_base_swunggoose",
        port=3307  # reemplazá si tu hosting usa otro
    )
    return conn

@app.route('/')
@login_required
def index():
    return render_template('index.html')

# --- backups ----
def ensure_backup_dir():
    os.makedirs(BACKUP_DIR, exist_ok=True)

def create_backup():
    """Crear un backup ZIP de la base actual."""
    ensure_backup_dir()
    now = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"backup_{now}.zip"
    backup_path = os.path.join(BACKUP_DIR, backup_name)
    with zipfile.ZipFile(backup_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.write(DB_PATH, arcname=os.path.basename(DB_PATH))
    return backup_name

@bp_backups.route('/backups')
@login_required
def listar_backups():
    ensure_backup_dir()
    archivos = sorted(
        [f for f in os.listdir(BACKUP_DIR) if f.endswith('.zip')],
        reverse=True
    )
    return render_template('backups.html', archivos=archivos)

@bp_backups.route('/backups/subir_base', methods=['POST'])
@login_required
def subir_base():
    """Subir toda la base de datos local SQLite a la base remota MySQL"""
    # --- Configuración de conexión MySQL remota ---
    MYSQL_HOST = "97j8os.h.filess.io"
    MYSQL_USER = "marchando_base_swunggoose"
    MYSQL_PASSWORD = "947e5010d57e22b4a674fc5e72c57332aeaab83a"
    MYSQL_DB = "marchando_base_swunggoose"

    # Conexión a SQLite local
    sqlite_conn = sqlite3.connect(DB_NAME)
    sqlite_conn.row_factory = sqlite3.Row
    sqlite_cursor = sqlite_conn.cursor()

    # Conexión a MySQL remota
    try:
        mysql_conn = mysql.connector.connect(
            host=MYSQL_HOST,
            user=MYSQL_USER,
            password=MYSQL_PASSWORD,
            database=MYSQL_DB,
            charset='utf8mb4'
        )
        mysql_cursor = mysql_conn.cursor()
    except Exception as e:
        flash(f"Error conectando a la base remota: {e}", "danger")
        return redirect(url_for('backups.listar_backups'))

    try:
        # Listar todas las tablas de SQLite
        sqlite_cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tablas = [t['name'] for t in sqlite_cursor.fetchall()]

        for tabla in tablas:
            sqlite_cursor.execute(f"SELECT * FROM {tabla}")
            filas = sqlite_cursor.fetchall()
            columnas = [desc[0] for desc in sqlite_cursor.description]

            if not filas:
                continue  # no hay datos, saltar

            # Generar query de INSERT con placeholders
            placeholders = ','.join(['%s'] * len(columnas))
            columnas_str = ','.join(columnas)
            sql_insert = f"INSERT INTO {tabla} ({columnas_str}) VALUES ({placeholders}) " \
                         f"ON DUPLICATE KEY UPDATE " + ','.join([f"{c}=VALUES({c})" for c in columnas])

            # Ejecutar cada fila
            for fila in filas:
                mysql_cursor.execute(sql_insert, tuple(fila))

        mysql_conn.commit()
        flash("Base de datos subida correctamente a MySQL remota.", "success")
    except Exception as e:
        flash(f"Error durante la subida: {e}", "danger")
    finally:
        sqlite_cursor.close()
        sqlite_conn.close()
        mysql_cursor.close()
        mysql_conn.close()

    return redirect(url_for('backups.listar_backups'))

@bp_backups.route('/backups/crear', methods=['POST'])
@login_required
def crear_backup_manual():
    nombre = create_backup()
    flash(f'Backup {nombre} creado correctamente.', 'success')
    return redirect(url_for('backups.listar_backups'))

@bp_backups.route('/backups/eliminar', methods=['POST'])
@login_required
def eliminar_backups():
    seleccionados = request.form.getlist('archivos')
    if not seleccionados:
        flash('No seleccionaste ningún backup para eliminar.', 'warning')
        return redirect(url_for('backups.listar_backups'))
    eliminados = []
    for archivo in seleccionados:
        ruta = os.path.join(BACKUP_DIR, archivo)
        if os.path.exists(ruta):
            os.remove(ruta)
            eliminados.append(archivo)
    flash(f'{len(eliminados)} backup(s) eliminado(s) correctamente.', 'success')
    return redirect(url_for('backups.listar_backups'))

# === CLIENTES ===
@app.route('/clientes')
@login_required
def clientes():
    with get_conn() as conn:
        clientes = conn.execute('''
            SELECT c.*, 
                   IFNULL(SUM(p.precio_total), 0) as consumo_total
            FROM clientes c
            LEFT JOIN pedidos p ON c.id = p.cliente_id AND p.estado = 'finalizado'
            GROUP BY c.id
            ORDER BY c.nombre
        ''').fetchall()
    return render_template('clientes.html', clientes=clientes)

@app.route('/clientes/nuevo', methods=['POST'])
@login_required
def nuevo_cliente():
    create_backup()
    data = request.form
    with get_conn() as conn:
        conn.execute('INSERT INTO clientes (nombre, contacto, direccion) VALUES (?, ?, ?)',
                     (data['nombre'], data['contacto'], data['direccion']))
        conn.commit()
    return redirect(url_for('clientes'))

@app.route('/clientes/editar/<int:id>', methods=['POST'])
@login_required
def editar_cliente(id):
    create_backup()
    data = request.form
    with get_conn() as conn:
        conn.execute('UPDATE clientes SET nombre=?, contacto=?, direccion=? WHERE id=?',
                     (data['nombre'], data['contacto'], data['direccion'], id))
        conn.commit()
    return redirect(url_for('clientes'))

@app.route('/clientes/eliminar/<int:id>')
@login_required
def eliminar_cliente(id):
    create_backup()
    with get_conn() as conn:
        # Borrar pedidos relacionados
        conn.execute('DELETE FROM pedidos WHERE cliente_id = ?', (id,))
        # Borrar cliente
        conn.execute('DELETE FROM clientes WHERE id = ?', (id,))
        conn.commit()
    return redirect(url_for('clientes'))


# --- RUTA: Buscar producto por código ---
@app.route('/buscar_producto_por_codigo')
@login_required
def buscar_producto_por_codigo():
    codigo = request.args.get('codigo', '').strip()
    if not codigo:
        return jsonify({"existe": False})
    
    with get_conn() as conn:
        # Buscar el código dentro de la lista separada por comas
        producto = conn.execute("""
            SELECT id, producto, tipo, cantidad, unidad, costo_total, referencia, codigo_barra
            FROM ingredientes
            WHERE ',' || codigo_barra || ',' LIKE '%,' || ? || ',%'
        """, (codigo,)).fetchone()

    if producto:
        return jsonify({"existe": True, "producto": dict(producto)})
    else:
        return jsonify({"existe": False})


# --- Guardar producto desde modal escáner: inserta o actualiza ---
@app.route('/guardar_producto', methods=['POST'])
@login_required
def guardar_producto():
    create_backup()
    data = request.form
    codigo_barra = data.get('codigo_barra', '').strip()  # Puede ser un único código
    producto = data.get('producto', '').strip()
    unidad = data.get('unidad', '').strip()
    referencia = data.get('referencia', '').strip()
    tipo = data.get('tipo', '').strip()

    try:
        cantidad = float(data.get('cantidad', '0'))
        costo_total = round(float(data.get('costo_total', '0')), 2)
    except ValueError:
        flash("Cantidad o costo total inválidos.", "danger")
        return redirect(url_for('modificar_ingredientes'))

    if not codigo_barra or not producto or cantidad <= 0 or costo_total <= 0:
        flash("Faltan campos obligatorios o valores inválidos.", "danger")
        return redirect(url_for('modificar_ingredientes'))

    costo_unitario = round(costo_total / cantidad, 4) if cantidad else 0
    fecha_actual = datetime.now().strftime('%d/%m/%Y')
  # objeto date, sin hora


    with get_conn() as conn:
        # Buscar si alguno de los códigos ya existe en la base
        existente = conn.execute("""
            SELECT * FROM ingredientes
            WHERE ',' || codigo_barra || ',' LIKE '%,' || ? || ',%'
        """, (codigo_barra,)).fetchone()

        if existente:
            # Actualizamos el producto
            conn.execute('''
    UPDATE ingredientes SET
        producto = ?, cantidad = ?, unidad = ?, costo_total = ?,
        costo_unitario = ?, referencia = ?, tipo = ?, ultima_actualizacion = ?
    WHERE id = ?
''', (producto, cantidad, unidad, costo_total, costo_unitario, referencia, tipo, fecha_actual, existente['id']))
            mensaje = "Producto actualizado correctamente."
        else:
            # Insertamos nuevo
            conn.execute('''
    INSERT INTO ingredientes (producto, tipo, referencia, cantidad, unidad, costo_total,
                              costo_unitario, ultima_actualizacion, codigo_barra)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
''', (producto, tipo, referencia, cantidad, unidad, costo_total,
      costo_unitario, fecha_actual, codigo_barra))
            mensaje = "Producto agregado correctamente."

        conn.commit()

    flash(mensaje, "success")
    return redirect(url_for('modificar_ingredientes'))

@app.route('/actualizar_precios')
@login_required
def actualizar_precios():

    with get_conn() as conn:
        rows = conn.execute("""
            SELECT 
                id,
                producto,
                tipo,
                referencia,
                cantidad,
                unidad,
                costo_total,
                ultima_actualizacion
            FROM ingredientes
            ORDER BY producto
        """).fetchall()

    ingredientes = []

    for r in rows:

        i = dict(r)

        if i["ultima_actualizacion"]:

            fecha_str = i["ultima_actualizacion"]

            try:
                fecha = datetime.strptime(fecha_str, "%Y-%m-%d")
            except ValueError:
                try:
                    fecha = datetime.strptime(fecha_str, "%Y-%m-%d %H:%M")
                except ValueError:
                    fecha = datetime.strptime(fecha_str, "%d/%m/%Y")

            dias = (datetime.now() - fecha).days

        else:
            dias = 999

        i["dias_actualizacion"] = dias
        ingredientes.append(i)

    return render_template(
        "actualizar_precios.html",
        ingredientes=ingredientes
    )

@app.route('/guardar_precios', methods=['POST'])
@login_required
def guardar_precios():

    create_backup()

    precios = request.form

    with get_conn() as conn:

        for key, value in precios.items():

            if key.startswith("precio_"):

                ingrediente_id = key.replace("precio_", "")
                nuevo_precio = float(value)

                actual = conn.execute(
                    "SELECT costo_total FROM ingredientes WHERE id = ?",
                    (ingrediente_id,)
                ).fetchone()

                if actual and float(actual["costo_total"]) != nuevo_precio:

                    conn.execute("""
                        UPDATE ingredientes
                        SET costo_total = ?,
                            ultima_actualizacion = ?
                        WHERE id = ?
                    """, (
                        nuevo_precio,
                        datetime.now().strftime("%Y-%m-%d"),
                        ingrediente_id
                    ))

        conn.commit()

    flash("Precios actualizados correctamente", "success")

    return redirect(url_for("actualizar_precios"))

# --- Editar ingrediente desde pantalla principal ---
@app.route('/ingredientes/editar/<int:id>', methods=['POST'])
@login_required
def editar_ingrediente(id):
    create_backup()
    data = request.form
    codigo_barra = data.get('codigo_barra', '').strip()  # Aquí puede haber varios códigos separados por coma
    producto = data['producto']
    cantidad = float(data['cantidad'])
    unidad = data['unidad']
    referencia = data.get('referencia', '')
    tipo = data.get('tipo', '')
    costo_total = round(float(data['costo_total']), 2)
    costo_unitario = round(costo_total / cantidad, 4) if cantidad else 0
    fecha_actual = datetime.now().strftime('%d/%m/%Y')
  # objeto date, sin hora

    with get_conn() as conn:
        conn.execute('''
    UPDATE ingredientes SET
        producto = ?, cantidad = ?, unidad = ?, referencia = ?,
        tipo = ?, costo_total = ?, costo_unitario = ?, codigo_barra = ?, ultima_actualizacion = ?
    WHERE id = ?
''', (producto, cantidad, unidad, referencia, tipo, costo_total,
      costo_unitario, codigo_barra, fecha_actual, id))
        conn.commit()

    flash('Ingrediente actualizado correctamente', 'success')
    return redirect(url_for('modificar_ingredientes'))

@app.route('/ingredientes/eliminar/<int:id>')
@login_required
def eliminar_ingrediente(id):
    create_backup()
    with get_conn() as conn:
        conn.execute('DELETE FROM ingredientes WHERE id = ?', (id,))
        conn.commit()
    flash('Ingrediente eliminado correctamente')
    return redirect(url_for('modificar_ingredientes'))

@app.route('/ingredientes/agregar', methods=['POST'])
@login_required
def agregar_ingrediente():
    create_backup()
    data = request.form
    producto = data['producto']
    cantidad = float(data['cantidad'])
    unidad = data['unidad']
    referencia = data.get('referencia', '')
    tipo = data.get('tipo', '')
    codigo_barra = data.get('codigo_barra', '').strip()  # <- NUEVO
    costo_total = round(float(data['costo_total']), 2)
    costo_unitario = round(costo_total / cantidad, 4) if cantidad else 0
    fecha_actual = datetime.now().strftime('%d/%m/%Y')
  # objeto date, sin hora

    with get_conn() as conn:
        conn.execute('''
    INSERT INTO ingredientes (producto, cantidad, unidad, referencia, tipo,
                              costo_total, costo_unitario, codigo_barra, ultima_actualizacion)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
''', (producto, cantidad, unidad, referencia, tipo,
      costo_total, costo_unitario, codigo_barra, fecha_actual))
        conn.commit()

    flash('Ingrediente agregado correctamente', 'success')
    return redirect(url_for('modificar_ingredientes'))


@app.route('/modificar_ingredientes')
@login_required
def modificar_ingredientes():
    with get_conn() as conn:
        ingredientes_raw = conn.execute('SELECT * FROM ingredientes ORDER BY producto').fetchall()

        referencias_raw = conn.execute("""
            SELECT DISTINCT referencia FROM ingredientes
            WHERE referencia IS NOT NULL AND referencia != ''
        """).fetchall()

        codigos_raw = conn.execute("""
            SELECT DISTINCT codigo_barra FROM ingredientes
            WHERE codigo_barra IS NOT NULL AND codigo_barra != ''
        """).fetchall()

    ingredientes = []
    for i in ingredientes_raw:
        fila = dict(i)
        try:
            fila['costo_unitario'] = float(fila['costo_unitario'])
        except (TypeError, ValueError):
            fila['costo_unitario'] = 0.0
        ingredientes.append(fila)

    referencias = [r['referencia'] for r in referencias_raw]
    codigos_barra = [c['codigo_barra'] for c in codigos_raw]

    return render_template('modificar_ingredientes.html',
                           ingredientes=ingredientes,
                           referencias=referencias,
                           codigos_barra=codigos_barra)


# --- Exportar ingredientes con código de barra ---
@app.route('/exportar_ingredientes')
@login_required
def exportar_ingredientes():
    with get_conn() as conn:
        df = pd.read_sql_query("""
            SELECT producto, cantidad, unidad, costo_total, tipo, referencia,
       codigo_barra, ultima_actualizacion
FROM ingredientes
        """, conn)

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Ingredientes')
    output.seek(0)

    return send_file(output, as_attachment=True, download_name='ingredientes.xlsx',
                     mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')


# --- Importar ingredientes con código de barra ---# --- Importar ingredientes con código de barra ---
# --- Importar ingredientes con código de barra ---
@app.route('/importar_ingredientes', methods=['POST'])
@login_required
def importar_ingredientes():
    create_backup()
    archivo = request.files.get('archivo_excel')
    if not archivo:
        flash('No se seleccionó archivo para importar.', 'danger')
        return redirect(url_for('modificar_ingredientes'))

    try:
        df = pd.read_excel(archivo)
    except Exception as e:
        flash(f"Error al leer el archivo Excel: {e}", 'danger')
        return redirect(url_for('modificar_ingredientes'))

    df.columns = [col.strip().lower() for col in df.columns]

    with get_conn() as conn:
        for _, row in df.iterrows():
            producto = str(row.get('producto', '')).strip()
            cantidad = float(row.get('cantidad', 0) or 0)
            unidad = str(row.get('unidad', '')).strip()
            tipo = str(row.get('tipo', '')).strip()
            referencia = str(row.get('referencia', '')).strip()
            codigo_barra = str(row.get('codigo_barra', '')).strip()
            costo_total = float(row.get('costo_total', 0) or 0)
            costo_unitario = round(costo_total / cantidad, 4) if cantidad else 0

            existente = conn.execute('SELECT * FROM ingredientes WHERE producto = ?', (producto,)).fetchone()

            if existente:
                hubo_cambios = (
                    float(existente['cantidad']) != cantidad or
                    existente['unidad'] != unidad or
                    existente['tipo'] != tipo or
                    existente['referencia'] != referencia or
                    existente['codigo_barra'] != codigo_barra or
                    float(existente['costo_total']) != costo_total or
                    round(float(existente['costo_unitario']), 4) != costo_unitario
                )

                if hubo_cambios:
                    fecha_actual = datetime.now().strftime('%d/%m/%Y')
                    conn.execute('''
                        UPDATE ingredientes SET
                            cantidad=?, unidad=?, tipo=?, referencia=?,
                            codigo_barra=?, costo_total=?, costo_unitario=?, ultima_actualizacion=?
                        WHERE producto=?
                    ''', (cantidad, unidad, tipo, referencia, codigo_barra,
                          costo_total, costo_unitario, fecha_actual, producto))
            else:
                fecha_actual = datetime.now().strftime('%d/%m/%Y')
                conn.execute('''
                    INSERT INTO ingredientes (producto, cantidad, unidad, tipo, referencia,
                                              codigo_barra, costo_total, costo_unitario, ultima_actualizacion)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (producto, cantidad, unidad, tipo, referencia,
                      codigo_barra, costo_total, costo_unitario, fecha_actual))

        conn.commit()

    flash('Ingredientes importados correctamente.', 'success')
    return redirect(url_for('modificar_ingredientes'))


@app.route('/buscar_ingrediente')
@login_required
def buscar_ingrediente():
    termino = request.args.get('q', '')
    with get_conn() as conn:
        resultados = conn.execute('''
            SELECT * FROM ingredientes WHERE producto LIKE ? LIMIT 10
        ''', ('%' + termino + '%',)).fetchall()
    return jsonify([dict(row) for row in resultados])

# === RECETAS ===
@app.route('/eliminar_receta/<int:id>')
@login_required
def eliminar_receta(id):
    create_backup()
    with get_conn() as conn:
        conn.execute('DELETE FROM recetas WHERE id = ?', (id,))
        conn.execute('DELETE FROM receta_ingredientes WHERE receta_id = ?', (id,))
        conn.commit()
    flash('Receta eliminada correctamente.', 'success')
    return redirect(url_for('ver_recetas'))

@app.route('/recetas')
@login_required
def ver_recetas():
    with get_conn() as conn:
        recetas = conn.execute('''
            SELECT r.*, 
                   COALESCE(SUM(ri.cantidad * i.costo_unitario), 0) AS valor_total, 
                   COALESCE(lp.precio_cliente, 0) AS precio_cliente
            FROM recetas r
            LEFT JOIN receta_ingredientes ri ON r.id = ri.receta_id
            LEFT JOIN ingredientes i ON ri.ingrediente_id = i.id
            LEFT JOIN lista_precios lp ON r.id = lp.receta_id
            GROUP BY r.id
            ORDER BY r.nombre
        ''').fetchall()
    return render_template('modificar_recetas.html', recetas=recetas)

@app.route('/nueva_receta', methods=['GET', 'POST'])
@login_required
def nueva_receta():
    if request.method == 'POST':
        create_backup()
        nombre = request.form['nombre']
        comentario = request.form.get('referencia', '')

        with get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'INSERT INTO recetas (nombre, referencia) VALUES (?, ?)',
                (nombre, comentario)
            )
            receta_id = cursor.lastrowid
            conn.commit()

        return redirect(url_for('modificar_receta', id=receta_id))

    with get_conn() as conn:
        recetas = [dict(r) for r in conn.execute(
            "SELECT id, nombre FROM recetas ORDER BY nombre"
        ).fetchall()]

    return render_template('nueva_receta.html', recetas=recetas)


@app.route("/receta/<int:receta_id>")
@login_required
def ver_receta(receta_id):
    conn = get_conn()
    receta = conn.execute("SELECT * FROM recetas WHERE id = ?", (receta_id,)).fetchone()

    ingredientes = conn.execute("""
        SELECT ri.id, i.producto, ri.cantidad, i.unidad, i.costo_unitario,
               (ri.cantidad * i.costo_unitario) AS costo_total
        FROM receta_ingredientes ri
        JOIN ingredientes i ON ri.ingrediente_id = i.id
        WHERE ri.receta_id = ?
    """, (receta_id,)).fetchall()

    costo_total = sum([ing["costo_total"] for ing in ingredientes])

    precio = conn.execute("""
        SELECT precio_cliente FROM lista_precios WHERE receta_id = ?
    """, (receta_id,)).fetchone()
    precio_cliente = precio["precio_cliente"] if precio else 0

    conn.close()
    return render_template("receta_ingredientes.html",
                           receta=receta,
                           ingredientes=ingredientes,
                           costo_total=costo_total,
                           precio_cliente=precio_cliente)

@app.route("/presupuesto", methods=["GET", "POST"])
@login_required
def presupuesto():
    conn = get_conn()
    if request.method == "POST" and request.is_json:
        create_backup()
        data = request.get_json()
        cliente_id = data.get("cliente_id")
        fecha = data.get("fecha")
        recetas = data.get("recetas", [])

        # --- Insertar cada línea como pedido pendiente ---
        for r in recetas:
            cantidad = int(r["cantidad"])
            pu = float(r["precio_unitario"])
            pt = float(r["total"])
            conn.execute(
                """INSERT INTO pedidos
                   (cliente_id, receta_id, fecha, cantidad, precio_unitario, precio_total, estado)
                   VALUES (?, ?, ?, ?, ?, ?, 'pendiente')""",
                (cliente_id, r["receta_id"], fecha, cantidad, pu, pt)
            )

        # --- Calcular total venta ---
        total_venta = sum(float(r["total"]) for r in recetas)

        # --- Crear string de recetas con nombre ---
        recetas_str_list = []
        total_costo = 0
        for r in recetas:
            receta = conn.execute("SELECT nombre FROM recetas WHERE id = ?", (r['receta_id'],)).fetchone()
            nombre_receta = receta['nombre'] if receta else f"Receta {r['receta_id']}"
            recetas_str_list.append(f"{nombre_receta}x{r['cantidad']}")

            # --- Opcional: calcular costo real según ingredientes ---
            costo_receta = conn.execute("""
                SELECT COALESCE(SUM(ri.cantidad * i.costo_unitario),0) AS costo_total
                FROM receta_ingredientes ri
                JOIN ingredientes i ON ri.ingrediente_id = i.id
                WHERE ri.receta_id = ?
            """, (r['receta_id'],)).fetchone()['costo_total']
            total_costo += costo_receta * int(r['cantidad'])

        recetas_str = " | ".join(recetas_str_list)

        # --- Insertar en tabla ORDENES ---
        conn.execute("""
            INSERT INTO ordenes (cliente_id, total_venta, total_costo, recetas, fecha)
            VALUES (?, ?, ?, ?, ?)
        """, (cliente_id, total_venta, total_costo, recetas_str, fecha))

        conn.commit()
        conn.close()
        return jsonify({"status": "ok", "msg": "Presupuesto convertido en pedido correctamente."})

    # --- GET: mostrar formulario ---
    hoy = datetime.now().strftime("%Y-%m-%d")
    clientes = conn.execute("SELECT id, nombre FROM clientes ORDER BY nombre").fetchall()
    recetas = conn.execute("""
        SELECT r.id, r.nombre,
               IFNULL(lp.precio_cliente, 0.0) AS precio_cliente
        FROM recetas r
        LEFT JOIN lista_precios lp ON r.id = lp.receta_id
        ORDER BY r.nombre
    """).fetchall()
    conn.close()
    return render_template("presupuesto.html",
                           hoy=hoy,
                           clientes=[dict(c) for c in clientes],
                           recetas=[dict(r) for r in recetas])

# === PEDIDOS ===
@app.route('/estadisticas_pedidos', methods=['GET'])
@login_required
def estadisticas_pedidos():
    conn = get_conn()
    cur = conn.cursor()

    # Filtro de mes/año
    fecha = request.args.get('fecha', '').strip()
    filtro_sql = ""
    params = []

    if fecha:
        try:
            mes, anio = fecha.split('/')
            mes = mes.zfill(2)
            filtro_sql = " AND strftime('%m', p.fecha) = ? AND strftime('%Y', p.fecha) = ?"
            params.extend([mes, anio])
        except ValueError:
            fecha = ""

    # Traemos todos los pedidos finalizados con filtro
    pedidos = cur.execute(
        f"SELECT * FROM pedidos p WHERE p.estado = 'finalizado' {filtro_sql}",
        params
    ).fetchall()

    # Totales generales
    total_recetas = sum([p['cantidad'] for p in pedidos]) if pedidos else 0
    total_vendido = sum([p['precio_total'] for p in pedidos]) if pedidos else 0

    # Total de compras (costo real calculado por ingredientes usados)
    ingredientes = cur.execute(f"""
        SELECT i.id,
               i.producto AS ingrediente,
               i.unidad AS unidad,
               i.costo_unitario AS costo_unitario,
               SUM(ri.cantidad * p.cantidad) AS total_usado
        FROM pedidos p
        JOIN receta_ingredientes ri ON p.receta_id = ri.receta_id
        JOIN ingredientes i ON ri.ingrediente_id = i.id
        WHERE p.estado = 'finalizado' {filtro_sql}
        GROUP BY i.id
    """, params).fetchall()

    total_costo = sum([f['total_usado'] * f['costo_unitario'] for f in ingredientes]) if ingredientes else 0

    # Por cliente
    clientes = cur.execute(f"""
        SELECT c.id,
               c.nombre AS cliente,
               COUNT(p.id) AS total_pedidos,
               SUM(p.precio_total) AS total_pagado
        FROM pedidos p
        JOIN clientes c ON p.cliente_id = c.id
        WHERE p.estado = 'finalizado' {filtro_sql}
        GROUP BY c.id
        ORDER BY total_pagado DESC
    """, params).fetchall()

    # Por receta
    recetas = cur.execute(f"""
        SELECT r.id,
               r.nombre AS receta,
               SUM(p.cantidad) AS total_vendida
        FROM pedidos p
        JOIN recetas r ON p.receta_id = r.id
        WHERE p.estado = 'finalizado' {filtro_sql}
        GROUP BY r.id
        ORDER BY total_vendida DESC
    """, params).fetchall()

    conn.close()

    # Renderizamos la vista
    return render_template('estadisticas_pedidos.html',
                           total_recetas=total_recetas,
                           total_vendido=total_vendido,
                           total_costo=total_costo,
                           ganancia=total_vendido - total_costo,
                           clientes=clientes,
                           recetas=recetas,
                           ingredientes=ingredientes,
                           fecha=fecha)

@app.route('/detalle_cliente/<int:cliente_id>', methods=['GET'])
@login_required
def detalle_cliente(cliente_id):
    conn = get_conn()
    cur = conn.cursor()

    # Filtro opcional por mes/año
    fecha = request.args.get('fecha', '').strip()
    filtro_sql = ""
    params = [cliente_id]

    if fecha:
        try:
            mes, anio = fecha.split('/')
            mes = mes.zfill(2)
            filtro_sql = " AND strftime('%m', p.fecha) = ? AND strftime('%Y', p.fecha) = ?"
            params.extend([mes, anio])
        except ValueError:
            pass

    # Cantidad total por receta para el cliente
    pedidos_cliente = cur.execute(f"""
        SELECT r.nombre AS receta,
               SUM(p.cantidad) AS cantidad
        FROM pedidos p
        JOIN recetas r ON p.receta_id = r.id
        WHERE p.cliente_id = ? AND p.estado = 'finalizado' {filtro_sql}
        GROUP BY r.id
        ORDER BY cantidad DESC
    """, params).fetchall()

    conn.close()

    resultado = [{'receta': row['receta'], 'cantidad': row['cantidad']} for row in pedidos_cliente]

    return jsonify(resultado)

@app.route('/cambiar_estado_pedido', methods=['GET'])
@login_required
def cambiar_estado_pedido_form():
    cliente_buscar = request.args.get('cliente_buscar', '').strip()
    conn = get_conn()
    c = conn.cursor()

    # Traemos pedidos junto con el id de orden correspondiente
    query = '''
        SELECT p.id, o.id AS ordenes_id, p.cliente_id, c.nombre AS cliente,
               p.receta_id, r.nombre AS receta,
               p.fecha, p.estado, p.cantidad
        FROM pedidos p
        JOIN clientes c ON p.cliente_id = c.id
        JOIN recetas r ON p.receta_id = r.id
        JOIN ordenes o ON o.cliente_id = p.cliente_id AND o.fecha = p.fecha
        WHERE 1=1
    '''
    params = []

    if cliente_buscar:
        query += " AND c.nombre LIKE ?"
        params.append(f'%{cliente_buscar}%')

    query += " ORDER BY p.fecha DESC"

    c.execute(query, params)
    pedidos = c.fetchall()
    conn.close()

    # Agrupar pedidos por cliente y fecha, incluyendo ordenes_id
    pedidos_agrupados = {}
    for p in pedidos:
        clave = (p['cliente_id'], p['fecha'])
        if clave not in pedidos_agrupados:
            pedidos_agrupados[clave] = {
                'cliente_id': p['cliente_id'],
                'cliente': p['cliente'],
                'fecha': p['fecha'],
                'ordenes_id': p['ordenes_id'],  # <-- agregamos aquí
                'pedidos': [],
            }
        pedidos_agrupados[clave]['pedidos'].append(p)

    pedidos_agrupados = list(pedidos_agrupados.values())

    return render_template(
        'cambiar_estado_pedido.html',
        pedidos_agrupados=pedidos_agrupados,
        cliente_buscar=cliente_buscar
    )

@app.route('/cambiar_estado_pedido', methods=['POST'])
@login_required
def cambiar_estado_pedido():
    create_backup()
    accion = request.form.get('accion')
    conn = get_conn()
    cur = conn.cursor()

    # Obtener todos los grupos cliente_id + fecha + ordenes_id
    cur.execute('''
        SELECT DISTINCT p.cliente_id, p.fecha, o.id AS ordenes_id
        FROM pedidos p
        JOIN ordenes o ON o.cliente_id = p.cliente_id AND o.fecha = p.fecha
    ''')
    grupos = cur.fetchall()

    if accion == 'guardar':
        for grupo in grupos:
            cliente_id = grupo['cliente_id']
            fecha = grupo['fecha']
            campo_estado = f'estado_{cliente_id}_{fecha}'
            nuevo_estado = request.form.get(campo_estado)
            if nuevo_estado in ['pendiente', 'finalizado']:
                cur.execute(
                    'UPDATE pedidos SET estado = ? WHERE cliente_id = ? AND fecha = ?',
                    (nuevo_estado, cliente_id, fecha)
                )
        conn.commit()
        flash('Estados de pedidos actualizados correctamente.')

    elif accion == 'eliminar':
        eliminados = 0
        for grupo in grupos:
            cliente_id = grupo['cliente_id']
            fecha = grupo['fecha']
            ordenes_id = grupo['ordenes_id']
            campo_eliminar = f'eliminar_{cliente_id}_{fecha}'
            if request.form.get(campo_eliminar) == 'on':
                # Eliminar pedidos
                cur.execute(
                    'DELETE FROM pedidos WHERE cliente_id = ? AND fecha = ?',
                    (cliente_id, fecha)
                )
                # Eliminar orden correspondiente
                cur.execute(
                    'DELETE FROM ordenes WHERE id = ?',
                    (ordenes_id,)
                )
                eliminados += 1
        conn.commit()
        if eliminados:
            flash(f'Se eliminaron {eliminados} grupo(s) de pedidos y órdenes.')
        else:
            flash('No se seleccionaron grupos para eliminar.')

    conn.close()
    return redirect(url_for('pedidos'))

@app.route('/finalizar_pedido/<int:cliente_id>/<fecha>/<estado>')
@login_required
def finalizar_pedido(cliente_id, fecha, estado):
    create_backup()
    with get_conn() as conn:
        conn.execute('''
            UPDATE pedidos SET estado = 'finalizado'
            WHERE cliente_id = ? AND fecha = ? AND estado = ?
        ''', (cliente_id, fecha, estado))
        conn.commit()
    flash('Pedido marcado como finalizado.')
    return redirect(url_for('pedidos'))

@app.route('/pedidos')
@login_required
def pedidos():
    cliente = request.args.get('cliente', '').strip()
    fecha = request.args.get('fecha', '').strip()  # Ahora será MM/YYYY
    estado = request.args.get('estado', '').strip()
    
    conn = get_conn()
    c = conn.cursor()

    # --- CONSULTA PRINCIPAL --- #
    # Traemos pedidos agrupados por la tabla ordenes para obtener el número de pedido y totales
    query = '''
        SELECT o.id AS ordenes_id,
               o.cliente_id,
               c.nombre AS cliente_nombre,
               o.fecha,
               o.total_venta AS total,
               o.total_costo,
               o.recetas,
               MAX(p.estado) AS estado
        FROM ordenes o
        JOIN clientes c ON o.cliente_id = c.id
        JOIN pedidos p ON p.cliente_id = o.cliente_id AND p.fecha = o.fecha
        WHERE 1=1
    '''
    params = []

    if cliente:
        query += ' AND LOWER(c.nombre) LIKE ?'
        params.append(f'%{cliente.lower()}%')

    # --- FILTRO POR MES/AÑO --- #
    if fecha:
        try:
            mes, anio = fecha.split('/')
            query += " AND strftime('%m', o.fecha) = ? AND strftime('%Y', o.fecha) = ?"
            params.extend([mes.zfill(2), anio])
        except ValueError:
            pass  # Si el formato es incorrecto, no aplicamos filtro

    # --- FILTRO POR ESTADO --- #
    if estado and estado != 'todos':
        query += ' AND p.estado = ?'
        params.append(estado)

    query += ' GROUP BY o.id ORDER BY o.fecha DESC'

    c.execute(query, params)
    filas = c.fetchall()

    # --- ARMAR AGRUPAMIENTO PARA EL HTML --- #
    pedidos_agrupados = []
    for fila in filas:
        # Traemos los pedidos individuales de cada orden para mostrar en el acordeón
        c.execute('''
            SELECT p.id, r.nombre AS nombre_receta, p.cantidad, p.precio_unitario, p.estado
            FROM pedidos p
            JOIN recetas r ON p.receta_id = r.id
            WHERE p.cliente_id = ? AND p.fecha = ?
            ORDER BY r.nombre
        ''', (fila['cliente_id'], fila['fecha']))
        pedidos = c.fetchall()

        pedidos_agrupados.append({
            'ordenes_id': fila['ordenes_id'],       # <-- número de pedido desde ordenes
            'cliente_id': fila['cliente_id'],
            'cliente_nombre': fila['cliente_nombre'],
            'fecha': fila['fecha'],
            'total': fila['total'],
            'estado': fila['estado'],
            'pedidos': pedidos
        })

    # --- LISTA DE CLIENTES --- #
    c.execute('SELECT id, nombre FROM clientes ORDER BY nombre')
    clientes = c.fetchall()

    conn.close()

    return render_template('pedidos.html',
                           pedidos_agrupados=pedidos_agrupados,
                           clientes=clientes)


@app.route('/imprimir_pedido/<int:cliente_id>/<fecha>/<estado>')
@login_required
def imprimir_pedido(cliente_id, fecha, estado):
    conn = get_conn()

    # --- TRAER DATOS DE LA ORDEN --- #
    pedido = conn.execute('''
        SELECT 
            c.nombre AS cliente,
            c.contacto,
            c.direccion,
            o.id AS orden_id,
            o.cliente_id,
            o.fecha,
            MAX(p.estado) AS estado,
            o.total_venta AS total,
            o.total_costo,
            o.recetas
        FROM ordenes o
        JOIN clientes c ON o.cliente_id = c.id
        JOIN pedidos p ON p.cliente_id = o.cliente_id AND p.fecha = o.fecha
        WHERE o.cliente_id = ? AND o.fecha = ?
        LIMIT 1
    ''', (cliente_id, fecha)).fetchone()

    # --- DETALLES INDIVIDUALES DE RECETAS --- #
    detalles = conn.execute('''
        SELECT 
            r.nombre AS receta,
            p.cantidad,
            (SELECT precio_cliente 
             FROM lista_precios 
             WHERE receta_id = r.id) AS precio_cliente
        FROM pedidos p
        JOIN recetas r ON p.receta_id = r.id
        WHERE p.cliente_id = ? 
        AND p.fecha = ?
    ''', (cliente_id, fecha)).fetchall()

    total = sum([
        d["precio_cliente"] * d["cantidad"] 
        for d in detalles
    ])

    conn.close()

    if not pedido:
        flash('Pedido no encontrado.', 'danger')
        return redirect(url_for('pedidos'))

    return render_template(
        'imprimir_pedido.html',
        pedido=pedido,
        detalles=detalles,
        total_general=total
    )

@app.route('/lista_precios', methods=['GET', 'POST'])
@login_required
def lista_precios():
    conn = get_conn()
    cur = conn.cursor()

    if request.method == 'POST':
        create_backup()
        for key, value in request.form.items():
            if key.startswith('precio_'):
                receta_id = key.replace('precio_', '')
                try:
                    precio = float(value)
                    cur.execute('''
                        INSERT INTO lista_precios (receta_id, precio_cliente)
                        VALUES (?, ?)
                        ON CONFLICT(receta_id) DO UPDATE SET precio_cliente=excluded.precio_cliente
                    ''', (receta_id, precio))
                except ValueError:
                    pass
        conn.commit()
        flash('Precios actualizados correctamente.', 'success')
        return redirect(url_for('lista_precios'))

    cur.execute('''
        SELECT 
            r.id, 
            r.nombre, 
            IFNULL(lp.precio_cliente, 0.0) AS precio_cliente,
            IFNULL(SUM(ri.costo_total), 0.0) AS costo_unitario
        FROM recetas r
        LEFT JOIN lista_precios lp ON r.id = lp.receta_id
        LEFT JOIN receta_ingredientes ri ON r.id = ri.receta_id
        LEFT JOIN ingredientes i ON ri.ingrediente_id = i.id
        GROUP BY r.id
        ORDER BY r.nombre
    ''')
    lista = cur.fetchall()
    conn.close()

    # Agregamos margen de ganancia a cada receta
    lista_dict = []
    for item in lista:
        costo = item['costo_unitario']
        precio = item['precio_cliente']
        if costo > 0:
            margen = round(((precio - costo) / costo) * 100, 2)
        else:
            margen = 0.0
        item_dict = dict(item)
        item_dict['margen'] = margen
        lista_dict.append(item_dict)

    return render_template('lista_precios.html', lista=lista_dict)

@app.route('/editar_pedido/<int:cliente_id>/<fecha>/<estado>', methods=['GET', 'POST'])
@login_required
def editar_pedido(cliente_id, fecha, estado):

    with get_conn() as conn:
        if request.method == 'POST':
            create_backup()

            # --- Obtener datos del POST ---
            if request.is_json:
                data = request.get_json()
                cliente_id_new = int(data['cliente_id'])
                fecha_new = data['fecha']
                estado_new = data['estado']
                recetas_pedido = data['recetas']
            else:
                cliente_id_new = int(request.form['cliente_id'])
                fecha_new = request.form['fecha']
                estado_new = request.form['estado']
                receta_ids = request.form.getlist('receta_id')
                cantidades = request.form.getlist('cantidad')
                precios_unitarios = request.form.getlist('precio_unitario')
                totales = request.form.getlist('total')
                recetas_pedido = []
                for i in range(len(receta_ids)):
                    recetas_pedido.append({
                        'receta_id': int(receta_ids[i]),
                        'cantidad': int(cantidades[i]),
                        'precio_unitario': float(precios_unitarios[i]),
                        'total': float(totales[i])
                    })

            # --- Borrar líneas existentes del pedido ---
            conn.execute('DELETE FROM pedidos WHERE cliente_id = ? AND fecha = ? AND estado = ?',
                         (cliente_id, fecha, estado))

            # --- Insertar nuevas líneas de pedido ---
            for r in recetas_pedido:
                conn.execute('''
                    INSERT INTO pedidos (cliente_id, receta_id, fecha, cantidad, precio_unitario, precio_total, estado)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (cliente_id_new, r['receta_id'], fecha_new, r['cantidad'], r['precio_unitario'], r['total'], estado_new))

            # --- Actualizar tabla ORDENES ---
            total_venta = sum(r['total'] for r in recetas_pedido)
            total_costo = 0
            recetas_str = []

            for r in recetas_pedido:
                # costo dinámico según ingredientes
                costo_receta = conn.execute("""
                    SELECT COALESCE(SUM(ri.cantidad * i.costo_unitario),0) AS costo_total
                    FROM receta_ingredientes ri
                    JOIN ingredientes i ON ri.ingrediente_id = i.id
                    WHERE ri.receta_id = ?
                """, (r['receta_id'],)).fetchone()['costo_total']
                total_costo += costo_receta * r['cantidad']

                receta = conn.execute("SELECT nombre FROM recetas WHERE id = ?", (r['receta_id'],)).fetchone()
                nombre_receta = receta['nombre'] if receta else f"Receta {r['receta_id']}"
                recetas_str.append(f"{nombre_receta}x{r['cantidad']}")

            # La orden siempre existe → actualizamos por cliente_id y fecha
            conn.execute("""
                UPDATE ordenes
                SET total_venta = ?, total_costo = ?, recetas = ?
                WHERE cliente_id = ? AND fecha = ?
            """, (total_venta, total_costo, " | ".join(recetas_str), cliente_id, fecha))

            conn.commit()

            flash('Pedido actualizado correctamente', 'success')
            return jsonify({'status': 'ok', 'msg': 'Pedido actualizado correctamente'})

        # --- GET: cargar formulario ---
        filas = conn.execute('''
            SELECT p.*, r.nombre as receta_nombre
            FROM pedidos p
            JOIN recetas r ON p.receta_id = r.id
            WHERE p.cliente_id = ? AND p.fecha = ? AND p.estado = ?
        ''', (cliente_id, fecha, estado)).fetchall()
        total_global = sum(f['precio_total'] for f in filas) if filas else 0

        if not filas:
            flash('Pedido no encontrado', 'danger')
            return redirect(url_for('pedidos'))

        clientes = conn.execute('SELECT * FROM clientes ORDER BY nombre').fetchall()
        recetas = conn.execute('''
            SELECT r.*, lp.precio_cliente AS precio_cliente_unitario
            FROM recetas r
            LEFT JOIN lista_precios lp ON r.id = lp.receta_id
            ORDER BY r.nombre
        ''').fetchall()

    pedido_info = {
        'cliente_id': cliente_id,
        'fecha': fecha,
        'estado': estado
    }

    return render_template('editar_pedido.html',
                           pedido=pedido_info,
                           lineas=filas,
                           clientes=clientes,
                           recetas=recetas,
                           total_global=total_global)

@app.route('/eliminar_pedido/<int:cliente_id>/<fecha>')
@login_required
def eliminar_pedido(cliente_id, fecha):
    create_backup()
    with get_conn() as conn:
        # --- Guardar los datos de referencia antes de borrar ---
        pedidos_a_borrar = conn.execute(
            'SELECT id, cliente_id, fecha FROM pedidos WHERE cliente_id = ? AND fecha = ?',
            (cliente_id, fecha)
        ).fetchall()

        if not pedidos_a_borrar:
            flash('No se encontraron pedidos para eliminar.', 'warning')
            return redirect(url_for('pedidos'))

        # Tomar cliente_id y fecha del primer registro (constantes para la orden)
        cliente_ref = pedidos_a_borrar[0]['cliente_id']
        fecha_ref = pedidos_a_borrar[0]['fecha']

        # --- Borrar todos los pedidos del cliente y fecha ---
        conn.execute(
            'DELETE FROM pedidos WHERE cliente_id = ? AND fecha = ?',
            (cliente_id, fecha)
        )

        # --- Borrar la orden asociada ---
        conn.execute(
            'DELETE FROM ordenes WHERE cliente_id = ? AND fecha = ?',
            (cliente_ref, fecha_ref)
        )

        conn.commit()
        flash('Pedidos y orden asociados eliminados correctamente.', 'success')

    return redirect(url_for('pedidos'))

@app.route('/marcar_finalizado/<int:id>')
@login_required
def marcar_finalizado(id):
    create_backup()
    with get_conn() as conn:
        pedido = conn.execute('SELECT cliente_id, fecha FROM pedidos WHERE id = ?', (id,)).fetchone()
        if pedido:
            conn.execute('UPDATE pedidos SET estado = "finalizado" WHERE cliente_id = ? AND fecha = ?',
                         (pedido['cliente_id'], pedido['fecha']))
            conn.commit()
            flash('Pedido marcado como finalizado.', 'success')
        else:
            flash('Pedido no encontrado.', 'danger')
    return redirect(url_for('pedidos'))

@app.route('/marcar_pendiente/<int:id>')
@login_required
def marcar_pendiente(id):
    create_backup()
    with get_conn() as conn:
        pedido = conn.execute('SELECT cliente_id, fecha FROM pedidos WHERE id = ?', (id,)).fetchone()
        if pedido:
            conn.execute('UPDATE pedidos SET estado = "pendiente" WHERE cliente_id = ? AND fecha = ?',
                         (pedido['cliente_id'], pedido['fecha']))
            conn.commit()
            flash('Pedido marcado como pendiente.', 'success')
        else:
            flash('Pedido no encontrado.', 'danger')
    return redirect(url_for('pedidos'))

# === COMPRAS ===
@app.route('/ingredientes_pedidos', methods=['POST'])
@login_required
def ingredientes_pedidos():
    data = request.get_json()
    pedidos = data.get('pedidos', [])  # lista de dicts {cliente_id, fecha}

    if not pedidos:
        return jsonify({'status': 'error', 'msg': 'No se recibieron pedidos'})

    # Generar condiciones para SQL
    condiciones = []
    params = []
    for p in pedidos:
        condiciones.append('(p.cliente_id = ? AND p.fecha = ? AND p.estado = "pendiente")')
        params.extend([p['cliente_id'], p['fecha']])

    where_clause = ' OR '.join(condiciones)

    query = f'''
        SELECT 
            i.producto, 
            i.tipo, 
            ri.unidad, 
            i.costo_unitario,
            SUM(ri.cantidad * p.cantidad) as cantidad_total
        FROM pedidos p
        JOIN receta_ingredientes ri ON p.receta_id = ri.receta_id
        JOIN ingredientes i ON ri.ingrediente_id = i.id
        WHERE {where_clause}
        GROUP BY i.producto, i.tipo, ri.unidad, i.costo_unitario
    '''

    with get_conn() as conn:
        filas = conn.execute(query, params).fetchall()

    ingredientes = []
    for f in filas:
        ingredientes.append({
            'producto': f['producto'],
            'tipo': f['tipo'] or '',
            'unidad': f['unidad'],
            'costo_unitario': float(f['costo_unitario'] or 0),
            'cantidad_total': float(f['cantidad_total'] or 0),
        })

    return jsonify({'status': 'ok', 'ingredientes': ingredientes})

@app.route('/compras')
@login_required
def compras():
    with get_conn() as conn:
        filas = conn.execute('''
            SELECT p.*, r.nombre as receta, c.nombre as cliente
            FROM pedidos p
            JOIN recetas r ON p.receta_id = r.id
            JOIN clientes c ON p.cliente_id = c.id
            WHERE p.estado = 'pendiente'
            ORDER BY c.nombre, p.fecha DESC
        ''').fetchall()

    from collections import defaultdict
    grupos = defaultdict(lambda: {'pedidos': [], 'cliente': '', 'cliente_id': None, 'fecha': None, 'estado': None, 'total': 0})

    for f in filas:
        key = (f['cliente_id'], f['fecha'], f['estado'])
        grupos[key]['pedidos'].append(f)
        grupos[key]['cliente'] = f['cliente']
        grupos[key]['cliente_id'] = f['cliente_id']
        grupos[key]['fecha'] = f['fecha']
        grupos[key]['estado'] = f['estado']
        grupos[key]['total'] += f['precio_total']

    pedidos_agrupados = list(grupos.values())

    return render_template('compras.html', pedidos_agrupados=pedidos_agrupados)

# Mostrar formulario de edición completa
@app.route('/modificar_receta/<int:id>', methods=['GET'])
@login_required
def modificar_receta(id):
    
    with get_conn() as conn:
        receta = conn.execute('SELECT * FROM recetas WHERE id = ?', (id,)).fetchone()
        ingredientes_receta = conn.execute('''
            SELECT ri.id as ri_id, i.id as ingrediente_id, i.producto, ri.cantidad, ri.unidad
            FROM receta_ingredientes ri
            JOIN ingredientes i ON ri.ingrediente_id = i.id
            WHERE receta_id = ?
        ''', (id,)).fetchall()
    return render_template('editar_receta.html', receta=receta, ingredientes=ingredientes_receta)

@app.route('/editar_ingrediente_receta/<int:ri_id>', methods=['POST'])
@login_required
def editar_ingrediente_receta(ri_id):
    create_backup()
    cantidad = float(request.form['cantidad'])
    unidad = request.form['unidad']
    with get_conn() as conn:
        costo_unitario = conn.execute('SELECT costo_unitario FROM receta_ingredientes WHERE id = ?', (ri_id,)).fetchone()[0]
        costo_total = cantidad * costo_unitario
        conn.execute('''
            UPDATE receta_ingredientes SET cantidad = ?, unidad = ?, costo_total = ? WHERE id = ?
        ''', (cantidad, unidad, costo_total, ri_id))
        conn.commit()
        receta_id = conn.execute('SELECT receta_id FROM receta_ingredientes WHERE id = ?', (ri_id,)).fetchone()[0]
    return redirect(url_for('modificar_receta', id=receta_id))

# Actualizar nombre y referencia
# Actualizar nombre, referencia y todos los ingredientes de la receta
@app.route('/actualizar_receta/<int:id>', methods=['POST'])
@login_required
def actualizar_receta(id):
    create_backup()
    nombre = request.form['nombre']
    referencia = request.form.get('referencia', '')

    with get_conn() as conn:
        # Actualizar los datos principales de la receta
        conn.execute(
            'UPDATE recetas SET nombre = ?, referencia = ? WHERE id = ?',
            (nombre, referencia, id)
        )

        # Actualizar todos los ingredientes enviados
        # Los IDs de ingredientes están en los inputs name="ingredientes_ids"
        ingredientes_ids = request.form.getlist('ingredientes_ids')
        for ri_id in ingredientes_ids:
            cantidad = request.form.get(f'cantidad_{ri_id}')
            unidad = request.form.get(f'unidad_{ri_id}')
            if cantidad and unidad:
                cantidad = float(cantidad)
                conn.execute('''
                    UPDATE receta_ingredientes
                    SET cantidad = ?, unidad = ?, 
                        costo_total = cantidad * costo_unitario
                    WHERE id = ?
                ''', (cantidad, unidad, ri_id))

        conn.commit()

    return redirect(url_for('ver_recetas'))

@app.route('/duplicar_receta/<int:receta_id>')
@login_required
def duplicar_receta(receta_id):
    create_backup()
    conn = get_conn()
    cur = conn.cursor()

    # Obtener receta original
    receta = cur.execute(
        "SELECT nombre, referencia FROM recetas WHERE id = ?",
        (receta_id,)
    ).fetchone()

    if not receta:
        conn.close()
        return redirect(url_for('ver_recetas'))

    # Crear nueva receta duplicada
    nuevo_nombre = receta['nombre'] + " copia"

    cur.execute(
        "INSERT INTO recetas (nombre, referencia) VALUES (?, ?)",
        (nuevo_nombre, receta['referencia'])
    )

    nueva_receta_id = cur.lastrowid

    # Copiar ingredientes completos
    ingredientes = cur.execute("""
        SELECT ingrediente_id, tipo, cantidad, unidad, costo_unitario, costo_total
        FROM receta_ingredientes
        WHERE receta_id = ?
    """, (receta_id,)).fetchall()

    for ing in ingredientes:
        cur.execute("""
            INSERT INTO receta_ingredientes (
                receta_id,
                ingrediente_id,
                tipo,
                cantidad,
                unidad,
                costo_unitario,
                costo_total
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        nueva_receta_id,
        ing['ingrediente_id'],
        ing['tipo'],
        ing['cantidad'],
        ing['unidad'],
        ing['costo_unitario'],
        ing['costo_total']
    ))

    # Copiar precio si existe
    precio = cur.execute("""
        SELECT precio_cliente FROM lista_precios
        WHERE receta_id = ?
    """, (receta_id,)).fetchone()

    if precio:
        cur.execute("""
            INSERT INTO lista_precios (receta_id, precio_cliente)
            VALUES (?, ?)
        """, (nueva_receta_id, precio['precio_cliente']))

    conn.commit()
    conn.close()

    return redirect(url_for('modificar_receta', id=nueva_receta_id))

# Agregar ingrediente a receta
@app.route('/agregar_ingrediente_receta/<int:receta_id>', methods=['POST'])
@login_required
def agregar_ingrediente_receta(receta_id):
    create_backup()
    ingrediente_id = int(request.form['ingrediente_id'])
    cantidad = float(request.form['cantidad'])
    
    with get_conn() as conn:
        # Traer tipo, unidad y costo_unitario del ingrediente original
        fila = conn.execute('SELECT tipo, unidad, costo_unitario FROM ingredientes WHERE id = ?', (ingrediente_id,)).fetchone()
        tipo = fila['tipo'] if fila else ''
        unidad = fila['unidad'] if fila else ''
        costo_unitario = fila['costo_unitario'] if fila else 0

        costo_total = cantidad * costo_unitario

        conn.execute('''
            INSERT INTO receta_ingredientes (receta_id, ingrediente_id, tipo, cantidad, unidad, costo_unitario, costo_total)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (receta_id, ingrediente_id, tipo, cantidad, unidad, costo_unitario, costo_total))
        conn.commit()

    return redirect(url_for('modificar_receta', id=receta_id))

# Eliminar ingrediente de receta
@app.route('/eliminar_ingrediente_receta/<int:ri_id>/<int:receta_id>')
@login_required
def eliminar_ingrediente_receta(ri_id, receta_id):
    create_backup()
    with get_conn() as conn:
        conn.execute('DELETE FROM receta_ingredientes WHERE id = ?', (ri_id,))
        conn.commit()
    return redirect(url_for('modificar_receta', id=receta_id))

# Registrar el blueprint de backups
app.register_blueprint(bp_backups)

if __name__ == '__main__':
    app.run(debug=True)
