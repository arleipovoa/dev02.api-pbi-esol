"""
Rotas da API ESOL.
Define todos os endpoints da aplicação.
"""
from typing import Any, Optional, List
import time

from fastapi import APIRouter, Depends, HTTPException, Header, Query, Request, Path
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from slowapi import Limiter
from slowapi.util import get_remote_address
from google.oauth2 import service_account
from googleapiclient.discovery import build

from app.config import settings
from app.exceptions import ProjectNotFoundError, SheetsError
from app.logger import logger
from app.models import (
    HealthCheckResponse,
    ProjectResponse,
    SummaryResponse,
    CacheRefreshResponse,
    CacheInfo,
    LocalityFilterResponse,
    StatusFilterResponse,
    CriticosResponse,
)
from app.security import verify_jwt, verify_api_key

router = APIRouter()
security = HTTPBearer(auto_error=False)

# Rate limiter
limiter = Limiter(key_func=get_remote_address)

# Mapeamento de aliases de coluna para normalizar nomes
COLUMN_ALIASES = {
    "numero_projeto": ["P", "Projeto", "Número do Projeto", "Numero do Projeto", "Código", "Codigo"],
    "status": ["Status da Usina", "Status", "Situação", "Situacao"],
    "vendedor": ["Vendedor", "Consultor", "Responsável Comercial", "Responsavel Comercial"],
}

# Cache
_cache: dict[str, Any] = {
    "data": None,
    "timestamp": 0.0,
}


def normalizar_texto(valor: Any) -> str:
    """
    Normaliza texto removendo espaços extras.

    Args:
        valor: Valor a normalizar (pode ser de qualquer tipo)

    Returns:
        String normalizada com espaços removidos
    """
    return str(valor).strip()


def obter_valor_canonico(projeto: dict[str, Any], campo_canonico: str) -> str:
    """
    Obtém valor do projeto usando aliases de coluna.

    Funcionalidade: permite buscar um campo do projeto usando múltiplos aliases.
    Por exemplo, a coluna "numero_projeto" pode ser chamada de "P", "Projeto",
    "Número do Projeto", etc. Esta função encontra o primeiro alias que existe.

    Args:
        projeto: Dicionário com dados do projeto
        campo_canonico: Nome canônico do campo (chave em COLUMN_ALIASES)

    Returns:
        Valor normalizado do campo, ou string vazia se não encontrado
    """
    for alias in COLUMN_ALIASES.get(campo_canonico, []):
        valor = projeto.get(alias)
        if valor is not None and normalizar_texto(valor) != "":
            return normalizar_texto(valor)
    return ""


def carregar_dados_planilha() -> list[dict[str, Any]]:
    """
    Carrega dados brutos da planilha Google Sheets.
    """
    try:
        credentials = service_account.Credentials.from_service_account_file(
            settings.SERVICE_ACCOUNT_FILE,
            scopes=settings.SCOPES,
        )
        service = build("sheets", "v4", credentials=credentials)
        sheet = service.spreadsheets()
        result = sheet.values().get(
            spreadsheetId=settings.SPREADSHEET_ID,
            range=settings.RANGE_NAME
        ).execute()

        values = result.get("values", [])
        if not values:
            logger.warning("Planilha vazia ou sem dados")
            return []

        headers = [normalizar_texto(h) for h in values[0]]
        data = values[1:]

        projetos: list[dict[str, Any]] = []
        for row in data:
            row_padded = row + [""] * (len(headers) - len(row))
            projeto_dict = dict(zip(headers, row_padded))
            projetos.append(projeto_dict)

        logger.debug(f"Carregados {len(projetos)} projetos da planilha")
        return projetos
    except Exception as e:
        logger.error(f"Erro ao carregar dados da planilha: {e}")
        raise SheetsError(f"Erro ao carregar dados: {str(e)}")


def carregar_dados() -> list[dict[str, Any]]:
    """
    Carrega dados com cache TTL (Time To Live).
    """
    agora = time.time()
    if _cache["data"] is None or (agora - _cache["timestamp"]) > settings.CACHE_TTL_SECONDS:
        _cache["data"] = carregar_dados_planilha()
        _cache["timestamp"] = agora
        logger.debug("Cache atualizado")
    return _cache["data"]


def limpar_cache() -> None:
    """
    Limpa o cache forçando uma nova requisição na próxima chamada.
    """
    _cache["data"] = None
    _cache["timestamp"] = 0.0
    logger.debug("Cache limpo")


# 🔐 AUTENTICAÇÃO HÍBRIDA (JWT OU API KEY)
def auth(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    x_api_key: str = Header(None)
) -> bool:
    """
    Autentica requisição usando JWT ou API Key.
    """
    # 1️⃣ Verifica JWT
    if credentials:
        payload = verify_jwt(credentials.credentials)
        if payload:
            logger.debug("Autenticação JWT bem-sucedida")
            return True

    # 2️⃣ Verifica API Key
    if x_api_key and verify_api_key(x_api_key):
        logger.debug("Autenticação API Key bem-sucedida")
        return True

    logger.warning("Tentativa de autenticação falhou")
    raise HTTPException(status_code=403, detail="Acesso não autorizado")


# ❤️ HEALTH CHECK
@router.get(
    "/health",
    response_model=HealthCheckResponse,
    summary="Health Check",
    description="Verifica se a API está ativa e retorna informações sobre cache.",
    tags=["Health"],
    operation_id="healthCheck",
)
@limiter.limit("30/minute")
def healthcheck(request: Request) -> HealthCheckResponse:
    logger.info("Health check realizado")
    return HealthCheckResponse(
        status="ok",
        cache_ttl_seconds=settings.CACHE_TTL_SECONDS,
        cached_items=len(_cache["data"] or []),
    )


# 🔄 ATUALIZAR CACHE
@router.post(
    "/cache/refresh",
    response_model=CacheRefreshResponse,
    summary="Refresh Cache",
    description="Força a atualização do cache. Útil para sincronizar dados mais recentes.",
    tags=["Cache Management"],
    operation_id="refreshCache",
)
@limiter.limit("10/minute")
def atualizar_cache(
    request: Request,
    _: bool = Depends(auth)
) -> CacheRefreshResponse:
    logger.info("Cache refresh solicitado")
    limpar_cache()
    carregar_dados()
    logger.info("Cache atualizado com sucesso")
    return CacheRefreshResponse(detail="Cache atualizado com sucesso")


# 🔎 BUSCAR PROJETO POR NÚMERO
@router.get(
    "/projeto/{numero}",
    response_model=ProjectResponse,
    summary="Get Project",
    description="Busca um projeto específico pelo seu número/ID.",
    tags=["Projects"],
    operation_id="getProject",
)
@limiter.limit("10/minute")
def buscar_projeto(
    numero: int = Path(..., description="Número ou ID do projeto", example=1010),
    request: Request = Request,
    _: bool = Depends(auth),
) -> dict[str, Any]:
    numero_str = str(numero).strip()
    logger.debug(f"Buscando projeto {numero_str}")
    projetos = carregar_dados()

    for projeto in projetos:
        if obter_valor_canonico(projeto, "numero_projeto") == numero_str:
            logger.info(f"Projeto {numero_str} encontrado")
            return projeto

    logger.warning(f"Projeto {numero_str} não encontrado")
    raise HTTPException(status_code=404, detail="Projeto não encontrado")


# 📋 LISTAR PROJETOS COM FILTROS
@router.get(
    "/projetos",
    response_model=List[ProjectResponse],
    summary="List Projects",
    description="Lista todos os projetos com filtros opcionais por status e vendedor.",
    tags=["Projects"],
    operation_id="listProjects",
)
@limiter.limit("10/minute")
def listar_projetos(
    request: Request,
    status: Optional[str] = Query(
        None,
        description="Filtrar por status do projeto (case-insensitive).",
        example="Ativo"
    ),
    vendedor: Optional[str] = Query(
        None,
        description="Filtrar por responsável/vendedor (case-insensitive).",
        example="João Silva"
    ),
    _: bool = Depends(auth)
) -> List[dict[str, Any]]:
    logger.debug(f"Listando projetos com filtros: status={status}, vendedor={vendedor}")
    projetos = carregar_dados()

    if status:
        status_norm = normalizar_texto(status).casefold()
        projetos = [
            p for p in projetos
            if obter_valor_canonico(p, "status").casefold() == status_norm
        ]

    if vendedor:
        vendedor_norm = normalizar_texto(vendedor).casefold()
        projetos = [
            p for p in projetos
            if obter_valor_canonico(p, "vendedor").casefold() == vendedor_norm
        ]

    return projetos


# 📝 ATUALIZAR STATUS/DADOS DO PROJETO
@router.put(
    "/projeto/{numero}",
    summary="Update Project",
    tags=["Projects"],
)
@limiter.limit("5/minute")
def atualizar_projeto(
    numero: int,
    dados: dict,
    request: Request,
    _: bool = Depends(auth)
):
    from app.sheets import atualizar_projeto_sheet
    logger.info(f"Solicitada atualização do projeto {numero}")
    success = atualizar_projeto_sheet(str(numero), dados)
    
    if not success:
        logger.error(f"Falha ao atualizar projeto {numero}")
        raise HTTPException(status_code=404, detail="Projeto não encontrado ou erro na planilha")
        
    limpar_cache()
    return {"detail": "Projeto atualizado com sucesso", "p": numero}


# ➕ CRIAR NOVO PROJETO
@router.post(
    "/projeto",
    summary="Create Project",
    tags=["Projects"],
)
@limiter.limit("5/minute")
def criar_projeto(
    dados: dict,
    request: Request,
    _: bool = Depends(auth)
):
    from app.sheets import criar_projeto_sheet
    logger.info("Solicitada criação de novo projeto")
    try:
        criar_projeto_sheet(dados)
        limpar_cache()
        return {"detail": "Projeto criado com sucesso"}
    except Exception as e:
        logger.error(f"Erro ao criar projeto: {e}")
        raise HTTPException(status_code=500, detail=f"Erro ao criar projeto: {str(e)}")


# 🗺️ FILTRAR PROJETOS POR LOCALIDADE
@router.get(
    "/projetos/por-localidade",
    response_model=LocalityFilterResponse,
    summary="Filter Projects by Locality",
    tags=["Projects"],
)
@limiter.limit("10/minute")
def filtrar_por_localidade(
    request: Request,
    cidade: Optional[str] = Query(None),
    bairro: Optional[str] = Query(None),
    distrito: Optional[str] = Query(None),
    estado: Optional[str] = Query(None),
    _: bool = Depends(auth)
) -> LocalityFilterResponse:
    projetos = carregar_dados()
    cidade_norm = cidade.strip().lower() if cidade else None
    bairro_norm = bairro.strip().lower() if bairro else None
    distrito_norm = distrito.strip().lower() if distrito else None
    estado_norm = estado.strip().lower() if estado else None

    projetos_filtrados = []
    for projeto in projetos:
        if cidade_norm and obter_valor_canonico(projeto, "cidade").lower() != cidade_norm:
            continue
        if bairro_norm and obter_valor_canonico(projeto, "bairro").lower() != bairro_norm:
            continue
        if distrito_norm and obter_valor_canonico(projeto, "distrito").lower() != distrito_norm:
            continue
        if estado_norm and obter_valor_canonico(projeto, "estado").lower() != estado_norm:
            continue
        projetos_filtrados.append(projeto)

    return LocalityFilterResponse(
        total_encontrados=len(projetos_filtrados),
        projetos=projetos_filtrados,
        filtros_aplicados={"cidade": cidade, "bairro": bairro, "distrito": distrito, "estado": estado},
    )


# 🔴 FILTRAR POR STATUS
@router.get(
    "/projetos/por-status",
    response_model=StatusFilterResponse,
    summary="Filter Projects by Status",
    tags=["Projects"],
)
@limiter.limit("10/minute")
def filtrar_por_status(
    request: Request,
    status: List[str] = Query(...),
    _: bool = Depends(auth)
) -> StatusFilterResponse:
    projetos = carregar_dados()
    status_norm = [s.strip().upper() for s in status]
    projetos_filtrados = [
        p for p in projetos
        if obter_valor_canonico(p, "status").upper() in status_norm
    ]
    return StatusFilterResponse(
        total_encontrados=len(projetos_filtrados),
        status_filtro=status,
        projetos=projetos_filtrados,
    )
