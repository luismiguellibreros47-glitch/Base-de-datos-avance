from flask import Blueprint, jsonify, request
import mysql.connector
from config import get_db_connection

pedidos_bp = Blueprint("pedidos", __name__, url_prefix="/api/pedidos")

ESTADOS_PEDIDO_CREACION = ("Pendiente", "Pagado", "Enviado", "Por Pagar")
ESTADOS_PEDIDO_VALIDOS = ("Pendiente", "Pagado", "Anulado", "Enviado", "Por Pagar")

@pedidos_bp.route("/", methods=["GET"])
def obtener_pedidos():
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        sql = """
            SELECT p.id_pedido, p.fecha_pedido, p.total_pedido, p.estado_pedido,
                   p.usuarios_id_usuario, p.tercero_id_tercero,
                   t.nombre AS nombre_tercero, u.nombre AS nombre_usuario
            FROM pedidos p
            INNER JOIN terceros t ON p.tercero_id_tercero = t.id_tercero
            INNER JOIN usuarios u ON p.usuarios_id_usuario = u.id_usuario
            ORDER BY p.id_pedido DESC
        """
        cursor.execute(sql)
        return jsonify(cursor.fetchall()), 200
    except mysql.connector.Error as err:
        return jsonify({"error": err.msg, "sqlstate": err.sqlstate, "codigo": err.errno}), 500
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@pedidos_bp.route("/<int:id_pedido>", methods=["GET"])
def obtener_pedido_completo(id_pedido):
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        sql_cabecera = """
            SELECT p.id_pedido, p.fecha_pedido, p.total_pedido, p.estado_pedido,
                   p.usuarios_id_usuario, p.tercero_id_tercero,
                   t.nombre AS nombre_tercero, u.nombre AS nombre_usuario
            FROM pedidos p
            INNER JOIN terceros t ON p.tercero_id_tercero = t.id_tercero
            INNER JOIN usuarios u ON p.usuarios_id_usuario = u.id_usuario
            WHERE p.id_pedido = %s
        """
        cursor.execute(sql_cabecera, (id_pedido,))
        pedido = cursor.fetchone()
        if not pedido:
            return jsonify({"error": f"Pedido {id_pedido} no encontrado."}), 404

        sql_detalles = """
            SELECT dp.id_detalle_pedido, dp.id_producto, pr.nombre AS nombre_producto,
                   dp.cantidad, dp.precioUnitario, dp.subtotal, dp.porcentaje_iva, dp.total_producto
            FROM detalle_pedido dp
            INNER JOIN productos pr ON dp.id_producto = pr.id_producto
            WHERE dp.id_pedido = %s
        """
        cursor.execute(sql_detalles, (id_pedido,))
        pedido["detalles"] = cursor.fetchall()
        return jsonify(pedido), 200
    except mysql.connector.Error as err:
        return jsonify({"error": err.msg, "sqlstate": err.sqlstate, "codigo": err.errno}), 500
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@pedidos_bp.route("/", methods=["POST"])
def crear_pedido():
    """
    Trigger disparado en MySQL: detalle_pedido_BEFORE_INSERT y detalle_pedido_AFTER_INSERT.
    Tarea por debajo: BEFORE INSERT valida que el producto esté activo y la cantidad sea mayor a 0.
    AFTER INSERT suma cantidad al stock en productos, actualiza precioCompra y suma al total_pedido.
    Error / SQLSTATE: SQLSTATE '45000' con mensaje 'El producto se encuentra inactivo' o
    'Cantidad menor a cero, por favor ingrese un valor positivo.'.
    """
    datos = request.json
    if not isinstance(datos, dict):
        return jsonify({"error": "Cuerpo JSON inválido."}), 400

    id_tercero = datos.get("tercero_id_tercero") or datos.get("id_tercero")
    id_usuario = datos.get("usuarios_id_usuario") or datos.get("id_usuario")
    estado = datos.get("estado_pedido")
    detalles = datos.get("detalles")

    if estado is None:
        estado = "Pendiente"
    if not isinstance(estado, str) or estado not in ESTADOS_PEDIDO_CREACION:
        return jsonify({"error": "Estado de pedido inválido. Valores permitidos: Pendiente, Pagado, Enviado, Por Pagar."}), 400

    if not id_tercero or not id_usuario or not isinstance(detalles, list) or len(detalles) == 0:
        return jsonify({"error": "Debe enviar tercero, usuario y al menos un detalle."}), 400

    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("SELECT id_tercero FROM terceros WHERE id_tercero = %s AND estado = 1", (int(id_tercero),))
        if not cursor.fetchone():
            return jsonify({"error": "El tercero seleccionado no existe o está inactivo."}), 400

        cursor.execute("SELECT id_usuario FROM usuarios WHERE id_usuario = %s AND estado = 1", (int(id_usuario),))
        if not cursor.fetchone():
            return jsonify({"error": "El usuario seleccionado no existe o está inactivo."}), 400

        sql_pedido = "INSERT INTO pedidos (usuarios_id_usuario, tercero_id_tercero, estado_pedido) VALUES (%s, %s, %s)"
        cursor.execute(sql_pedido, (int(id_usuario), int(id_tercero), estado))
        id_pedido = cursor.lastrowid

        sql_detalle = """
            INSERT INTO detalle_pedido (id_pedido, id_producto, cantidad, precioUnitario, porcentaje_iva)
            VALUES (%s, %s, %s, %s, %s)
        """
        for item in detalles:
            if not isinstance(item, dict):
                raise ValueError("Detalle de producto inválido.")
            id_producto = int(item["id_producto"])
            cantidad = int(item["cantidad"])
            precio = float(item["precioUnitario"])
            iva = float(item.get("porcentaje_iva", 0.19))
            if cantidad <= 0 or precio <= 0 or iva < 0 or iva > 1:
                raise ValueError("Cantidad, precio unitario e IVA deben ser valores positivos válidos.")

            cursor.execute(sql_detalle, (id_pedido, id_producto, cantidad, precio, iva))

        conn.commit()
        return jsonify({"mensaje": "Pedido registrado con éxito.", "id_pedido": id_pedido}), 201
    except mysql.connector.Error as err:
        if conn:
            conn.rollback()
        return jsonify({"error": err.msg, "sqlstate": err.sqlstate, "codigo": err.errno}), 400
    except (KeyError, TypeError, ValueError) as err:
        if conn:
            conn.rollback()
        return jsonify({"error": str(err)}), 400
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@pedidos_bp.route("/<int:id_pedido>/estado", methods=["PUT"])
def actualizar_estado_pedido(id_pedido):
    """
    Trigger disparado en MySQL: pedidos_BEFORE_UPDATE y pedidos_AFTER_UPDATE.
    Tarea por debajo: BEFORE UPDATE bloquea cualquier cambio de estado si el pedido ya está 'Anulado'.
    AFTER UPDATE ajusta cantidad_stock en productos si el estado pasa a 'Anulado'.
    Error / SQLSTATE: SQLSTATE '45000' con mensaje 'Error: Un pedido anulado no puede volver a cambiarse de estado por seguridad contable.'.
    """
    datos = request.json
    estado = datos.get("estado_pedido") if isinstance(datos, dict) else None
    if not isinstance(estado, str) or estado not in ESTADOS_PEDIDO_VALIDOS:
        return jsonify({"error": "Estado de pedido inválido."}), 400
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("UPDATE pedidos SET estado_pedido = %s WHERE id_pedido = %s", (estado, id_pedido))
        conn.commit()
        if cursor.rowcount == 0:
            return jsonify({"error": "Pedido no encontrado o sin cambios."}), 404
        return jsonify({"mensaje": f"Estado del pedido {id_pedido} actualizado a {estado}."}), 200
    except mysql.connector.Error as err:
        if conn:
            conn.rollback()
        return jsonify({"error": err.msg, "sqlstate": err.sqlstate, "codigo": err.errno}), 400
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
