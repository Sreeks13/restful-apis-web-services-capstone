from flask import Flask, jsonify, request
from functools import wraps

from school_data import SchoolData
from settings import SETTINGS

app = Flask(__name__)
school = SchoolData()


def require_auth(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        auth = request.authorization
        expected_user = SETTINGS["username"]
        expected_password = SETTINGS["password"]
        client_name = request.headers.get("X-TuneTrack-Client")

        if (
            not auth
            or auth.username != expected_user
            or auth.password != expected_password
        ):
            return jsonify({"error": "Authentication required"}), 401

        if client_name != SETTINGS["client_name"]:
            return jsonify({"error": "Invalid client header"}), 400

        return view(*args, **kwargs)

    return wrapper


@app.get("/health")
def health():
    return jsonify({"status": "ok"}), 200


@app.get("/lessons")
@require_auth
def list_lessons():
    return jsonify(school.list_lessons()), 200


@app.get("/lessons/<int:lesson_id>")
@require_auth
def get_lesson(lesson_id):
    lesson = school.get_lesson(lesson_id)
    if lesson is None:
        return jsonify({"error": "Lesson not found"}), 404
    return jsonify(lesson), 200


@app.post("/lessons")
@require_auth
def create_lesson():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "JSON object required"}), 400

    required = ("student", "instrument", "date", "duration", "teacher")
    if any(not data.get(field) for field in required):
        return jsonify({"error": "Missing required lesson fields"}), 400

    try:
        duration = int(data["duration"])
    except (ValueError, TypeError):
        return jsonify({"error": "Duration must be an integer"}), 400

    if duration <= 0:
        return jsonify({"error": "Duration must be positive"}), 400

    lesson = school.create_lesson({
        "student": str(data["student"]),
        "instrument": str(data["instrument"]),
        "date": str(data["date"]),
        "duration": duration,
        "teacher": str(data["teacher"]),
        "notes": str(data.get("notes", "")),
    })
    return jsonify(lesson), 201


@app.put("/lessons/<int:lesson_id>")
@require_auth
def update_lesson(lesson_id):
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "JSON object required"}), 400

    allowed = {"student", "instrument", "date", "duration", "teacher", "notes"}
    if not data or set(data) - allowed:
        return jsonify({"error": "Invalid or empty update fields"}), 400

    if "duration" in data:
        try:
            data["duration"] = int(data["duration"])
        except (ValueError, TypeError):
            return jsonify({"error": "Duration must be an integer"}), 400

        if data["duration"] <= 0:
            return jsonify({"error": "Duration must be positive"}), 400

    lesson = school.update_lesson(lesson_id, data)
    if lesson is None:
        return jsonify({"error": "Lesson not found"}), 404
    return jsonify(lesson), 200


@app.delete("/lessons/<int:lesson_id>")
@require_auth
def delete_lesson(lesson_id):
    if not school.delete_lesson(lesson_id):
        return jsonify({"error": "Lesson not found"}), 404
    return "", 204


if __name__ == "__main__":
    app.run(
        host="127.0.0.1",
        port=int(__import__("os").getenv("TUNETRACK_PORT", "5000")),
        debug=False,
    )