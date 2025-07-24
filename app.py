from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file, jsonify
import sqlite3
from functools import wraps
from datetime import datetime, timedelta
import pandas as pd
import io
import os
from collections import defaultdict


app = Flask(__name__)
#app.secret_key = os.environ.get('SECRET_KEY', 'esta_es_una_clave_secreta_para_desarrollo') # PRUEBAS LOCALES
#ACCESS_CODE = os.environ.get('ACCESS_CODE', '1111')  # o el código que quieras por defecto - # PRUEBAS LOCALES 
app.secret_key = os.environ.get('SECRET_KEY')  # ideal no usar valor por defecto en producción
ACCESS_CODE = os.environ.get('ACCESS_CODE')  # o el código que quieras por defecto

DB_NAME = 'marchando_base.db'

LOGIN_REQUIRED = False  # Cambiar a True para activar validación

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
 #       if not session.get('logged_in'): # PRUEBAS LOCALES
        if LOGIN_REQUIRED and not session.get('logged_in'):
            return redirect(url_for('login', next=request.path))
        return f(*args, **kwargs)
    return decorated_function

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

def get_conn():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/')
@login_required
def index():
    return render_template('index.html')

# === CLIENTES ===
@app.route('/clientes')
@login_required
def clientes():
    with get_conn() as conn:
        clientes = conn.execute('''
            SELECT c.*, 
                   IFNULL(SUM(p.precio_total), 0) as consumo_total
            FROM clientes c
            LEFT JOIN pedidos p ON c.id = p.cliente_id AND p.estado = 'completo'
            GROUP BY c.id
            ORDER BY c.nombre
        ''').fetchall()
    return render_template('clientes.html', clientes=clientes)

@app.route('/clientes/nuevo', methods=['POST'])
@login_required
def nuevo_cliente():
    data = request.form
    with get_conn() as conn:
        conn.execute('INSERT INTO clientes (nombre, contacto, direccion) VALUES (?, ?, ?)',
                     (data['nombre'], data['contacto'], data['direccion']))
        conn.commit()
    return redirect(url_for('clientes'))

@app.route('/clientes/editar/<int:id>', methods=['POST'])
@login_required
def editar_cliente(id):
    data = request.form
    with get_conn() as conn:
        conn.execute('UPDATE clientes SET nombre=?, contacto=?, direccion=? WHERE id=?',
                     (data['nombre'], data['contacto'], data['direccion'], id))
        conn.commit()
    return redirect(url_for('clientes'))

@app.route('/clientes/eliminar/<int:id>')
@login_required
def eliminar_cliente(id):
    with get_conn() as conn:
        conn.execute('DELETE FROM clientes WHERE id=?', (id,))
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
        producto = conn.execute("""
    SELECT id, producto, tipo, cantidad, unidad, costo_total, referencia
    FROM ingredientes WHERE codigo_barra = ?
""", (codigo,)).fetchone()

    if producto:
        return jsonify({"existe": True, "producto": dict(producto)})
    else:
        return jsonify({"existe": False})

# --- Guardar producto desde modal escáner: inserta o actualiza ---
@app.route('/guardar_producto', methods=['POST'])
@login_required
def guardar_producto():
    data = request.form
    codigo_barra = data.get('codigo_barra', '').strip()
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
    fecha_actual = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    with get_conn() as conn:
        existente = conn.execute('SELECT * FROM ingredientes WHERE codigo_barra = ?', (codigo_barra,)).fetchone()

        if existente:
            # Actualizamos SOLO los campos manejados por modal escáner
            conn.execute('''
    UPDATE ingredientes SET
        producto = ?, cantidad = ?, unidad = ?, costo_total = ?,
        costo_unitario = ?, referencia = ?, tipo = ?, ultima_actualizacion = ?
    WHERE codigo_barra = ?
''', (producto, cantidad, unidad, costo_total, costo_unitario, referencia, tipo, fecha_actual, codigo_barra))

            mensaje = "Producto actualizado correctamente."
        else:
            # Insertamos nuevo con tipo/referencia vacíos
            conn.execute('''
    INSERT INTO ingredientes (producto, tipo, referencia, cantidad, unidad, costo_total, costo_unitario, ultima_actualizacion, codigo_barra)
    VALUES (?, '', '', ?, ?, ?, ?, ?, ?)
''', (producto, referencia, cantidad, unidad, costo_total, costo_unitario, fecha_actual, codigo_barra))

            mensaje = "Producto agregado correctamente."
        conn.commit()

    flash(mensaje, "success")
    return redirect(url_for('modificar_ingredientes'))



@app.route('/ingredientes/editar/<int:id>', methods=['POST'])
@login_required
def editar_ingrediente(id):
    data = request.form
    codigo_barra = data.get('codigo_barra', '').strip()
    producto = data['producto']
    cantidad = float(data['cantidad'])
    unidad = data['unidad']
    referencia = data.get('referencia', '')
    tipo = data.get('tipo', '')
    costo_total = round(float(data['costo_total']), 2)
    costo_unitario = round(costo_total / cantidad, 4) if cantidad else 0

    with get_conn() as conn:
        conn.execute('''
    UPDATE ingredientes SET
        producto = ?,
        cantidad = ?,
        unidad = ?,
        referencia = ?,
        tipo = ?,
        costo_total = ?,
        costo_unitario = ?,
        codigo_barra = ?
    WHERE id = ?
''', (producto, cantidad, unidad, referencia, tipo, costo_total, costo_unitario, codigo_barra, id))

        conn.commit()

    flash('Ingrediente actualizado correctamente')
    return redirect(url_for('modificar_ingredientes'))

@app.route('/ingredientes/eliminar/<int:id>')
@login_required
def eliminar_ingrediente(id):
    with get_conn() as conn:
        conn.execute('DELETE FROM ingredientes WHERE id = ?', (id,))
        conn.commit()
    flash('Ingrediente eliminado correctamente')
    return redirect(url_for('modificar_ingredientes'))

@app.route('/ingredientes/agregar', methods=['POST'])
@login_required
def agregar_ingrediente():
    data = request.form
    producto = data['producto']
    cantidad = float(data['cantidad'])
    unidad = data['unidad']
    referencia = data.get('referencia', '')
    tipo = data.get('tipo', '')
    costo_total = round(float(data['costo_total']), 2)
    costo_unitario = round(costo_total / cantidad, 4) if cantidad else 0

    with get_conn() as conn:
        conn.execute('''
            INSERT INTO ingredientes (producto, cantidad, unidad, referencia, tipo, costo_total, costo_unitario)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (producto, cantidad, unidad, referencia, tipo, costo_total, costo_unitario))
        conn.commit()

    flash('Ingrediente agregado correctamente')
    return redirect(url_for('modificar_ingredientes'))

@app.route('/modificar_ingredientes')
@login_required
def modificar_ingredientes():
    with get_conn() as conn:
        ingredientes_raw = conn.execute('SELECT * FROM ingredientes ORDER BY producto').fetchall()
        
        referencias_raw = conn.execute("SELECT DISTINCT referencia FROM ingredientes WHERE referencia IS NOT NULL AND referencia != ''").fetchall()
        codigos_raw = conn.execute("SELECT DISTINCT codigo_barra FROM ingredientes WHERE codigo_barra IS NOT NULL AND codigo_barra != ''").fetchall()
    
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

@app.route('/exportar_ingredientes')
@login_required
def exportar_ingredientes():
    with get_conn() as conn:
        df = pd.read_sql_query("SELECT producto, cantidad, unidad, costo_total, tipo, referencia FROM ingredientes", conn)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Ingredientes')
    output.seek(0)
    return send_file(output, as_attachment=True, download_name='ingredientes.xlsx',
                     mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

@app.route('/importar_ingredientes', methods=['POST'])
@login_required
def importar_ingredientes():
    archivo = request.files.get('archivo_excel')
    if not archivo:
        return "No se seleccionó archivo", 400
    
    print(f"Archivo recibido: {archivo.filename}")
    
    try:
        df = pd.read_excel(archivo)
    except Exception as e:
        return f"Error al leer Excel: {e}", 400

    # Limpiamos nombres columnas para evitar problemas de espacios o mayúsculas
    df.columns = [col.strip().lower() for col in df.columns]

    print(f"Columnas en Excel: {df.columns.tolist()}")

    with get_conn() as conn:
        for _, row in df.iterrows():
            producto = row.get('producto', '')
            cantidad = float(row.get('cantidad', 0))
            unidad = row.get('unidad', '')
            tipo = row.get('tipo', '')  # Aquí debería venir bien si la columna existe
            costo_total = float(row.get('costo_total', 0))
            costo_unitario = costo_total / cantidad if cantidad else 0

            conn.execute('''
    INSERT INTO ingredientes (producto, cantidad, unidad, tipo, costo_total, costo_unitario)
    VALUES (?, ?, ?, ?, ?, ?)
    ON CONFLICT(producto) DO UPDATE SET
        cantidad=excluded.cantidad,
        unidad=excluded.unidad,
        tipo=excluded.tipo,
        costo_total=excluded.costo_total,
        costo_unitario=excluded.costo_unitario
''', (producto, cantidad, unidad, tipo, costo_total, costo_unitario))

        conn.commit()
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
        nombre = request.form['nombre']
        referencia = request.form.get('referencia', '')
        with get_conn() as conn:
            conn.execute('INSERT INTO recetas (nombre, referencia) VALUES (?, ?)', (nombre, referencia))
            conn.commit()
        return redirect(url_for('ver_recetas'))
    return render_template('nueva_receta.html')

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

# === PRESUPUESTO ===
@app.route("/presupuesto", methods=["GET", "POST"])
@login_required
def presupuesto():
    conn = get_conn()
    if request.method == "POST" and request.is_json:
        data = request.get_json()
        cliente_id = data.get("cliente_id")
        fecha = data.get("fecha")
        recetas = data.get("recetas", [])

        # Insertar cada línea como un pedido pendiente
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
        conn.commit()
        conn.close()
        return jsonify({"status":"ok", "msg":"Presupuesto convertido en pedido correctamente."})

    # GET: mostrar el formulario
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
@app.route('/estadisticas_pedidos', methods=['GET', 'POST'])
@login_required
def estadisticas_pedidos():
    conn = get_conn()
    cur = conn.cursor()

    filtro = request.form.get('filtro', 'todos')

    # Filtro base: solo pedidos finalizados
    base_query = "SELECT * FROM pedidos WHERE estado = 'completo'"
    pedidos = cur.execute(base_query).fetchall()

    # Datos generales
    total_recetas = sum([p['cantidad'] for p in pedidos]) if pedidos else 0
    total_vendido = sum([p['precio_total'] for p in pedidos]) if pedidos else 0

    # Por cliente
    clientes = cur.execute("""
        SELECT c.nombre AS cliente, 
               COUNT(p.id) AS total_pedidos, 
               SUM(p.precio_total) AS total_pagado
        FROM pedidos p
        JOIN clientes c ON p.cliente_id = c.id
        WHERE p.estado = 'completo'
        GROUP BY c.id
        ORDER BY total_pagado DESC
    """).fetchall()

    # Por receta
    recetas = cur.execute("""
        SELECT r.nombre AS receta, 
               SUM(p.cantidad) AS total_vendida
        FROM pedidos p
        JOIN recetas r ON p.receta_id = r.id
        WHERE p.estado = 'completo'
        GROUP BY r.id
        ORDER BY total_vendida DESC
    """).fetchall()

    # Por ingrediente
    ingredientes = cur.execute("""
        SELECT i.producto AS ingrediente,
               i.unidad AS unidad,
               SUM(ri.cantidad * p.cantidad) AS total_usado
        FROM pedidos p
        JOIN receta_ingredientes ri ON p.receta_id = ri.receta_id
        JOIN ingredientes i ON ri.ingrediente_id = i.id
        WHERE p.estado = 'completo'
        GROUP BY i.id
        ORDER BY total_usado DESC
    """).fetchall()

    conn.close()

    return render_template('estadisticas_pedidos.html',
                           total_recetas=total_recetas,
                           total_vendido=total_vendido,
                           filtro=filtro,
                           clientes=clientes,
                           recetas=recetas,
                           ingredientes=ingredientes)



@app.route('/cambiar_estado_pedido', methods=['GET'])
@login_required
def cambiar_estado_pedido_form():
    cliente_buscar = request.args.get('cliente_buscar', '').strip()
    conn = get_conn()
    c = conn.cursor()

    query = '''
        SELECT p.id, p.cliente_id, c.nombre AS cliente, 
               p.receta_id, r.nombre AS receta, 
               p.fecha, p.estado, p.cantidad
        FROM pedidos p
        JOIN clientes c ON p.cliente_id = c.id
        JOIN recetas r ON p.receta_id = r.id
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

    # Agrupar pedidos por cliente y fecha
    pedidos_agrupados = {}
    for p in pedidos:
        clave = (p['cliente_id'], p['fecha'])
        if clave not in pedidos_agrupados:
            pedidos_agrupados[clave] = {
                'cliente_id': p['cliente_id'],
                'cliente': p['cliente'],
                'fecha': p['fecha'],
                'pedidos': [],
            }
        pedidos_agrupados[clave]['pedidos'].append(p)

    pedidos_agrupados = list(pedidos_agrupados.values())

    return render_template('cambiar_estado_pedido.html', pedidos_agrupados=pedidos_agrupados, cliente_buscar=cliente_buscar)

@app.route('/cambiar_estado_pedido', methods=['POST'])
@login_required
def cambiar_estado_pedido():
    accion = request.form.get('accion')
    conn = get_conn()
    cur = conn.cursor()

    # Obtener todos los grupos cliente_id + fecha (para iterar)
    cur.execute('SELECT DISTINCT cliente_id, fecha FROM pedidos')
    grupos = cur.fetchall()

    if accion == 'guardar':
        for grupo in grupos:
            cliente_id = grupo['cliente_id']
            fecha = grupo['fecha']
            campo_estado = f'estado_{cliente_id}_{fecha}'
            nuevo_estado = request.form.get(campo_estado)
            if nuevo_estado in ['pendiente', 'completo']:
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
            campo_eliminar = f'eliminar_{cliente_id}_{fecha}'
            if request.form.get(campo_eliminar) == 'on':
                cur.execute(
                    'DELETE FROM pedidos WHERE cliente_id = ? AND fecha = ?',
                    (cliente_id, fecha)
                )
                eliminados += 1
        conn.commit()
        if eliminados:
            flash(f'Se eliminaron {eliminados} grupo(s) de pedidos.')
        else:
            flash('No se seleccionaron grupos para eliminar.')

    conn.close()
    return redirect(url_for('pedidos'))

@app.route('/finalizar_pedido/<int:cliente_id>/<fecha>/<estado>')
@login_required
def finalizar_pedido(cliente_id, fecha, estado):
    with get_conn() as conn:
        conn.execute('''
            UPDATE pedidos SET estado = 'completo'
            WHERE cliente_id = ? AND fecha = ? AND estado = ?
        ''', (cliente_id, fecha, estado))
        conn.commit()
    flash('Pedido marcado como completo.')
    return redirect(url_for('pedidos'))

@app.route('/pedidos')
@login_required
def pedidos():
    cliente = request.args.get('cliente', '').strip()
    fecha = request.args.get('fecha', '').strip()
    estado = request.args.get('estado', '').strip()

    conn = get_conn()
    c = conn.cursor()

    query = '''
        SELECT p.id, p.fecha, p.estado, p.cliente_id,
               c.nombre AS cliente_nombre,
               r.nombre AS nombre_receta,
               p.cantidad, p.precio_unitario
        FROM pedidos p
        JOIN clientes c ON p.cliente_id = c.id
        JOIN recetas r ON p.receta_id = r.id
        WHERE 1=1
    '''
    params = []

    if cliente:
        # Filtrar por nombre parcial (case insensitive)
        query += ' AND LOWER(c.nombre) LIKE ?'
        params.append(f'%{cliente.lower()}%')

    if fecha:
        query += ' AND p.fecha = ?'
        params.append(fecha)

    if estado:
        query += ' AND p.estado = ?'
        params.append(estado)

    query += ' ORDER BY p.fecha DESC'

    c.execute(query, params)
    pedidos = c.fetchall()

    # Agrupar pedidos por cliente_id y fecha
    pedidos_agrupados = {}
    for p in pedidos:
        clave = (p['cliente_id'], p['fecha'])
        if clave not in pedidos_agrupados:
            pedidos_agrupados[clave] = {
                'cliente_id': p['cliente_id'],
                'cliente_nombre': p['cliente_nombre'],
                'fecha': p['fecha'],
                'estado': p['estado'],
                'pedidos': [],
                'total': 0
            }

        pedidos_agrupados[clave]['pedidos'].append(p)
        costo = p['precio_unitario'] or 0
        cantidad = p['cantidad'] or 0
        pedidos_agrupados[clave]['total'] += costo * cantidad

    pedidos_agrupados = list(pedidos_agrupados.values())

    # Cargar lista de clientes para otros usos (opcional)
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
    pedido = conn.execute('''
        SELECT cliente_id, fecha, estado FROM pedidos
        WHERE cliente_id = ? AND fecha = ? AND estado = ?
        LIMIT 1
    ''', (cliente_id, fecha, estado)).fetchone()

    detalles = conn.execute('''
        SELECT r.nombre AS receta, p.cantidad,
            (SELECT precio_cliente FROM lista_precios WHERE receta_id = r.id) AS precio_cliente
        FROM pedidos p
        JOIN recetas r ON p.receta_id = r.id
        WHERE p.cliente_id = ? AND p.fecha = ? AND p.estado = ?
    ''', (cliente_id, fecha, estado)).fetchall()

    total = sum([d["precio_cliente"] * d["cantidad"] for d in detalles])
    conn.close()

    if not pedido:
        flash('Pedido no encontrado.', 'danger')
        return redirect(url_for('pedidos'))

    return render_template('imprimir_pedido.html',
                           pedido=pedido,
                           detalles=detalles,
                           total_general=total)

@app.route('/lista_precios', methods=['GET', 'POST'])
@login_required
def lista_precios():
    conn = get_conn()
    cur = conn.cursor()

    if request.method == 'POST':
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

            conn.execute('DELETE FROM pedidos WHERE cliente_id = ? AND fecha = ? AND estado = ?',
                         (cliente_id, fecha, estado))

            for r in recetas_pedido:
                conn.execute('''
                    INSERT INTO pedidos (cliente_id, receta_id, fecha, cantidad, precio_unitario, precio_total, estado)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (cliente_id_new, r['receta_id'], fecha_new, r['cantidad'], r['precio_unitario'], r['total'], estado_new))
            conn.commit()

            flash('Pedido actualizado correctamente', 'success')
            return jsonify({'status': 'ok', 'msg': 'Pedido actualizado correctamente'})

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

@app.route('/eliminar_pedido/<int:id>')
@login_required
def eliminar_pedido(id):
    with get_conn() as conn:
        conn.execute('DELETE FROM pedidos WHERE id = ?', (id,))
        conn.commit()
    return redirect(url_for('pedidos'))

@app.route('/marcar_completo/<int:id>')
@login_required
def marcar_completo(id):
    with get_conn() as conn:
        pedido = conn.execute('SELECT cliente_id, fecha FROM pedidos WHERE id = ?', (id,)).fetchone()
        if pedido:
            conn.execute('UPDATE pedidos SET estado = "completo" WHERE cliente_id = ? AND fecha = ?',
                         (pedido['cliente_id'], pedido['fecha']))
            conn.commit()
    return redirect(url_for('pedidos'))

@app.route('/marcar_pendiente/<int:id>')
@login_required
def marcar_pendiente(id):
    with get_conn() as conn:
        pedido = conn.execute('SELECT cliente_id, fecha FROM pedidos WHERE id = ?', (id,)).fetchone()
        if pedido:
            conn.execute('UPDATE pedidos SET estado = "pendiente" WHERE cliente_id = ? AND fecha = ?',
                         (pedido['cliente_id'], pedido['fecha']))
            conn.commit()
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
@app.route('/actualizar_receta/<int:id>', methods=['POST'])
@login_required
def actualizar_receta(id):
    nombre = request.form['nombre']
    referencia = request.form['referencia']
    with get_conn() as conn:
        conn.execute('UPDATE recetas SET nombre = ?, referencia = ? WHERE id = ?', (nombre, referencia, id))
        conn.commit()
    return redirect(url_for('ver_recetas'))

# Agregar ingrediente a receta
@app.route('/agregar_ingrediente_receta/<int:receta_id>', methods=['POST'])
@login_required
def agregar_ingrediente_receta(receta_id):
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
    with get_conn() as conn:
        conn.execute('DELETE FROM receta_ingredientes WHERE id = ?', (ri_id,))
        conn.commit()
    return redirect(url_for('modificar_receta', id=receta_id))

if __name__ == '__main__':
    app.run(debug=True)
