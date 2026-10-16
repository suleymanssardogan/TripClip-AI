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


def test_deleted_account_subject_cannot_list_or_create_trips(client, registered_user):
    user_id = registered_user['user_id']
    headers = {'x-user-id': str(user_id)}
    assert client.get('/internal/trips', headers=headers).status_code == 200
    assert client.delete('/internal/auth/account', headers=headers).status_code == 200
    assert client.get('/internal/trips', headers=headers).status_code == 401
    assert client.post('/internal/trips', headers=headers, json={'title': 'Deleted user', 'place_ids': []}).status_code == 401


def test_disabled_account_subject_is_rejected(client, registered_user):
    from conftest import TestingSessionLocal
    from app.models.user import User
    with TestingSessionLocal() as db:
        db.get(User, registered_user['user_id']).is_active = False
        db.commit()
    assert client.get('/internal/trips', headers={'x-user-id': str(registered_user['user_id'])}).status_code == 401
