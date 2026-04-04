"""
Configuração de testes e fixtures compartilhadas.
"""
from typing import Any, Dict, Generator

import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch

from app.config import settings
from app.main import app


@pytest.fixture
def client() -> TestClient:
    """Cliente HTTP para testes."""
    return TestClient(app)


@pytest.fixture
def api_key() -> str:
    """API Key para testes."""
    return "test-api-key"


@pytest.fixture
def mock_projects() -> list[Dict[str, Any]]:
    """Dados mockados de projetos para testes."""
    return [
        {
            "P": "1010",
            "Projeto": "Solar Panel Installation",
            "Status da Usina": "Ativo",
            "Vendedor": "João Silva",
            "Valor": "50000",
        },
        {
            "P": "1011",
            "Projeto": "Wind Farm",
            "Status da Usina": "Proposta",
            "Vendedor": "Maria Santos",
            "Valor": "100000",
        },
        {
            "P": "1012",
            "Projeto": "Hydro Power",
            "Status da Usina": "Ativo",
            "Vendedor": "João Silva",
            "Valor": "75000",
        },
    ]


@pytest.fixture
def mock_sheets_service(mock_projects: list[Dict[str, Any]]):
    """Mock do serviço de Google Sheets."""
    mock_service = MagicMock()

    # Configurar resposta do spreadsheets().values().get()
    mock_response = {
        "values": [
            ["P", "Projeto", "Status da Usina", "Vendedor", "Valor"],
            *[
                [
                    p.get(k) for k in ["P", "Projeto", "Status da Usina", "Vendedor", "Valor"]
                ]
                for p in mock_projects
            ],
        ]
    }

    mock_service.spreadsheets.return_value.values.return_value.get.return_value.execute.return_value = (
        mock_response
    )

    return mock_service


@pytest.fixture(autouse=True)
def reset_cache():
    """Limpa o cache antes de cada teste."""
    from app.routes import _cache, limpar_cache

    limpar_cache()
    yield
    limpar_cache()


@pytest.fixture
def env_vars(monkeypatch):
    """Configura variáveis de ambiente para testes."""
    monkeypatch.setenv("SECRET_KEY", "test-secret-key")
    monkeypatch.setenv("API_KEY_MASTER", "test-api-key")
    monkeypatch.setenv("CACHE_TTL_SECONDS", "60")
    monkeypatch.setenv("DEBUG", "true")

    return monkeypatch
