"""
Python HTTP API: CV (/classify) и RAG retrieval (/rag/context) для Go-сервера.
"""

import hmac
import os
import sys

_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, _root)

from dotenv import load_dotenv
from flask import Flask, jsonify, request
from flask_cors import CORS

load_dotenv(os.path.join(_root, ".env"))

from cv.registry import get_classifier_for_crop
from rag.crops_config import list_crops, normalize_crop_id
from rag.retrieval import retrieve_rag_context
from rag import vector_store as vs
from rag.warmup import warmup_rag

app = Flask(__name__)
_cors_origins = [
    o.strip()
    for o in os.environ.get(
        "CORS_ALLOWED_ORIGINS",
        "http://localhost,http://127.0.0.1",
    ).split(",")
    if o.strip()
]
CORS(app, origins=_cors_origins, supports_credentials=True)


@app.route("/classify", methods=["POST"])
def classify_image():
    try:
        crop_id = request.form.get("crop_id") or request.args.get("crop_id") or "apple"
        try:
            crop_id = normalize_crop_id(crop_id)
        except ValueError as e:
            return jsonify({"success": False, "error": str(e)}), 400

        if "image" not in request.files:
            return jsonify({"success": False, "error": "No image file provided"}), 400

        file = request.files["image"]
        if file.filename == "":
            return jsonify({"success": False, "error": "Empty filename"}), 400

        image_bytes = file.read()
        if len(image_bytes) == 0:
            return jsonify({"success": False, "error": "Empty image file"}), 400

        clf = get_classifier_for_crop(crop_id)
        result = clf.predict_from_bytes(image_bytes)
        result["crop_id"] = crop_id
        response = jsonify(result)
        response.headers.set("Content-Type", "application/json; charset=utf-8")
        return response, 200

    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/rag/context", methods=["POST"])
def rag_context():
    try:
        data = request.get_json(silent=True) or {}
        question = (data.get("question") or "").strip()
        crop_id = data.get("crop_id") or "apple"
        if not question:
            return jsonify({"success": False, "error": "Пустой вопрос"}), 400

        payload = retrieve_rag_context(question, crop_id=crop_id)
        resp = jsonify(payload)
        resp.headers.set("Content-Type", "application/json; charset=utf-8")
        status = 200 if payload.get("success") else 422
        return resp, status
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/crops", methods=["GET"])
def crops_list():
    return jsonify({"success": True, **list_crops()}), 200


@app.route("/health", methods=["GET"])
def health_check():
    return jsonify({"status": "healthy", "service": "garden-python"}), 200


@app.route("/admin/reindex", methods=["POST"])
def admin_reindex():
    expected = os.environ.get("ADMIN_SECRET", "")
    secret = request.headers.get("X-Admin-Secret", "")
    if not expected or not hmac.compare_digest(secret, expected):
        return jsonify({"success": False, "error": "forbidden"}), 403
    try:
        vs.reset_vector_store()
        store = vs.load_vector_store(force_reindex=True)
        if store is None:
            return jsonify({"success": False, "error": "Нет статей для индексации"}), 400
        return jsonify({"success": True, "message": "RAG переиндексирован"}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


if __name__ == "__main__":
    port = int(os.environ.get("CLASSIFIER_PORT", 5000))
    if os.environ.get("USE_GUNICORN", "").lower() in ("1", "true", "yes"):
        import subprocess

        conf = os.path.join(os.path.dirname(__file__), "gunicorn.conf.py")
        print(f"Запуск Python API (gunicorn) на порту {port}")
        raise SystemExit(subprocess.call(["gunicorn", "-c", conf, "api.app:app"]))

    warmup_rag()
    print(f"Запуск Python API (Flask dev) на порту {port}")
    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)
