"""
Utilidades de autenticación compartidas entre los routers.
"""
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, Request
from fastapi.responses import RedirectResponse
import jwt
from jwt.exceptions import InvalidTokenError, ExpiredSignatureError

SECRET_KEY        = "7e19d6b108943e9602f19a86d2c08f5533dc13abe9c95bf4f628eb7cb79a4b45"
TOKEN_SECONDS_EXP = 120
ALGORITHM         = "HS256"


def create_token(data: dict) -> str:
    payload = data.copy()
    payload["exp"] = datetime.now(timezone.utc) + timedelta(seconds=TOKEN_SECONDS_EXP)
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    """Decodifica y valida el JWT. Lanza HTTPException 401 si es inválido."""
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except (InvalidTokenError, ExpiredSignatureError):
        raise HTTPException(status_code=401, detail="Sesión inválida o expirada")


def get_token_from_cookie(request: Request) -> str:
    """Extrae el JWT de la cookie o redirige a /login."""
    token = request.cookies.get("access_token")
    if not token:
        raise _redir("/login")
    return token


def require_rol(payload: dict, rol: str) -> None:
    """Lanza 403 si el rol del token no coincide."""
    if payload.get("rol") != rol:
        raise HTTPException(status_code=403, detail=f"Acceso restringido a {rol}s")


def set_auth_cookie(response: RedirectResponse, token: str) -> RedirectResponse:
    response.set_cookie(
        key="access_token",
        value=token,
        max_age=TOKEN_SECONDS_EXP,
        httponly=True,
        samesite="lax",
    )
    return response


def _redir(url: str):
    """Truco: lanza una HTTPException con redirect para salir desde helpers."""
    from starlette.responses import RedirectResponse as SR
    # No podemos lanzar RedirectResponse como excepción directamente,
    # así que usamos un HTTPException especial y la ruta lo captura.
    raise HTTPException(status_code=307, headers={"Location": url})