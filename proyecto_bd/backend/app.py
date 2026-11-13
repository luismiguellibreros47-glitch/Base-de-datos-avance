from flask import Flask
from flask_cors import CORS
from routes.productos import productos_bp
from routes.terceros import terceros_bp
from routes.pedidos import pedidos_bp
from routes.ventas import ventas_bp
from routes.usuarios import usuarios_bp

app = Flask(__name__)
app.url_map.strict_slashes = False
CORS(app)

app.register_blueprint(productos_bp)
app.register_blueprint(terceros_bp)
app.register_blueprint(pedidos_bp)
app.register_blueprint(ventas_bp)
app.register_blueprint(usuarios_bp)

@app.route("/", methods=["GET"])
def inicio():
    return {"mensaje": "API ERP activa"}

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
