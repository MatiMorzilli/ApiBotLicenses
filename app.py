import os
import sqlite3
import datetime
from flask import Flask, request, jsonify, g
from dotenv import load_dotenv

# Cargar variables de entorno desde el archivo .env
load_dotenv()

DATABASE = 'licenses.db'
# Obtener la API key administrativa de la variable de entorno (o usar un valor por defecto)
ADMIN_API_KEY = os.environ.get("ADMIN_API_KEY", "clave_secreta_por_defecto")

def get_db():
    """Obtiene una conexión a la base de datos y la almacena en 'g' para la solicitud actual."""
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row  # Permite acceder a columnas por nombre
    return db

def init_db():
    """
    Crea la base de datos y la tabla 'licenses' si no existen.
    Inserta registros de ejemplo si la tabla está vacía.
    """
    db = sqlite3.connect(DATABASE)
    with db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS licenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                usuario TEXT NOT NULL,
                license_key TEXT NOT NULL UNIQUE,
                subscription_date TEXT NOT NULL,
                expiration_date TEXT,
                active INTEGER DEFAULT 1
            );
        """)
        cur = db.execute("SELECT COUNT(*) as count FROM licenses")
        count = cur.fetchone()["count"]
        if count == 0:
            # Insertar licencias de ejemplo
            db.execute("""
                INSERT INTO licenses (usuario, license_key, subscription_date, expiration_date, active)
                VALUES (?, ?, ?, ?, ?)
            """, ("usuario1", "LICENSE-1234-5678", "2023-03-03", "2023-12-31", 1))
            db.execute("""
                INSERT INTO licenses (usuario, license_key, subscription_date, expiration_date, active)
                VALUES (?, ?, ?, ?, ?)
            """, ("usuario2", "LICENSE-9876-5432", "2023-01-01", "2023-02-01", 1))
    db.close()

def check_api_key():
    """
    Verifica que en la cabecera se envíe la API key correcta (usando la cabecera 'X-API-KEY').
    Retorna True si es válida, False en caso contrario.
    """
    api_key = request.headers.get("X-API-KEY")
    return api_key == ADMIN_API_KEY

app = Flask(__name__)

@app.teardown_appcontext
def close_connection(exception):
    """Cierra la conexión a la base de datos al finalizar la solicitud."""
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

@app.route("/api/validate", methods=["POST"])
def validate_license():
    """
    Endpoint público para validar una licencia.
    Recibe un JSON con la clave "license" y verifica:
      - Que la licencia exista en la base de datos.
      - Que esté activa.
      - Que, si tiene fecha de expiración, aún no esté expirada.
    """
    data = request.get_json()
    if not data or "license" not in data:
        return jsonify({"valid": False, "message": "No se proporcionó la licencia"}), 400

    license_key = data["license"]
    db = get_db()
    cur = db.execute("SELECT * FROM licenses WHERE license_key = ? AND active = 1", (license_key,))
    row = cur.fetchone()
    
    if row is None:
        return jsonify({"valid": False, "message": "Licencia inválida o desactivada"}), 200

    expiration = row["expiration_date"]
    if expiration:
        try:
            exp_date = datetime.datetime.strptime(expiration, "%Y-%m-%d").date()
            if datetime.date.today() > exp_date:
                return jsonify({"valid": False, "message": "Licencia expirada"}), 200
        except Exception as e:
            return jsonify({"valid": False, "message": "Error en el formato de fecha"}), 500

    return jsonify({
        "valid": True, 
        "message": "Licencia válida", 
        "usuario": row["usuario"],
        "subscription_date": row["subscription_date"],
        "expiration_date": expiration
    }), 200

@app.route("/api/admin/add_or_update_license", methods=["POST"])
def add_or_update_license():
    """
    Endpoint administrativo para agregar o actualizar una licencia.
    Requiere la cabecera 'X-API-KEY' con la API key correcta.
    
    Body de ejemplo:
    {
        "usuario": "usuario_nuevo",
        "license_key": "LICENSE-0000-1111",
        "subscription_date": "2023-03-03",
        "expiration_date": "2023-12-31",
        "active": 1
    }
    """
    if not check_api_key():
        return jsonify({"success": False, "message": "No autorizado"}), 401

    data = request.get_json()
    required = ["usuario", "license_key", "subscription_date", "expiration_date", "active"]
    if not data or any(field not in data for field in required):
        return jsonify({"success": False, "message": "Faltan campos obligatorios"}), 400

    db = get_db()
    try:
        db.execute("""
            INSERT INTO licenses (usuario, license_key, subscription_date, expiration_date, active)
            VALUES (?, ?, ?, ?, ?)
        """, (
            data["usuario"],
            data["license_key"],
            data["subscription_date"],
            data["expiration_date"],
            data["active"]
        ))
        db.commit()
        return jsonify({"success": True, "message": "Licencia agregada"}), 200
    except sqlite3.IntegrityError:
        db.execute("""
            UPDATE licenses
            SET usuario = ?, subscription_date = ?, expiration_date = ?, active = ?
            WHERE license_key = ?
        """, (
            data["usuario"],
            data["subscription_date"],
            data["expiration_date"],
            data["active"],
            data["license_key"]
        ))
        db.commit()
        return jsonify({"success": True, "message": "Licencia actualizada"}), 200

@app.route("/api/admin/deactivate_license", methods=["POST"])
def deactivate_license():
    """
    Endpoint administrativo para desactivar una licencia.
    Requiere la cabecera 'X-API-KEY' con la API key correcta.
    
    Body de ejemplo:
    {
        "license_key": "LICENSE-0000-1111"
    }
    """
    if not check_api_key():
        return jsonify({"success": False, "message": "No autorizado"}), 401

    data = request.get_json()
    if not data or "license_key" not in data:
        return jsonify({"success": False, "message": "Falta el campo license_key"}), 400

    db = get_db()
    db.execute("UPDATE licenses SET active = 0 WHERE license_key = ?", (data["license_key"],))
    db.commit()
    return jsonify({"success": True, "message": "Licencia desactivada"}), 200

@app.route("/api/admin/list_licenses", methods=["GET"])
def list_licenses():
    """
    Endpoint administrativo para listar todas las licencias.
    Requiere la cabecera 'X-API-KEY' con la API key correcta.
    No requiere body, es un GET.
    """
    if not check_api_key():
        return jsonify({"success": False, "message": "No autorizado"}), 401

    db = get_db()
    cur = db.execute("SELECT * FROM licenses")
    rows = cur.fetchall()
    licenses = []
    for row in rows:
        licenses.append({
            "id": row["id"],
            "usuario": row["usuario"],
            "license_key": row["license_key"],
            "subscription_date": row["subscription_date"],
            "expiration_date": row["expiration_date"],
            "active": row["active"]
        })
    return jsonify({"success": True, "licenses": licenses}), 200

if __name__ == "__main__":
    if not os.path.exists(DATABASE):
        init_db()
    # Usa el puerto definido en la variable de entorno PORT o el 5000 por defecto.
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
