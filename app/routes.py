"""
Rotas da API ESOL.
Define todos os endpoints da aplicação.
"""
from typing import Any, Optional
import time

from fastapi import APIRouter, Depends, HTTPException, Header, Query, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from slowapi import Limiter
from slowapi.util import get_remote_address
from google.oauth2 import service_account
from googleapiclient.discovery import build

from app.config import settings
from app.exceptions import ProjectNotFoundError, SheetsError
from app.logger import logger
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
    """Normaliza texto removendo espaços extras."""
    return str(valor).strip()


def obter_valor_canonico(projeto: dict[str, Any], campo_canonico: str) -> str:
    """Obtém valor do projeto usando aliases de coluna."""
    for alias in COLUMN_ALIASES.get(campo_canonico, []):
        valor = projeto.get(alias)
        if valor is not None and normalizar_texto(valor) != "":
            return normalizar_texto(valor)
    return ""


def carregar_dados_planilha() -> list[dict[str, Any]]:
    """Carrega dados da planilha Google Sheets."""
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
    """Carrega dados com cache TTL."""
    agora = time.time()
    if _cache["data"] is None or (agora - _cache["timestamp"]) > settings.CACHE_TTL_SECONDS:
        _cache["data"] = carregar_dados_planilha()
        _cache["timestamp"] = agora
        logger.debug("Cache atualizado")
    return _cache["data"]


def limpar_cache() -> None:
    """Limpa o cache."""
    _cache["data"] = None
    _cache["timestamp"] = 0.0


# 🔐 AUTENTICAÇÃO HÍBRIDA (JWT OU API KEY)
def auth(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    x_api_key: str = Header(None)
) -> bool:
    """Autentica usando JWT ou API Key."""
    # 1️⃣ Verifica JWT
    if credentials:
        payload = verify_jwt(credentials.credentials)
        if payload:
            return True

    # 2️⃣ Verifica API Key
    if x_api_key and verify_api_key(x_api_key):
        return True

    raise HTTPException(status_code=403, detail="Acesso não autorizado")


# ❤️ HEALTH CHECK
@router.get("/health")
@limiter.limit("30/minute")
def healthcheck(request: Request) -> dict[str, Any]:
    """Verifica saúde da API."""
    logger.info("Health check realizado")
    return {
        "status": "ok",
        "cache_ttl_seconds": settings.CACHE_TTL_SECONDS,
        "cached_items": len(_cache["data"] or []),
    }


# 🔄 ATUALIZAR CACHE
@router.post("/cache/refresh")
@limiter.limit("10/minute")
def atualizar_cache(
    request: Request,
    _: bool = Depends(auth)
) -> dict[str, str]:
    """Força atualização do cache."""
    logger.info("Cache refresh solicitado")
    limpar_cache()
    carregar_dados()
    logger.info("Cache atualizado com sucesso")
    return {"detail": "Cache atualizado com sucesso"}


# 🔎 BUSCAR PROJETO POR NÚMERO
@router.get("/projeto/{numero}")
@limiter.limit("10/minute")
def buscar_projeto(
    numero: int,
    request: Request,
    _: bool = Depends(auth)
) -> dict[str, Any]:
    """Busca projeto específico por número."""
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
@router.get("/projetos")
@limiter.limit("10/minute")
def listar_projetos(
    request: Request,
    status: Optional[str] = Query(None),
    vendedor: Optional[str] = Query(None),
    _: bool = Depends(auth)
) -> list[dict[str, Any]]:
    """Lista projetos com filtros opcionais."""
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


# 📊 RESUMO AGREGADO
@router.get("/resumo")
@limiter.limit("10/minute")
def resumo(
    request: Request,
    _: bool = Depends(auth)
) -> dict[str, Any]:
    """Retorna resumo de projetos agregados por status e vendedor."""
    projetos = carregar_dados()

    por_status: dict[str, int] = {}
    por_vendedor: dict[str, int] = {}

    for projeto in projetos:
        status = obter_valor_canonico(projeto, "status") or "Sem status"
        vendedor = obter_valor_canonico(projeto, "vendedor") or "Sem vendedor"

        por_status[status] = por_status.get(status, 0) + 1
        por_vendedor[vendedor] = por_vendedor.get(vendedor, 0) + 1

    return {
        "total_projetos": len(projetos),
        "por_status": dict(sorted(por_status.items())),
        "por_vendedor": dict(sorted(por_vendedor.items())),
        "cache": {
            "ttl_seconds": settings.CACHE_TTL_SECONDS,
            "last_refresh_epoch": _cache["timestamp"],
            "cached_items": len(_cache["data"] or []),
        },
    }