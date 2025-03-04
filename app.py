from flask import Flask, request, jsonify

app = Flask(__name__)

# Lista simulada de licencias válidas
# En producción podrías usar una base de datos o un sistema más complejo
VALID_LICENSES = [
    "LICENSE-1234-5678",
    "LICENSE-9876-5432"
]

@app.route("/api/validate", methods=["POST"])
def validate_license():
    """
    Endpoint para validar una licencia.
    Espera un JSON con la clave 'license'.
    Retorna { valid: true/false, message: '...' }
    """
    data = request.get_json()
    if not data or "license" not in data:
        return jsonify({"valid": False, "message": "No se proporcionó la licencia"}), 400

    license_key = data["license"]
    if license_key in VALID_LICENSES:
        return jsonify({"valid": True, "message": "Licencia válida"}), 200
    else:
        return jsonify({"valid": False, "message": "Licencia inválida o desactivada"}), 200

if __name__ == "__main__":
    # Para probar en local:
    # python app.py
    # Se iniciará en http://localhost:5000
    app.run(host="0.0.0.0", port=5001)

