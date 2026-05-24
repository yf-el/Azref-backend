import jwt
from jwt.algorithms import RSAAlgorithm

from auth_clerk.jwks import JWKSClient
from auth_clerk.schemas import ClerkClaims


async def verify_token(token: str, issuer: str, jwks: JWKSClient) -> ClerkClaims:
    unverified_header = jwt.get_unverified_header(token)
    kid = unverified_header.get("kid")
    if not kid:
        raise ValueError("Token missing 'kid' header")

    jwk = await jwks.get_signing_key(kid)
    public_key = RSAAlgorithm.from_jwk(jwk)

    payload = jwt.decode(
        token,
        key=public_key,
        algorithms=["RS256"],
        issuer=issuer,
        options={"require": ["exp", "iat", "iss", "sub"]},
    )

    return ClerkClaims(**payload)
