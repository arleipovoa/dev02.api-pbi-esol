"""
Pydantic models para validação e documentação de requisições/respostas.
Melhora o esquema OpenAPI para integração com OpenAI Custom Actions.
"""
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, RootModel


# ========================
# Response Models
# ========================

class HealthCheckResponse(BaseModel):
    """Resposta do health check da API."""

    status: str = Field(..., description="Status da API (sempre 'ok')")
    cache_ttl_seconds: int = Field(..., description="TTL do cache em segundos")
    cached_items: int = Field(..., description="Número de itens em cache")

    class Config:
        json_schema_extra = {
            "example": {
                "status": "ok",
                "cache_ttl_seconds": 60,
                "cached_items": 42,
            }
        }


class ProjectResponse(BaseModel):
    """Dados de um projeto individual."""

    P: str = Field(..., description="Número/ID do projeto")
    Projeto: str = Field(..., description="Nome do projeto")
    Status_da_Usina: Optional[str] = Field(
        None,
        alias="Status da Usina",
        description="Status atual do projeto"
    )
    Vendedor: Optional[str] = Field(None, description="Responsável comercial/vendedor")
    Valor: Optional[str] = Field(None, description="Valor do projeto")

    # Campos adicionais que possam vir da planilha
    extra: Dict[str, Any] = Field(default_factory=dict, exclude=True)

    class Config:
        populate_by_name = True  # Aceita ambos os nomes (com e sem alias)
        json_schema_extra = {
            "example": {
                "P": "1010",
                "Projeto": "Solar Panel Installation",
                "Status da Usina": "Ativo",
                "Vendedor": "João Silva",
                "Valor": "50000",
            }
        }


class ProjectsListResponse(RootModel):
    """Lista de projetos."""

    root: List[Dict[str, Any]] = Field(
        ...,
        description="Lista de projetos com todos os seus atributos"
    )

    class Config:
        json_schema_extra = {
            "example": [
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
            ]
        }


class SummaryByStatus(RootModel):
    """Contagem de projetos por status."""

    root: Dict[str, int] = Field(
        ...,
        description="Status como chave, contagem como valor"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "Ativo": 25,
                "Proposta": 10,
                "Parado": 5,
                "Concluído": 2,
            }
        }


class SummaryByVendor(RootModel):
    """Contagem de projetos por vendedor."""

    root: Dict[str, int] = Field(
        ...,
        description="Nome do vendedor como chave, contagem como valor"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "João Silva": 20,
                "Maria Santos": 15,
                "Pedro Costa": 7,
            }
        }


class CacheInfo(BaseModel):
    """Informações sobre o cache."""

    ttl_seconds: int = Field(..., description="Tempo de vida do cache em segundos")
    last_refresh_epoch: float = Field(..., description="Timestamp do último refresh")
    cached_items: int = Field(..., description="Número de itens em cache")

    class Config:
        json_schema_extra = {
            "example": {
                "ttl_seconds": 60,
                "last_refresh_epoch": 1712254800.5,
                "cached_items": 42,
            }
        }


class SummaryResponse(BaseModel):
    """Resposta resumida com estatísticas agregadas."""

    total_projetos: int = Field(..., description="Número total de projetos")
    por_status: Dict[str, int] = Field(
        ...,
        description="Contagem de projetos por status"
    )
    por_vendedor: Dict[str, int] = Field(
        ...,
        description="Contagem de projetos por vendedor"
    )
    cache: CacheInfo = Field(..., description="Informações sobre o cache")

    class Config:
        json_schema_extra = {
            "example": {
                "total_projetos": 42,
                "por_status": {
                    "Ativo": 25,
                    "Proposta": 10,
                    "Parado": 5,
                    "Concluído": 2,
                },
                "por_vendedor": {
                    "João Silva": 20,
                    "Maria Santos": 15,
                    "Pedro Costa": 7,
                },
                "cache": {
                    "ttl_seconds": 60,
                    "last_refresh_epoch": 1712254800.5,
                    "cached_items": 42,
                },
            }
        }


class CacheRefreshResponse(BaseModel):
    """Resposta ao refresh de cache."""

    detail: str = Field(..., description="Mensagem de sucesso")

    class Config:
        json_schema_extra = {
            "example": {
                "detail": "Cache atualizado com sucesso"
            }
        }


class LocalityFilterResponse(BaseModel):
    """Resposta para filtro por localidade."""

    total_encontrados: int = Field(..., description="Total de projetos encontrados")
    projetos: List[Dict[str, Any]] = Field(
        ...,
        description="Lista de projetos que correspondem aos critérios"
    )
    filtros_aplicados: Dict[str, Optional[str]] = Field(
        ...,
        description="Filtros que foram aplicados na busca"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "total_encontrados": 5,
                "projetos": [
                    {
                        "P": "1010",
                        "Projeto": "Solar Panel Installation",
                        "Bairro": "Centro",
                        "Cidade": "Manhuaçu",
                        "Estado": "MG"
                    }
                ],
                "filtros_aplicados": {
                    "cidade": "Manhuaçu",
                    "estado": "MG",
                    "bairro": None,
                    "distrito": None
                }
            }
        }


class StatusFilterResponse(BaseModel):
    """Resposta para filtro por status."""

    total_encontrados: int = Field(..., description="Total de projetos encontrados")
    status_filtro: List[str] = Field(..., description="Status que foram filtrados")
    projetos: List[Dict[str, Any]] = Field(
        ...,
        description="Lista de projetos com os status especificados"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "total_encontrados": 49,
                "status_filtro": ["PENDÊNCIA", "AGUARDANDO", "MUITO ATRASADO"],
                "projetos": [
                    {
                        "P": "1010",
                        "Projeto": "Solar Panel Installation",
                        "Status da Usina": "PENDÊNCIA",
                        "Vendedor": "João Silva"
                    }
                ]
            }
        }


class CriticosResponse(BaseModel):
    """Resposta para projetos críticos/muito atrasados."""

    total_criticos: int = Field(..., description="Total de projetos muito atrasados")
    projetos: List[Dict[str, Any]] = Field(
        ...,
        description="Lista de projetos com status MUITO ATRASADO"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "total_criticos": 5,
                "projetos": [
                    {
                        "P": "1010",
                        "Projeto": "Solar Panel Installation",
                        "Status da Usina": "MUITO ATRASADO",
                        "Vendedor": "João Silva",
                        "Dias em atraso": 45
                    }
                ]
            }
        }


class ProjectDataResponse(BaseModel):
    """Resposta flexível para dados de projeto - aceita qualquer campo."""

    class Config:
        extra = "allow"
        json_schema_extra = {
            "example": {
                "p": "999",
                "Apelido da Usina": "Christiane Ferreira Ker",
                "Status da Usina": "EM OPERAÇÃO"
            }
        }


class ErrorResponse(BaseModel):
    """Resposta de erro padrão."""

    detail: str = Field(..., description="Descrição do erro")
    status_code: Optional[int] = Field(None, description="Código HTTP de erro")

    class Config:
        json_schema_extra = {
            "example": {
                "detail": "Projeto não encontrado",
                "status_code": 404,
            }
        }


# ========================
# Request Models
# ========================

class ListProjectsParams(BaseModel):
    """Parâmetros para listar projetos com filtros."""

    status: Optional[str] = Field(
        None,
        description="Filtrar por status do projeto (case-insensitive). Exemplos: 'Ativo', 'Proposta', 'Parado'",
        examples=["Ativo", "Proposta"]
    )
    vendedor: Optional[str] = Field(
        None,
        description="Filtrar por responsável/vendedor (case-insensitive). Exemplos: 'João Silva', 'Maria Santos'",
        examples=["João Silva", "Maria Santos"]
    )

    class Config:
        json_schema_extra = {
            "example": {
                "status": "Ativo",
                "vendedor": "João Silva",
            }
        }
