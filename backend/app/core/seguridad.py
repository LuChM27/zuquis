"""Contraseñas (Argon2), tokens de acceso (JWT) y tokens de renovación opacos (sección 11)."""

import hashlib
import secrets
import uuid
from datetime import datetime, timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from app.core.config import obtener_config
from app.shared.fechas import ahora

_hasher = PasswordHasher()


def hashear_clave(clave: str) -> str:
    return _hasher.hash(clave)


def verificar_clave(hash_guardado: str, clave: str) -> bool:
    try:
        return _hasher.verify(hash_guardado, clave)
    except (VerificationError, InvalidHashError):
        return False


# Hash fijo para gastar el mismo tiempo cuando el usuario no existe y no revelar si existe.
HASH_FICTICIO = hashear_clave(secrets.token_urlsafe(16))


def crear_access_token(usuario_id: uuid.UUID, sede_id: uuid.UUID) -> tuple[str, datetime]:
    cfg = obtener_config()
    expira = ahora() + timedelta(minutes=cfg.access_minutos)
    carga = {
        "sub": str(usuario_id),
        "sede": str(sede_id),
        "exp": expira,
        "iat": ahora(),
        "tipo": "access",
    }
    return jwt.encode(carga, cfg.jwt_secret, algorithm=cfg.jwt_algoritmo), expira


def leer_access_token(token: str) -> dict:
    cfg = obtener_config()
    carga = jwt.decode(token, cfg.jwt_secret, algorithms=[cfg.jwt_algoritmo])
    if carga.get("tipo") != "access":
        raise jwt.InvalidTokenError("Tipo de token inválido")
    return carga


def nuevo_refresh_token() -> tuple[str, str]:
    """Devuelve (token para la cookie, hash para guardar en la base)."""
    token = secrets.token_urlsafe(48)
    return token, hash_refresh(token)


def hash_refresh(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()
