import pytest
import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization

from app.services.github_app import GitHubAppService


@pytest.fixture
def rsa_private_key():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    ).decode("utf-8")


def test_github_app_jwt_generation(rsa_private_key):
    service = GitHubAppService(app_id="123456", private_key=rsa_private_key)
    token = service.generate_jwt(expiration_seconds=300)
    assert token is not None

    # Decode and verify header & claims
    decoded = jwt.decode(token, options={"verify_signature": False})
    assert decoded["iss"] == "123456"
    assert "exp" in decoded
    assert "iat" in decoded
    assert decoded["exp"] > decoded["iat"]


def test_missing_credentials_raises_error():
    service = GitHubAppService(app_id="", private_key="")
    with pytest.raises(ValueError, match="GitHub App ID and Private Key are required"):
        service.generate_jwt()
