import pytest
from jose import jwt
from app.core.auth import SECRET_KEY, ALGORITHM


@pytest.mark.parametrize("claims", [
    {"sub": "1", "type": "refresh"}, {"sub": "1"}, {"type": "access"},
    {"sub": "bad", "type": "access"}, {"sub": "0", "type": "access"},
    {"sub": "-1", "type": "access"}, {"sub": "1", "type": "access", "exp": 1},
])
def test_bad_access_claims_return_401(client, mock_core_api, claims):
    token = jwt.encode(claims, SECRET_KEY, algorithm=ALGORITHM)
    response = client.get('/api/mobile/videos/1', headers={'Authorization': f'Bearer {token}'})
    assert response.status_code == 401
    mock_core_api.get.assert_not_awaited()
