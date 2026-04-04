"""
Testes para os endpoints da API.
"""
from unittest.mock import patch
from typing import Dict, Any

import pytest
from fastapi.testclient import TestClient


class TestHealthEndpoint:
    """Testes do endpoint /health."""

    def test_health_check(self, client: TestClient) -> None:
        """Testa que o health check retorna status ok."""
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"
        assert "cache_ttl_seconds" in response.json()

    def test_health_check_rate_limit(self, client: TestClient) -> None:
        """Testa rate limiting do health check."""
        # Health check tem limite de 30/minuto, então fazemos 31 requisições
        for i in range(31):
            response = client.get("/health")
            if i < 30:
                assert response.status_code == 200
            else:
                # 31ª requisição deve ser rate limited
                assert response.status_code == 429


class TestProjectEndpoints:
    """Testes dos endpoints de projetos."""

    def test_buscar_projeto_sem_autenticacao(self, client: TestClient) -> None:
        """Testa que endpoint requer autenticação."""
        response = client.get("/projeto/1010")
        assert response.status_code == 403
        assert "não autorizado" in response.json()["detail"].lower()

    def test_buscar_projeto_com_api_key(
        self, client: TestClient, api_key: str, mock_sheets_service
    ) -> None:
        """Testa buscar projeto com autenticação via API Key."""
        with patch("app.routes.service_account.Credentials.from_service_account_file"):
            with patch(
                "app.routes.build", return_value=mock_sheets_service
            ):
                response = client.get(
                    "/projeto/1010",
                    headers={"x-api-key": api_key}
                )
                assert response.status_code == 200
                data = response.json()
                assert data["P"] == "1010"

    def test_buscar_projeto_inexistente(
        self, client: TestClient, api_key: str, mock_sheets_service
    ) -> None:
        """Testa buscar projeto que não existe."""
        with patch("app.routes.service_account.Credentials.from_service_account_file"):
            with patch("app.routes.build", return_value=mock_sheets_service):
                response = client.get(
                    "/projeto/9999",
                    headers={"x-api-key": api_key}
                )
                assert response.status_code == 404
                assert "não encontrado" in response.json()["detail"].lower()

    def test_listar_projetos_sem_filtro(
        self, client: TestClient, api_key: str, mock_sheets_service, mock_projects
    ) -> None:
        """Testa listar todos os projetos."""
        with patch("app.routes.service_account.Credentials.from_service_account_file"):
            with patch("app.routes.build", return_value=mock_sheets_service):
                response = client.get(
                    "/projetos",
                    headers={"x-api-key": api_key}
                )
                assert response.status_code == 200
                data = response.json()
                assert len(data) == len(mock_projects)

    def test_listar_projetos_com_filtro_status(
        self, client: TestClient, api_key: str, mock_sheets_service
    ) -> None:
        """Testa listar projetos filtrados por status."""
        with patch("app.routes.service_account.Credentials.from_service_account_file"):
            with patch("app.routes.build", return_value=mock_sheets_service):
                response = client.get(
                    "/projetos?status=Ativo",
                    headers={"x-api-key": api_key}
                )
                assert response.status_code == 200
                data = response.json()
                # Deve ter apenas projetos com status "Ativo"
                for projeto in data:
                    assert projeto["Status da Usina"] == "Ativo"

    def test_listar_projetos_com_filtro_vendedor(
        self, client: TestClient, api_key: str, mock_sheets_service
    ) -> None:
        """Testa listar projetos filtrados por vendedor."""
        with patch("app.routes.service_account.Credentials.from_service_account_file"):
            with patch("app.routes.build", return_value=mock_sheets_service):
                response = client.get(
                    "/projetos?vendedor=João%20Silva",
                    headers={"x-api-key": api_key}
                )
                assert response.status_code == 200
                data = response.json()
                # Deve ter 2 projetos de João Silva
                assert len(data) == 2

    def test_listar_projetos_case_insensitive(
        self, client: TestClient, api_key: str, mock_sheets_service
    ) -> None:
        """Testa que filtros são case-insensitive."""
        with patch("app.routes.service_account.Credentials.from_service_account_file"):
            with patch("app.routes.build", return_value=mock_sheets_service):
                response = client.get(
                    "/projetos?status=ativo",  # minúsculo
                    headers={"x-api-key": api_key}
                )
                assert response.status_code == 200
                data = response.json()
                for projeto in data:
                    assert projeto["Status da Usina"].lower() == "ativo"

    def test_resumo_endpoint(
        self, client: TestClient, api_key: str, mock_sheets_service
    ) -> None:
        """Testa endpoint de resumo agregado."""
        with patch("app.routes.service_account.Credentials.from_service_account_file"):
            with patch("app.routes.build", return_value=mock_sheets_service):
                response = client.get(
                    "/resumo",
                    headers={"x-api-key": api_key}
                )
                assert response.status_code == 200
                data = response.json()

                # Verificar estrutura de resposta
                assert "total_projetos" in data
                assert "por_status" in data
                assert "por_vendedor" in data
                assert "cache" in data

                # Verificar dados
                assert data["total_projetos"] == 3
                assert "Ativo" in data["por_status"]
                assert "João Silva" in data["por_vendedor"]


class TestCacheEndpoint:
    """Testes do endpoint de gerenciamento de cache."""

    def test_refresh_cache_sem_autenticacao(self, client: TestClient) -> None:
        """Testa que refresh cache requer autenticação."""
        response = client.post("/cache/refresh")
        assert response.status_code == 403

    def test_refresh_cache_com_api_key(
        self, client: TestClient, api_key: str, mock_sheets_service
    ) -> None:
        """Testa refresh de cache com autenticação."""
        with patch("app.routes.service_account.Credentials.from_service_account_file"):
            with patch("app.routes.build", return_value=mock_sheets_service):
                response = client.post(
                    "/cache/refresh",
                    headers={"x-api-key": api_key}
                )
                assert response.status_code == 200
                assert "sucesso" in response.json()["detail"].lower()


class TestRateLimiting:
    """Testes de rate limiting."""

    def test_projeto_rate_limit(
        self, client: TestClient, api_key: str, mock_sheets_service
    ) -> None:
        """Testa rate limiting do endpoint /projeto."""
        with patch("app.routes.service_account.Credentials.from_service_account_file"):
            with patch("app.routes.build", return_value=mock_sheets_service):
                # Fazer 11 requisições (limite é 10/minuto)
                for i in range(11):
                    response = client.get(
                        "/projeto/1010",
                        headers={"x-api-key": api_key}
                    )
                    if i < 10:
                        assert response.status_code == 200
                    else:
                        # 11ª requisição deve ser rate limited
                        assert response.status_code == 429
