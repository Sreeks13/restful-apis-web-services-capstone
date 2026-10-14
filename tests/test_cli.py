import unittest

from mock_server import app, school
from settings import SETTINGS


class TestTuneTrackAPI(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        self.headers = {
            "X-TuneTrack-Client": SETTINGS["client_name"]
        }
        self.auth = (
            SETTINGS["username"],
            SETTINGS["password"],
        )

    def request_headers(self):
        import base64

        credentials = (
            f"{self.auth[0]}:{self.auth[1]}".encode("utf-8")
        )
        encoded = base64.b64encode(credentials).decode("ascii")

        return {
            **self.headers,
            "Authorization": f"Basic {encoded}",
        }

    def test_health_is_public(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)

    def test_lessons_requires_auth(self):
        response = self.client.get("/lessons")
        self.assertEqual(response.status_code, 401)

    def test_list_lessons(self):
        response = self.client.get(
            "/lessons", headers=self.request_headers()
        )
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.get_json(), list)

    def test_create_lesson(self):
        response = self.client.post(
            "/lessons",
            headers=self.request_headers(),
            json={
                "student": "Test Student",
                "instrument": "Piano",
                "date": "2026-10-25",
                "duration": 30,
                "teacher": "Test Teacher",
            },
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.get_json()["student"], "Test Student")

    def test_missing_lesson_returns_404(self):
        response = self.client.get(
            "/lessons/99999",
            headers=self.request_headers(),
        )
        self.assertEqual(response.status_code, 404)

    def test_invalid_client_header(self):
        headers = self.request_headers()
        headers["X-TuneTrack-Client"] = "WrongClient"

        response = self.client.get("/lessons", headers=headers)
        self.assertEqual(response.status_code, 400)


if __name__ == "__main__":
    unittest.main()