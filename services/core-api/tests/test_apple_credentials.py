from types import SimpleNamespace
from unittest.mock import patch
import pytest
from cryptography.fernet import Fernet
from fastapi import HTTPException
from app.application.services import apple_credentials as apple
from app.models.user import User
from app.models.apple_revocation import AppleRevocation
from app.infrastructure.repositories.sql_user_repository import SqlUserRepository


def configure(monkeypatch):
    key = Fernet.generate_key()
    monkeypatch.setenv('APPLE_TOKEN_ENCRYPTION_KEY', key.decode())
    return Fernet(key)


def test_exchange_encrypts_and_binds_subject(monkeypatch):
    encryption = configure(monkeypatch)
    response = SimpleNamespace(status_code=200, json=lambda: {'id_token': 'signed', 'refresh_token': 'private'})
    with patch.object(apple, 'client_credentials', return_value={'client_id': 'app'}), patch.object(apple.httpx, 'Client') as client:
        client.return_value.__enter__.return_value.post.return_value = response
        encrypted = apple.exchange('code', 'subject', lambda _: ('subject', None))
        assert encrypted != 'private'
        assert encryption.decrypt(encrypted.encode()) == b'private'
        with pytest.raises(HTTPException) as exc:
            apple.exchange('code', 'another-user', lambda _: ('subject', None))
        assert exc.value.status_code == 401


def test_missing_configuration_does_not_consume_code(monkeypatch):
    monkeypatch.delenv('APPLE_TOKEN_ENCRYPTION_KEY', raising=False)
    with patch.object(apple.httpx, 'Client') as client, pytest.raises(HTTPException) as exc:
        apple.exchange('code', 'subject', lambda _: ('subject', None))
    assert exc.value.status_code == 503
    client.assert_not_called()


def test_revocation_retries_and_erases_on_success(monkeypatch):
    from conftest import TestingSessionLocal
    encryption = configure(monkeypatch)
    with TestingSessionLocal() as db:
        row = AppleRevocation(encrypted_token=encryption.encrypt(b'private').decode())
        db.add(row); db.commit(); job_id = row.id
    with patch('app.core.database.SessionLocal', TestingSessionLocal), patch.object(apple, 'revoke', side_effect=RuntimeError()):
        apple.dispatch_revocations()
    from datetime import datetime
    with TestingSessionLocal() as db:
        row = db.get(AppleRevocation, job_id)
        assert row.attempts == 1
        row.available_at = datetime.utcnow(); db.commit()
    with patch('app.core.database.SessionLocal', TestingSessionLocal), patch.object(apple, 'revoke'):
        apple.dispatch_revocations()
    with TestingSessionLocal() as db:
        assert db.get(AppleRevocation, job_id) is None


def test_account_deletion_queues_encrypted_token_atomically():
    from conftest import TestingSessionLocal
    import uuid
    with TestingSessionLocal() as db:
        user = User(email=f'{uuid.uuid4()}@example.test', apple_id=str(uuid.uuid4()), apple_refresh_token_encrypted='encrypted')
        db.add(user); db.commit(); user_id = user.id
        SqlUserRepository(db).delete_account(user_id)
        assert db.get(User, user_id) is None
        assert db.query(AppleRevocation).filter_by(encrypted_token='encrypted').count() == 1
        db.query(AppleRevocation).filter_by(encrypted_token='encrypted').delete(); db.commit()


def test_apple_sign_in_route_persists_provider_token(client):
    import uuid
    from conftest import TestingSessionLocal
    subject = uuid.uuid4().hex
    email = f'apple_{subject}@example.test'
    with patch('app.application.services.auth_service.AuthService._verify_apple_token', return_value=(subject, email)), patch.object(apple, 'exchange', return_value='encrypted') as exchange:
        response = client.post('/internal/auth/apple', json={'identity_token': 'identity', 'authorization_code': 'code'})
    assert response.status_code == 200
    assert 'apple_refresh_token' not in str(response.json())
    assert exchange.call_args.args[:2] == ('code', subject)
    with TestingSessionLocal() as db:
        assert db.get(User, response.json()['user_id']).apple_refresh_token_encrypted == 'encrypted'


def test_provider_failure_does_not_create_user(client):
    import uuid
    from conftest import TestingSessionLocal
    email = f'{uuid.uuid4()}@example.test'
    with patch('app.application.services.auth_service.AuthService._verify_apple_token', return_value=('subject', email)), patch.object(apple, 'exchange', side_effect=HTTPException(503, 'Apple unavailable')):
        response = client.post('/internal/auth/apple', json={'identity_token': 'identity', 'authorization_code': 'code'})
    assert response.status_code == 503
    with TestingSessionLocal() as db:
        assert db.query(User).filter_by(email=email).first() is None
