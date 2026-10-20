from jose import jwt
from app.core.auth import SECRET_KEY, ALGORITHM, ACCESS_COOKIE, REFRESH_COOKIE


def test_expired_cookie_triggers_refresh_instead_of_anonymous_lookup(client, mock_core_api):
    client.cookies.set(ACCESS_COOKIE, jwt.encode(
        {'sub': '17', 'type': 'access', 'exp': 1}, SECRET_KEY, algorithm=ALGORITHM))
    assert client.get('/api/web/plans/52').status_code == 401
    mock_core_api.get.assert_not_awaited()


def test_refresh_cookie_without_access_triggers_refresh(client, mock_core_api):
    client.cookies.set(REFRESH_COOKIE, 'opaque-token')
    assert client.get('/api/web/plans/52').status_code == 401
    mock_core_api.get.assert_not_awaited()


def test_generic_not_found_preserves_http_semantics():
    from app.core.error_wrapper import _parse_core_error
    code, message, status = _parse_core_error({'error': {'code': 'NOT_FOUND'}})
    assert status == 404 and code == 'NOT_FOUND'
    assert 'erişim' in message
