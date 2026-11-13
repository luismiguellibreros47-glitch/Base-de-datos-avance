from flask import Blueprint, jsonify, request
import mysql.connector
from config import get_db_connection

terceros_bp = Blueprint("terceros", __name__, url_prefix="/api/terceros")

@terceros_bp.route("/", methods=["GET"])
def obtener_terceros():
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        todos = request.args.get("todos") == "1"
        if todos:
            cursor.execute("SELECT id_tercero, nombre, correo, contacto, estado FROM terceros ORDER BY id_tercero DESC")
        else:
            cursor.execute("SELECT id_tercero, nombre, correo, contacto, estado FROM terceros WHERE estado = 1 ORDER BY id_tercero DESC")
        return jsonify(cursor.fetchall()), 200
    except mysql.connector.Error as err:
        return jsonify({"error": err.msg, "sqlstate": err.sqlstate, "codigo": err.errno}), 500
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@terceros_bp.route("/", methods=["POST"])
def crear_tercero():
    datos = request.json
    if not isinstance(datos, dict) or not str(datos.get("nombre", "")).strip() or not str(datos.get("contacto", "")).strip():
        return jsonify({"error": "Los campos 'nombre' y 'contacto' son obligatorios."}), 400
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        nombre = str(datos["nombre"]).strip()
        contacto = str(datos["contacto"]).strip()
        correo = str(datos.get("correo") or "").strip() or None
        sql = "INSERT INTO terceros (nombre, correo, contacto) VALUES (%s, %s, %s)"
        cursor.execute(sql, (nombre, correo, contacto))
        conn.commit()
        return jsonify({"mensaje": "Tercero creado con éxito", "id_tercero": cursor.lastrowid}), 201
    except mysql.connector.Error as err:
        if conn:
            conn.rollback()
        return jsonify({"error": err.msg, "sqlstate": err.sqlstate, "codigo": err.errno}), 400
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@terceros_bp.route("/<int:id_tercero>", methods=["PUT"])
def actualizar_tercero(id_tercero):
    """
    Trigger disparado en MySQL: terceros_BEFORE_UPDATE.
    Tarea por debajo: Si se intenta inactivar el tercero (estado = 0), cuenta si tiene ventas
    asociadas en la tabla ventas y bloquea la inactivación si existe al menos una.
    Error / SQLSTATE: SQLSTATE '45000' con mensaje 'Acción denegada: No se puede eliminar el cliente porque tiene ventas registradas en el sistema.'.
    """
    datos = request.json
    if not isinstance(datos, dict) or not str(datos.get("nombre", "")).strip() or not str(datos.get("contacto", "")).strip():
        return jsonify({"error": "Los campos 'nombre' y 'contacto' son obligatorios."}), 400
    conn = None
    cursor = None
    try:
        estado = int(datos.get("estado", 1))
        if estado not in (0, 1):
            return jsonify({"error": "Estado inválido."}), 400
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        nombre = str(datos["nombre"]).strip()
        contacto = str(datos["contacto"]).strip()
        correo = str(datos.get("correo") or "").strip() or None
        sql = "UPDATE terceros SET nombre = %s, correo = %s, contacto = %s, estado = %s WHERE id_tercero = %s"
        cursor.execute(sql, (nombre, correo, contacto, estado, id_tercero))
        conn.commit()
        if cursor.rowcount == 0:
            return jsonify({"error": "Tercero no encontrado o sin cambios."}), 404
        return jsonify({"mensaje": f"Tercero {id_tercero} actualizado correctamente."}), 200
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

@terceros_bp.route("/<int:id_tercero>", methods=["DELETE"])
def eliminar_tercero(id_tercero):
    """
    Trigger disparado en MySQL: terceros_BEFORE_UPDATE.
    Tarea por debajo: Al actualizar estado = 0, valida en la tabla ventas si el tercero tiene
    ventas registradas e impide el borrado lógico en caso afirmativo.
    Error / SQLSTATE: SQLSTATE '45000' con mensaje 'Acción denegada: No se puede eliminar el cliente porque tiene ventas registradas en el sistema.'.
    """
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("UPDATE terceros SET estado = 0 WHERE id_tercero = %s", (id_tercero,))
        conn.commit()
        if cursor.rowcount == 0:
            return jsonify({"error": "Tercero no encontrado o ya estaba inactivo."}), 404
        return jsonify({"mensaje": f"Tercero {id_tercero} inactivado correctamente."}), 200
    except mysql.connector.Error as err:
        if conn:
            conn.rollback()
        return jsonify({"error": err.msg, "sqlstate": err.sqlstate, "codigo": err.errno}), 400
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
