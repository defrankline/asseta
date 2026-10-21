"""Real RS256 JWTs signed by a test key, verified by the production OidcTokenVerifier."""

import time
import uuid
from typing import Any

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa

ISSUER = "http://keycloak.test/realms/asseta"
AUDIENCE = "asseta-api"


class StaticKeyProvider:
    def __init__(self, public_key: Any):
        self._key = public_key

    def key_for(self, token: str) -> Any:
        return self._key


class TokenFactory:
    def __init__(self) -> None:
        self.private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self.public_key = self.private_key.public_key()

    def mint(
        self,
        subject: str,
        groups: list[str],
        email: str = "user@example.com",
        ttl: int = 300,
        audience: str = AUDIENCE,
        issuer: str = ISSUER,
        key: Any = None,
    ) -> str:
        now = int(time.time())
        claims = {
            "sub": subject,
            "iss": issuer,
            "aud": audience,
            "iat": now,
            "exp": now + ttl,
            "email": email,
            "name": email.split("@")[0],
            "groups": groups,
            "sid": str(uuid.uuid4()),
        }
        return jwt.encode(claims, key or self.private_key, algorithm="RS256")
