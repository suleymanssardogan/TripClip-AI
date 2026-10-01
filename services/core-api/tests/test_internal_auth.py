"""
BFF ↔ core-api paylaşılan sır (X-Internal-Secret) doğrulaması.
"""
import unittest.mock as mock

import pytest
from fastapi import HTTPException

from app.core import internal_auth


@pytest.mark.asyncio
async def test_verify_internal_secret_skips_when_unset():
    """INTERNAL_API_SECRET tanımlı değilse (dev/test) doğrulama atlanır."""
    with mock.patch.object(internal_auth, "INTERNAL_API_SECRET", ""):
        await internal_auth.verify_internal_secret(x_internal_secret="anything")  # no raise


@pytest.mark.asyncio
async def test_verify_internal_secret_rejects_wrong_value():
    with mock.patch.object(internal_auth, "INTERNAL_API_SECRET", "correct-secret"):
        with pytest.raises(HTTPException) as exc_info:
            await internal_auth.verify_internal_secret(x_internal_secret="wrong-secret")
        assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_verify_internal_secret_accepts_correct_value():
    with mock.patch.object(internal_auth, "INTERNAL_API_SECRET", "correct-secret"):
        await internal_auth.verify_internal_secret(x_internal_secret="correct-secret")  # no raise


@pytest.mark.parametrize("secret", ["", "short"])
def test_production_rejects_weak_internal_secret(secret):
    import os
    import subprocess
    import sys
    result = subprocess.run(
        [sys.executable, "-c", "import app.core.internal_auth"],
        env={**os.environ, "APP_ENV": "production", "INTERNAL_API_SECRET": secret},
        capture_output=True, text=True,
    )
    assert result.returncode != 0
    assert "INTERNAL_API_SECRET must contain at least 32 characters" in result.stderr
