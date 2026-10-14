import requests
from requests.auth import HTTPBasicAuth

from settings import SETTINGS


class APIClientError(Exception):
    pass


class APIClient:
    def __init__(self, base_url=None, timeout=None, session=None):
        self.base_url = (base_url or SETTINGS["base_url"]).rstrip("/")
        self.timeout = timeout or SETTINGS["timeout"]
        self.session = session or requests.Session()

        self.session.auth = HTTPBasicAuth(
            SETTINGS["username"],
            SETTINGS["password"],
        )
        self.session.headers.update({
            "X-TuneTrack-Client": SETTINGS["client_name"],
            "Accept": "application/json",
        })

    def request(self, method, path, **kwargs):
        url = f"{self.base_url}/{path.lstrip('/')}"

        try:
            response = self.session.request(
                method,
                url,
                timeout=self.timeout,
                **kwargs,
            )
            response.raise_for_status()

            if response.status_code == 204 or not response.content:
                return None

            return response.json()

        except requests.Timeout as exc:
            raise APIClientError("Request timed out.") from exc
        except requests.ConnectionError as exc:
            raise APIClientError(
                "Cannot connect to TuneTrack server."
            ) from exc
        except requests.HTTPError as exc:
            response = exc.response
            try:
                message = response.json().get(
                    "error", response.reason
                )
            except (ValueError, AttributeError):
                message = response.reason if response else str(exc)

            status = response.status_code if response else "unknown"
            raise APIClientError(
                f"HTTP {status}: {message}"
            ) from exc
        except ValueError as exc:
            raise APIClientError(
                "Server returned invalid JSON."
            ) from exc

    def list_lessons(self):
        return self.request("GET", "/lessons")

    def get_lesson(self, lesson_id):
        return self.request("GET", f"/lessons/{lesson_id}")

    def create_lesson(self, lesson):
        return self.request("POST", "/lessons", json=lesson)

    def update_lesson(self, lesson_id, changes):
        return self.request(
            "PUT", f"/lessons/{lesson_id}", json=changes
        )

    def delete_lesson(self, lesson_id):
        return self.request("DELETE", f"/lessons/{lesson_id}")

    def close(self):
        self.session.close()