from flask import Blueprint, jsonify, request
import mysql.connector
from config import get_db_connection

ventas_bp = Blueprint("ventas", __name__, url_prefix="/api/ventas")

ESTADOS_VENTA_CREACION = ("Pendiente", "Pagado", "Enviado", "Por Pagar")
ESTADOS_VENTA_VALIDOS = ("Pendiente", "Pagado", "Anulado", "Enviado", "Por Pagar")

@ventas_bp.route("/", methods=["GET"])
def obtener_ventas():
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        sql = """
            SELECT v.id_venta, v.fecha_venta, v.total_venta, v.estado_venta,
                   v.usuarios_id_usuario, v.tercero_id_tercero,
                   t.nombre AS nombre_tercero, u.nombre AS nombre_usuario
            FROM ventas v
            INNER JOIN terceros t ON v.tercero_id_tercero = t.id_tercero
            INNER JOIN usuarios u ON v.usuarios_id_usuario = u.id_usuario
            ORDER BY v.id_venta DESC
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

@ventas_bp.route("/<int:id_venta>", methods=["GET"])
def obtener_venta_completa(id_venta):
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        sql_cabecera = """
            SELECT v.id_venta, v.fecha_venta, v.total_venta, v.estado_venta,
                   v.usuarios_id_usuario, v.tercero_id_tercero,
                   t.nombre AS nombre_tercero, u.nombre AS nombre_usuario
            FROM ventas v
            INNER JOIN terceros t ON v.tercero_id_tercero = t.id_tercero
            INNER JOIN usuarios u ON v.usuarios_id_usuario = u.id_usuario
            WHERE v.id_venta = %s
        """
        cursor.execute(sql_cabecera, (id_venta,))
        venta = cursor.fetchone()
        if not venta:
            return jsonify({"error": f"Venta {id_venta} no encontrada."}), 404

        sql_detalles = """
            SELECT dv.id_detalle_venta, dv.id_producto, p.nombre AS nombre_producto,
                   dv.cantidad, dv.precioUnitario, dv.subtotal, dv.porcentaje_iva, dv.total_venta
            FROM detalleventa dv
            INNER JOIN productos p ON dv.id_producto = p.id_producto
            WHERE dv.id_venta = %s
        """
        cursor.execute(sql_detalles, (id_venta,))
        venta["detalles"] = cursor.fetchall()
        return jsonify(venta), 200
    except mysql.connector.Error as err:
        return jsonify({"error": err.msg, "sqlstate": err.sqlstate, "codigo": err.errno}), 500
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@ventas_bp.route("/", methods=["POST"])
def crear_venta():
    """
    Trigger disparado en MySQL: detalleventa_BEFORE_INSERT y detalleventa_AFTER_INSERT.
    Tarea por debajo: BEFORE INSERT valida que el producto esté activo, tenga ingresos en
    detalle_pedido, cantidad > 0 y stock suficiente. AFTER INSERT descuenta cantidad_stock
    en productos y suma el subtotal con IVA a total_venta en ventas.
    Error / SQLSTATE: SQLSTATE '45000' con mensaje 'El producto se encuentra inactivo' o
    'Cantidad menor a cero, por favor ingrese un valor positivo.'.
    """
    datos = request.json
    if not isinstance(datos, dict):
        return jsonify({"error": "Cuerpo JSON inválido."}), 400

    id_tercero = datos.get("tercero_id_tercero") or datos.get("id_tercero")
    id_usuario = datos.get("usuarios_id_usuario") or datos.get("id_usuario")
    estado = datos.get("estado_venta")
    detalles = datos.get("detalles")

    if estado is None:
        estado = "Pendiente"
    if not isinstance(estado, str) or estado not in ESTADOS_VENTA_CREACION:
        return jsonify({"error": "Estado de venta inválido. Valores permitidos: Pendiente, Pagado, Enviado, Por Pagar."}), 400

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

        sql_venta = "INSERT INTO ventas (usuarios_id_usuario, tercero_id_tercero, estado_venta) VALUES (%s, %s, %s)"
        cursor.execute(sql_venta, (int(id_usuario), int(id_tercero), estado))
        id_venta = cursor.lastrowid

        sql_detalle = """
            INSERT INTO detalleventa (id_venta, id_producto, cantidad, precioUnitario, porcentaje_iva)
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

            cursor.execute("SELECT precioCompra, estado FROM productos WHERE id_producto = %s", (id_producto,))
            prod = cursor.fetchone()
            if not prod or prod["estado"] != 1:
                raise ValueError(f"El producto {id_producto} no existe o está inactivo.")
            if precio < float(prod["precioCompra"]):
                raise ValueError("El precio de venta no puede ser menor al precio de compra.")

            cursor.execute(sql_detalle, (id_venta, id_producto, cantidad, precio, iva))

        conn.commit()
        return jsonify({"mensaje": "Venta registrada con éxito.", "id_venta": id_venta}), 201
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

@ventas_bp.route("/<int:id_venta>/estado", methods=["PUT"])
def actualizar_estado_venta(id_venta):
    """
    Trigger disparado en MySQL: ventas_BEFORE_UPDATE y ventas_AFTER_UPDATE.
    Tarea por debajo: BEFORE UPDATE impide modificar una venta que ya está en estado 'Anulado'.
    AFTER UPDATE devuelve automáticamente al stock de productos las cantidades de detalleventa
    si el nuevo estado pasa a ser 'Anulado'.
    Error / SQLSTATE: SQLSTATE '45000' con mensaje 'Error: Una venta anulada no puede volver a cambiarse de estado por seguridad contable.'.
    """
    datos = request.json
    estado = datos.get("estado_venta") if isinstance(datos, dict) else None
    if not isinstance(estado, str) or estado not in ESTADOS_VENTA_VALIDOS:
        return jsonify({"error": "Estado de venta inválido."}), 400
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("UPDATE ventas SET estado_venta = %s WHERE id_venta = %s", (estado, id_venta))
        conn.commit()
        if cursor.rowcount == 0:
            return jsonify({"error": "Venta no encontrada o sin cambios."}), 404
        return jsonify({"mensaje": f"Estado de la venta {id_venta} actualizado a {estado}."}), 200
    except mysql.connector.Error as err:
        if conn:
            conn.rollback()
        return jsonify({"error": err.msg, "sqlstate": err.sqlstate, "codigo": err.errno}), 400
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@ventas_bp.route("/<int:id_venta>/anular", methods=["PUT"])
def anular_venta(id_venta):
    """
    Trigger disparado en MySQL: ventas_BEFORE_UPDATE y ventas_AFTER_UPDATE.
    Tarea por debajo: BEFORE UPDATE valida que la venta no haya sido anulada previamente para
    preservar la historia contable. AFTER UPDATE recorre detalleventa del id_venta actualizado
    y suma nuevamente las cantidades vendidas a productos.cantidad_stock sin lógica en Python.
    Error / SQLSTATE: SQLSTATE '45000' con mensaje 'Error: Una venta anulada no puede volver a cambiarse de estado por seguridad contable.'.
    """
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("UPDATE ventas SET estado_venta = 'Anulado' WHERE id_venta = %s", (id_venta,))
        conn.commit()
        if cursor.rowcount == 0:
            return jsonify({"error": f"Venta {id_venta} no encontrada."}), 404
        return jsonify({"mensaje": f"Venta {id_venta} anulada correctamente."}), 200
    except mysql.connector.Error as err:
        if conn:
            conn.rollback()
        return jsonify({"error": err.msg, "sqlstate": err.sqlstate, "codigo": err.errno}), 400
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
