"""Production startup must reject missing or weak signing keys."""
import os
import subprocess
import sys

import pytest


@pytest.mark.parametrize("secret", ["", "short", "tripclip-secret-change-in-production"])
def test_production_rejects_unsafe_jwt_secret(secret):
    result = subprocess.run(
        [sys.executable, "-c", "import app.core.auth"],
        env={**os.environ, "APP_ENV": "production", "JWT_SECRET_KEY": secret},
        capture_output=True, text=True,
    )
    assert result.returncode != 0
    assert "JWT_SECRET_KEY" in result.stderr


def test_production_accepts_long_jwt_secret():
    result = subprocess.run(
        [sys.executable, "-c", "import app.core.auth"],
        env={**os.environ, "APP_ENV": "production", "JWT_SECRET_KEY": "test-only-" + "a" * 40},
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
