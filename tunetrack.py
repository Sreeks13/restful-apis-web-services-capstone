import os
import sys
import base64
import argparse
import threading
import unittest
from unittest.mock import Mock

import requests
from flask import Flask, jsonify, request, make_response
from requests.auth import HTTPBasicAuth


# ============================================================
# 1. CONFIGURATION
# ============================================================

BASE_URL = os.getenv(
    "TUNETRACK_BASE_URL", "http://127.0.0.1:5000"
)
USERNAME = os.getenv("TUNETRACK_USER", "student")
PASSWORD = os.getenv("TUNETRACK_PASSWORD", "lessonpass")
CLIENT_TOKEN = os.getenv("TUNETRACK_TOKEN", "tunetrack-client")
TIMEOUT = float(os.getenv("TUNETRACK_TIMEOUT", "3"))


# ============================================================
# 2. IN-MEMORY DATA STORE
# ============================================================

class SchoolData:
    def __init__(self):
        self.lessons = {}
        self.next_id = 1
        self.lock = threading.Lock()

    def list(self):
        with self.lock:
            return [dict(item) for item in self.lessons.values()]

    def get(self, lesson_id):
        with self.lock:
            item = self.lessons.get(int(lesson_id))
            return dict(item) if item else None

    def create(self, data):
        with self.lock:
            item = {"id": self.next_id, **data}
            self.lessons[self.next_id] = item
            self.next_id += 1
            return dict(item)

    def update(self, lesson_id, data):
        with self.lock:
            lesson_id = int(lesson_id)
            if lesson_id not in self.lessons:
                return None
            self.lessons[lesson_id].update(data)
            return dict(self.lessons[lesson_id])

    def delete(self, lesson_id):
        with self.lock:
            return (
                self.lessons.pop(int(lesson_id), None) is not None
            )


db = SchoolData()


# ============================================================
# 3. REST API SERVER
# ============================================================

app = Flask(__name__)

REQUIRED_FIELDS = (
    "student", "instrument", "date", "duration_minutes"
)

ALLOWED_FIELDS = {
    "student", "instrument", "date",
    "duration_minutes", "teacher", "notes"
}


@app.before_request
def authenticate():
    # Health check is public.
    if request.path == "/health":
        return None

    auth = request.authorization

    if (
        not auth
        or auth.username != USERNAME
        or auth.password != PASSWORD
    ):
        return jsonify({
            "error": "unauthorized",
            "message": "Invalid Basic Authentication"
        }), 401

    if request.headers.get("X-TuneTrack-Client") != CLIENT_TOKEN:
        return jsonify({
            "error": "unauthorized",
            "message": "Invalid client header"
        }), 401

    return None


@app.get("/health")
def health():
    return jsonify({"status": "ok"}), 200


@app.get("/lessons")
def list_lessons():
    return jsonify({"lessons": db.list()}), 200


@app.get("/lessons/<int:lesson_id>")
def get_lesson(lesson_id):
    lesson = db.get(lesson_id)

    if lesson is None:
        return jsonify({
            "error": "not_found",
            "message": "Lesson not found"
        }), 404

    return jsonify(lesson), 200


def validate_lesson(data, creating=False):
    if not isinstance(data, dict):
        return "Request body must be a JSON object"

    if creating:
        missing = [
            field for field in REQUIRED_FIELDS
            if field not in data
        ]
        if missing:
            return "Missing fields: " + ", ".join(missing)

    unknown = set(data) - ALLOWED_FIELDS
    if unknown:
        return "Unknown fields: " + ", ".join(sorted(unknown))

    for field in ("student", "instrument", "date"):
        if field in data:
            value = data[field]
            if not isinstance(value, str) or not value.strip():
                return f"{field} must be a non-empty string"

    if "duration_minutes" in data:
        value = data["duration_minutes"]

        if isinstance(value, bool):
            return "duration_minutes must be an integer"

        try:
            duration = int(value)
        except (ValueError, TypeError, OverflowError):
            return "duration_minutes must be an integer"

        if isinstance(value, float) and not value.is_integer():
            return "duration_minutes must be an integer"

        if isinstance(value, str) and str(duration) != value.strip():
            return "duration_minutes must be an integer"

        if duration <= 0:
            return "duration_minutes must be positive"

    return None


def normalize_lesson(data):
    result = dict(data)

    for field in ("student", "instrument", "date"):
        if field in result:
            result[field] = result[field].strip()

    if "duration_minutes" in result:
        result["duration_minutes"] = int(
            result["duration_minutes"]
        )

    return result


@app.post("/lessons")
def create_lesson():
    data = request.get_json(silent=True)
    error = validate_lesson(data, creating=True)

    if error:
        return jsonify({
            "error": "bad_request",
            "message": error
        }), 400

    data = normalize_lesson(data)
    data.setdefault("teacher", "")
    data.setdefault("notes", "")

    lesson = db.create(data)
    return jsonify(lesson), 201


@app.put("/lessons/<int:lesson_id>")
def update_lesson(lesson_id):
    data = request.get_json(silent=True)

    if not isinstance(data, dict) or not data:
        return jsonify({
            "error": "bad_request",
            "message": "Provide a non-empty JSON object"
        }), 400

    current = db.get(lesson_id)

    if current is None:
        return jsonify({
            "error": "not_found",
            "message": "Lesson not found"
        }), 404

    error = validate_lesson(data)

    if error:
        return jsonify({
            "error": "bad_request",
            "message": error
        }), 400

    merged = normalize_lesson({**current, **data})
    merged.pop("id", None)

    updated = db.update(lesson_id, merged)
    return jsonify(updated), 200


@app.delete("/lessons/<int:lesson_id>")
def delete_lesson(lesson_id):
    if not db.delete(lesson_id):
        return jsonify({
            "error": "not_found",
            "message": "Lesson not found"
        }), 404

    return "", 204


@app.errorhandler(500)
def internal_server_error(error):
    app.logger.exception("Unexpected server error: %s", error)
    return jsonify({
        "error": "server_error",
        "message": "An unexpected server error occurred"
    }), 500


# ============================================================
# 4. API CLIENT AND FRIENDLY ERROR HANDLING
# ============================================================

class TuneTrackError(Exception):
    """Readable error for API and connection failures."""


class APIClient:
    def __init__(
        self,
        base_url=BASE_URL,
        username=USERNAME,
        password=PASSWORD,
        token=CLIENT_TOKEN,
        timeout=TIMEOUT,
        session=None
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = session or requests.Session()

        self.session.auth = HTTPBasicAuth(username, password)
        self.session.headers.update({
            "Accept": "application/json",
            "Content-Type": "application/json",
            "X-TuneTrack-Client": token
        })

    def request(self, method, path, **kwargs):
        try:
            response = self.session.request(
                method,
                self.base_url + path,
                timeout=self.timeout,
                **kwargs
            )

            if response.status_code == 204:
                return None

            try:
                data = response.json()
            except ValueError:
                data = {}

            if response.status_code >= 400:
                message = data.get(
                    "message",
                    response.reason or "Request failed"
                )
                raise TuneTrackError(
                    f"HTTP {response.status_code}: {message}"
                )

            return data

        except requests.exceptions.Timeout as exc:
            raise TuneTrackError(
                f"Request timed out after {self.timeout} seconds."
            ) from exc

        except requests.exceptions.ConnectionError as exc:
            raise TuneTrackError(
                "Cannot reach the API server. Is it running?"
            ) from exc

        except requests.exceptions.RequestException as exc:
            raise TuneTrackError(
                f"Request failed: {exc}"
            ) from exc

    def list_lessons(self):
        return self.request("GET", "/lessons")["lessons"]

    def get_lesson(self, lesson_id):
        return self.request("GET", f"/lessons/{int(lesson_id)}")

    def create_lesson(self, **data):
        return self.request("POST", "/lessons", json=data)

    def update_lesson(self, lesson_id, **data):
        return self.request(
            "PUT", f"/lessons/{int(lesson_id)}", json=data
        )

    def delete_lesson(self, lesson_id):
        return self.request("DELETE", f"/lessons/{int(lesson_id)}")


# ============================================================
# 5. DISPLAY HELPERS
# ============================================================

def show_lesson(lesson):
    print(
        f"Lesson #{lesson['id']}: "
        f"{lesson['student']} - {lesson['instrument']}"
    )
    print(
        f"Date: {lesson['date']} | "
        f"Duration: {lesson['duration_minutes']} minutes"
    )

    if lesson.get("teacher"):
        print(f"Teacher: {lesson['teacher']}")

    if lesson.get("notes"):
        print(f"Notes: {lesson['notes']}")


def show_lessons(lessons):
    if not lessons:
        print("No lessons scheduled.")
        return

    for lesson in lessons:
        show_lesson(lesson)
        print("-" * 40)


# ============================================================
# 6. COMMAND-LINE INTERFACE
# ============================================================

def run_cli(argv=None):
    parser = argparse.ArgumentParser(
        description="TuneTrack Music School Lesson API Manager"
    )
    commands = parser.add_subparsers(
        dest="command", required=True
    )

    commands.add_parser("list", help="List all lessons")

    get_cmd = commands.add_parser("get", help="Get a lesson")
    get_cmd.add_argument("id", type=int)

    create_cmd = commands.add_parser(
        "create", help="Create a lesson"
    )

    for field in ("student", "instrument", "date"):
        create_cmd.add_argument(f"--{field}", required=True)

    create_cmd.add_argument("--duration", type=int, required=True)
    create_cmd.add_argument("--teacher", default="")
    create_cmd.add_argument("--notes", default="")

    update_cmd = commands.add_parser(
        "update", help="Update a lesson"
    )
    update_cmd.add_argument("id", type=int)

    for field in ("student", "instrument", "date", "teacher", "notes"):
        update_cmd.add_argument(f"--{field}")

    update_cmd.add_argument("--duration", type=int)

    delete_cmd = commands.add_parser(
        "delete", help="Delete a lesson"
    )
    delete_cmd.add_argument("id", type=int)

    args = parser.parse_args(argv)
    client = APIClient()

    try:
        if args.command == "list":
            show_lessons(client.list_lessons())

        elif args.command == "get":
            show_lesson(client.get_lesson(args.id))

        elif args.command == "create":
            lesson = client.create_lesson(
                student=args.student,
                instrument=args.instrument,
                date=args.date,
                duration_minutes=args.duration,
                teacher=args.teacher,
                notes=args.notes
            )
            print("Lesson created successfully (HTTP 201).")
            show_lesson(lesson)

        elif args.command == "update":
            changes = {
                "student": args.student,
                "instrument": args.instrument,
                "date": args.date,
                "duration_minutes": args.duration,
                "teacher": args.teacher,
                "notes": args.notes
            }
            changes = {
                key: value for key, value in changes.items()
                if value is not None
            }

            if not changes:
                print("Provide at least one field to update.")
                return 2

            lesson = client.update_lesson(args.id, **changes)
            print("Lesson updated successfully (HTTP 200).")
            show_lesson(lesson)

        elif args.command == "delete":
            client.delete_lesson(args.id)
            print("Lesson deleted successfully (HTTP 204).")

        return 0

    except TuneTrackError as exc:
        print(f"Error: {exc}")
        return 1


# ============================================================
# 7. AUTOMATED TESTS
# ============================================================

class TestSchoolData(unittest.TestCase):
    def test_crud_operations(self):
        store = SchoolData()

        lesson = store.create({
            "student": "Asha",
            "instrument": "Piano",
            "date": "2026-10-20",
            "duration_minutes": 30
        })

        lesson_id = lesson["id"]

        self.assertEqual(store.get(lesson_id)["student"], "Asha")
        self.assertIsNotNone(
            store.update(lesson_id, {"notes": "Practice"})
        )
        self.assertEqual(
            store.get(lesson_id)["notes"], "Practice"
        )
        self.assertTrue(store.delete(lesson_id))
        self.assertIsNone(store.get(lesson_id))


class TestAPI(unittest.TestCase):
    def setUp(self):
        app.config["TESTING"] = True
        self.client = app.test_client()

        with db.lock:
            db.lessons.clear()
            db.next_id = 1

        credentials = base64.b64encode(
            f"{USERNAME}:{PASSWORD}".encode()
        ).decode()

        self.headers = {
            "Authorization": f"Basic {credentials}",
            "X-TuneTrack-Client": CLIENT_TOKEN
        }

    def send(self, method, path, **kwargs):
        kwargs.setdefault("headers", self.headers)
        return getattr(self.client, method)(path, **kwargs)

    def test_health(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)

    def test_authentication(self):
        response = self.client.get("/lessons")
        self.assertEqual(response.status_code, 401)

    def test_missing_custom_header(self):
        response = self.client.get(
            "/lessons",
            headers={
                "Authorization": self.headers["Authorization"]
            }
        )
        self.assertEqual(response.status_code, 401)

    def test_crud_and_status_codes(self):
        payload = {
            "student": "Asha",
            "instrument": "Piano",
            "date": "2026-10-20",
            "duration_minutes": 30,
            "teacher": "Mr Rao"
        }

        created = self.send("post", "/lessons", json=payload)
        self.assertEqual(created.status_code, 201)
        lesson_id = created.get_json()["id"]

        listed = self.send("get", "/lessons")
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(len(listed.get_json()["lessons"]), 1)

        fetched = self.send("get", f"/lessons/{lesson_id}")
        self.assertEqual(fetched.status_code, 200)

        updated = self.send(
            "put",
            f"/lessons/{lesson_id}",
            json={"notes": "Bring sheet music"}
        )
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(
            updated.get_json()["notes"], "Bring sheet music"
        )

        deleted = self.send("delete", f"/lessons/{lesson_id}")
        self.assertEqual(deleted.status_code, 204)

        missing = self.send("get", f"/lessons/{lesson_id}")
        self.assertEqual(missing.status_code, 404)

    def test_invalid_payload(self):
        response = self.send(
            "post", "/lessons", json={"student": "Asha"}
        )
        self.assertEqual(response.status_code, 400)

    def test_invalid_duration(self):
        response = self.send(
            "post",
            "/lessons",
            json={
                "student": "Asha",
                "instrument": "Piano",
                "date": "2026-10-20",
                "duration_minutes": -5
            }
        )
        self.assertEqual(response.status_code, 400)


class TestAPIClient(unittest.TestCase):
    def test_session_configuration(self):
        client = APIClient()
        self.assertIsInstance(client.session.auth, HTTPBasicAuth)
        self.assertEqual(
            client.session.headers["X-TuneTrack-Client"],
            CLIENT_TOKEN
        )

    def test_timeout_handling(self):
        session = Mock()
        session.request.side_effect = requests.exceptions.Timeout()
        client = APIClient(session=session)

        with self.assertRaisesRegex(TuneTrackError, "timed out"):
            client.list_lessons()

    def test_connection_failure(self):
        session = Mock()
        session.request.side_effect = (
            requests.exceptions.ConnectionError()
        )
        client = APIClient(session=session)

        with self.assertRaisesRegex(TuneTrackError, "Cannot reach"):
            client.list_lessons()

    def test_http_error(self):
        session = Mock()
        response = Mock()
        response.status_code = 404
        response.reason = "Not Found"
        response.json.return_value = {
            "message": "Lesson not found"
        }
        session.request.return_value = response

        client = APIClient(session=session)

        with self.assertRaisesRegex(
            TuneTrackError, "HTTP 404"
        ):
            client.get_lesson(999)


# ============================================================
# 8. ENTRY POINT
# ============================================================

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "server":
        app.run(
            host="127.0.0.1",
            port=int(os.getenv("TUNETRACK_PORT", "5000")),
            debug=False
        )

    elif len(sys.argv) > 1 and sys.argv[1] == "test":
        unittest.main(argv=[sys.argv[0], *sys.argv[2:]])

    else:
        raise SystemExit(run_cli())