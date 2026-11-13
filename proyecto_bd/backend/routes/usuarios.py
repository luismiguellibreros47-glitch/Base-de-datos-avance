from flask import Blueprint, jsonify
import mysql.connector
from config import get_db_connection

usuarios_bp = Blueprint("usuarios", __name__, url_prefix="/api/usuarios")

@usuarios_bp.route("/", methods=["GET"])
def obtener_usuarios():
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT id_usuario, nombre, correo, roles_id_rol FROM usuarios WHERE estado = 1 ORDER BY id_usuario")
        return jsonify(cursor.fetchall()), 200
    except mysql.connector.Error as err:
        return jsonify({"error": err.msg, "sqlstate": err.sqlstate, "codigo": err.errno}), 500
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
