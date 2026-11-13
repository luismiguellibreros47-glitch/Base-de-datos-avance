from flask import Blueprint, jsonify, request
import mysql.connector
from config import get_db_connection

productos_bp = Blueprint("productos", __name__, url_prefix="/api/productos")

@productos_bp.route("/", methods=["GET"])
def obtener_productos():
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        todos = request.args.get("todos") == "1"
        if todos:
            cursor.execute(
                "SELECT id_producto, nombre, cantidad_stock, nivel_minimo, precioCompra, precioVenta, estado, tarifa_iva FROM productos ORDER BY id_producto DESC"
            )
        else:
            cursor.execute(
                "SELECT id_producto, nombre, cantidad_stock, nivel_minimo, precioCompra, precioVenta, estado, tarifa_iva FROM productos WHERE estado = 1 ORDER BY id_producto DESC"
            )
        return jsonify(cursor.fetchall()), 200
    except mysql.connector.Error as err:
        return jsonify({"error": err.msg, "sqlstate": err.sqlstate, "codigo": err.errno}), 500
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@productos_bp.route("/", methods=["POST"])
def crear_producto():
    datos = request.json
    if not isinstance(datos, dict) or not str(datos.get("nombre", "")).strip():
        return jsonify({"error": "El campo 'nombre' es obligatorio."}), 400
    conn = None
    cursor = None
    try:
        nombre = str(datos["nombre"]).strip()
        stock = int(datos.get("cantidad_stock", 0))
        minimo = int(datos.get("nivel_minimo", 5))
        compra = float(datos.get("precioCompra", 0))
        venta = float(datos.get("precioVenta", 0))
        iva = float(datos.get("tarifa_iva", 0.19))
        if stock < 0 or minimo < 0 or compra < 0 or venta < 0 or iva < 0 or iva > 1:
            return jsonify({"error": "Los valores numéricos del producto no pueden ser negativos ni inválidos."}), 400

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        sql = """
            INSERT INTO productos (nombre, cantidad_stock, nivel_minimo, precioCompra, precioVenta, tarifa_iva)
            VALUES (%s, %s, %s, %s, %s, %s)
        """
        cursor.execute(sql, (nombre, stock, minimo, compra, venta, iva))
        conn.commit()
        return jsonify({"mensaje": "Producto creado con éxito", "id_producto": cursor.lastrowid}), 201
    except mysql.connector.Error as err:
        if conn:
            conn.rollback()
        return jsonify({"error": err.msg, "sqlstate": err.sqlstate, "codigo": err.errno}), 400
    except (TypeError, ValueError) as err:
        return jsonify({"error": str(err)}), 400
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@productos_bp.route("/<int:id_producto>", methods=["PUT"])
def actualizar_producto(id_producto):
    """
    Trigger disparado en MySQL: productos_BEFORE_UPDATE.
    Tarea por debajo: Si se intenta cambiar estado de 1 a 0, valida que el producto no tenga stock
    disponible ni registros en detalle_pedido. Por seguridad contable no permite alterar
    cantidad_stock ni precioCompra directamente.
    Error / SQLSTATE: SQLSTATE '45000' con mensaje 'Operación denegada: El producto no se puede inactivar porque aún tiene stock.'
    o 'Operación denegada: El producto está amarrado a un pedido existente.'.
    """
    datos = request.json
    if not isinstance(datos, dict) or not str(datos.get("nombre", "")).strip():
        return jsonify({"error": "El campo 'nombre' es obligatorio."}), 400
    conn = None
    cursor = None
    try:
        nombre = str(datos["nombre"]).strip()
        minimo = int(datos.get("nivel_minimo", 5))
        venta = float(datos.get("precioVenta", 0))
        iva = float(datos.get("tarifa_iva", 0.19))
        estado = int(datos.get("estado", 1))
        if minimo < 0 or venta < 0 or iva < 0 or iva > 1 or estado not in (0, 1):
            return jsonify({"error": "Datos numéricos o estado inválidos."}), 400

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        sql = """
            UPDATE productos
            SET nombre = %s, nivel_minimo = %s, precioVenta = %s, tarifa_iva = %s, estado = %s
            WHERE id_producto = %s
        """
        cursor.execute(sql, (nombre, minimo, venta, iva, estado, id_producto))
        conn.commit()
        if cursor.rowcount == 0:
            return jsonify({"error": "Producto no encontrado o sin cambios."}), 404
        return jsonify({"mensaje": f"Producto {id_producto} actualizado correctamente."}), 200
    except mysql.connector.Error as err:
        if conn:
            conn.rollback()
        return jsonify({"error": err.msg, "sqlstate": err.sqlstate, "codigo": err.errno}), 400
    except (TypeError, ValueError) as err:
        return jsonify({"error": str(err)}), 400
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@productos_bp.route("/<int:id_producto>", methods=["DELETE"])
def eliminar_producto(id_producto):
    """
    Trigger disparado en MySQL: productos_BEFORE_UPDATE.
    Tarea por debajo: Al intentar poner estado = 0, verifica que cantidad_stock sea 0 y que el
    producto no esté amarrado a ningún pedido en detalle_pedido.
    Error / SQLSTATE: SQLSTATE '45000' con mensaje 'Operación denegada: El producto no se puede inactivar porque aún tiene stock.'
    o 'Operación denegada: El producto está amarrado a un pedido existente.'.
    """
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("UPDATE productos SET estado = 0 WHERE id_producto = %s", (id_producto,))
        conn.commit()
        if cursor.rowcount == 0:
            return jsonify({"error": "Producto no encontrado o ya estaba inactivo."}), 404
        return jsonify({"mensaje": f"Producto {id_producto} inactivado correctamente."}), 200
    except mysql.connector.Error as err:
        if conn:
            conn.rollback()
        return jsonify({"error": err.msg, "sqlstate": err.sqlstate, "codigo": err.errno}), 400
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
