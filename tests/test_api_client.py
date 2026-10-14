import unittest
from unittest.mock import Mock

import requests

from api_client import APIClient, APIClientError


class TestAPIClient(unittest.TestCase):
    def setUp(self):
        self.session = Mock(spec=requests.Session)
        self.client = APIClient(
            base_url="http://localhost:5000",
            timeout=3,
            session=self.session,
        )

    def test_client_sets_auth_and_header(self):
        self.assertIsNotNone(self.session.auth)
        self.assertEqual(
            self.session.headers.update.call_args.args[0][
                "X-TuneTrack-Client"
            ],
            "TuneTrack",
        )

    def test_successful_json_response(self):
        response = Mock()
        response.status_code = 200
        response.content = b'{"id": 1}'
        response.json.return_value = {"id": 1}
        response.raise_for_status.return_value = None
        self.session.request.return_value = response

        result = self.client.get_lesson(1)

        self.assertEqual(result, {"id": 1})
        self.session.request.assert_called_once()

    def test_timeout_is_handled(self):
        self.session.request.side_effect = requests.Timeout()

        with self.assertRaisesRegex(APIClientError, "timed out"):
            self.client.get_lesson(1)

    def test_connection_error_is_handled(self):
        self.session.request.side_effect = requests.ConnectionError()

        with self.assertRaisesRegex(APIClientError, "Cannot connect"):
            self.client.get_lesson(1)


if __name__ == "__main__":
    unittest.main()