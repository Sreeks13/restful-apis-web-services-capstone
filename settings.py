import configparser
import os
from pathlib import Path

CONFIG_FILE = Path(__file__).with_name("tunetrack.ini")


def load_settings():
    config = configparser.ConfigParser()

    if CONFIG_FILE.exists():
        config.read(CONFIG_FILE)

    return {
        "base_url": os.getenv(
            "TUNETRACK_BASE_URL",
            config.get("api", "base_url",
                       fallback="http://127.0.0.1:5000"),
        ).rstrip("/"),
        "timeout": float(os.getenv(
            "TUNETRACK_TIMEOUT",
            config.get("api", "timeout", fallback="3"),
        )),
        "username": os.getenv(
            "TUNETRACK_USERNAME",
            config.get("auth", "username", fallback="student"),
        ),
        "password": os.getenv(
            "TUNETRACK_PASSWORD",
            config.get("auth", "password", fallback="lessonpass"),
        ),
        "client_name": os.getenv(
            "TUNETRACK_CLIENT",
            config.get("auth", "client_name", fallback="TuneTrack"),
        ),
    }


SETTINGS = load_settings()