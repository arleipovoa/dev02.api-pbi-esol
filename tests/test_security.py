"""
Testes para autenticação e segurança.
"""
import pytest
from unittest.mock import patch

from app.security import create_access_token, verify_jwt, verify_api_key
from app.config import settings


class TestJWTAuthentication:
    """Testes de autenticação JWT."""

    def test_create_access_token(self) -> None:
        """Testa criação de token JWT."""
        data = {"sub": "user123", "email": "test@example.com"}
        token = create_access_token(data)

        # Token deve ser uma string não vazia
        assert isinstance(token, str)
        assert len(token) > 0

    def test_verify_jwt_valid_token(self) -> None:
        """Testa verificação de token JWT válido."""
        data = {"sub": "user123", "email": "test@example.com"}
        token = create_access_token(data)

        # Verificar token
        payload = verify_jwt(token)
        assert payload is not None
        assert payload["sub"] == "user123"
        assert payload["email"] == "test@example.com"

    def test_verify_jwt_invalid_token(self) -> None:
        """Testa verificação de token JWT inválido."""
        invalid_token = "invalid.token.here"
        payload = verify_jwt(invalid_token)
        assert payload is None

    def test_verify_jwt_malformed_token(self) -> None:
        """Testa verificação de token JWT malformado."""
        malformed_token = "not_a_jwt_at_all"
        payload = verify_jwt(malformed_token)
        assert payload is None


class TestAPIKeyAuthentication:
    """Testes de autenticação por API Key."""

    def test_verify_api_key_master(self) -> None:
        """Testa verificação de API_KEY_MASTER."""
        with patch.object(settings, 'API_KEY_MASTER', 'test-key-123'):
            result = verify_api_key('test-key-123')
            assert result is True

    def test_verify_api_key_esol(self) -> None:
        """Testa verificação de ESOL_API_KEY."""
        with patch.object(settings, 'ESOL_API_KEY', 'esol-key-456'):
            with patch.object(settings, 'API_KEY_MASTER', None):
                result = verify_api_key('esol-key-456')
                assert result is True

    def test_verify_api_key_invalid(self) -> None:
        """Testa verificação de API Key inválida."""
        with patch.object(settings, 'API_KEY_MASTER', 'correct-key'):
            with patch.object(settings, 'ESOL_API_KEY', None):
                result = verify_api_key('wrong-key')
                assert result is False

    def test_verify_api_key_empty(self) -> None:
        """Testa verificação com API Key vazia."""
        with patch.object(settings, 'API_KEY_MASTER', 'correct-key'):
            result = verify_api_key('')
            assert result is False

    def test_verify_api_key_none_configured(self) -> None:
        """Testa verificação quando nenhuma API Key está configurada."""
        with patch.object(settings, 'API_KEY_MASTER', None):
            with patch.object(settings, 'ESOL_API_KEY', None):
                result = verify_api_key('any-key')
                assert result is False


class TestAuthenticationMethods:
    """Testes de múltiplos métodos de autenticação."""

    def test_api_key_takes_precedence(self) -> None:
        """Testa que API Key é verificada mesmo se JWT falhar."""
        # Criar um token JWT inválido
        invalid_jwt = "invalid.jwt.token"

        # Com API Key válida, deve funcionar
        with patch.object(settings, 'API_KEY_MASTER', 'valid-key'):
            result_jwt = verify_jwt(invalid_jwt)
            result_api = verify_api_key('valid-key')

            assert result_jwt is None  # JWT inválido
            assert result_api is True  # API Key válida

    def test_both_keys_can_work(self) -> None:
        """Testa que tanto API_KEY_MASTER quanto ESOL_API_KEY funcionam."""
        with patch.object(settings, 'API_KEY_MASTER', 'master-key'):
            with patch.object(settings, 'ESOL_API_KEY', 'esol-key'):
                assert verify_api_key('master-key') is True
                assert verify_api_key('esol-key') is True
                assert verify_api_key('wrong-key') is False
