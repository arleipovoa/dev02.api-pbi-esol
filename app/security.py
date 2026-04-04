"""
Módulo de autenticação e segurança.
Suporta JWT e API Key.
"""
from datetime import datetime, timedelta
from typing import Optional

from jose import JWTError, jwt

from app.config import settings
from app.exceptions import AuthenticationError
from app.logger import logger


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Cria um token JWT.

    Args:
        data: Dados a incluir no token
        expires_delta: Tempo de expiração customizado

    Returns:
        Token JWT codificado
    """
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )
    to_encode.update({"exp": expire})

    encoded_jwt = jwt.encode(
        to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM
    )
    return encoded_jwt


def verify_jwt(token: str) -> Optional[dict]:
    """
    Verifica e decodifica um token JWT.

    Args:
        token: Token JWT a verificar

    Returns:
        Payload do token se válido, None caso contrário
    """
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        return payload
    except JWTError as e:
        logger.warning(f"Token JWT inválido: {e}")
        return None


def verify_api_key(api_key: str) -> bool:
    """
    Verifica se a API Key é válida.

    Args:
        api_key: API Key a verificar

    Returns:
        True se válida, False caso contrário
    """
    # Checar contra API_KEY_MASTER
    if settings.API_KEY_MASTER and api_key == settings.API_KEY_MASTER:
        return True

    # Checar contra ESOL_API_KEY
    if settings.ESOL_API_KEY and api_key == settings.ESOL_API_KEY:
        return True

    logger.warning(f"API Key inválida recebida")
    return False