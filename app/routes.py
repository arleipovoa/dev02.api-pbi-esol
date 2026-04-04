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

    Examples:
        # Se projeto tem coluna "P"
        obter_valor_canonico(projeto, "numero_projeto")  # -> valor de "P"

        # Se projeto tem coluna "Status"
        obter_valor_canonico(projeto, "status")  # -> valor de "Status"
    """
    for alias in COLUMN_ALIASES.get(campo_canonico, []):
        valor = projeto.get(alias)
        if valor is not None and normalizar_texto(valor) != "":
            return normalizar_texto(valor)
    return ""


def carregar_dados_planilha() -> list[dict[str, Any]]:
    """
    Carrega dados brutos da planilha Google Sheets.

    Conecta-se à API de Google Sheets usando credenciais de Service Account
    e retorna os dados da aba especificada (RANGE_NAME).

    Returns:
        Lista de dicionários, cada um representando uma linha da planilha
        com headers como chaves

    Raises:
        SheetsError: Se houver erro ao acessar a planilha

    Note:
        Esta função faz uma conexão real com Google Sheets. Use com cuidado
        em testes pois pode ser lenta. Para testes, considere mockar.
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

    Mantém os dados em cache na memória e só faz uma nova requisição
    ao Google Sheets se o tempo de vida do cache expirou.

    Returns:
        Lista de projetos com cache

    Note:
        O tempo de TTL é configurável via CACHE_TTL_SECONDS
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

    Útil para forçar uma sincronização com os dados mais recentes da planilha.
    Normalmente chamado pelo endpoint POST /cache/refresh.
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

    Suporta dois métodos de autenticação:
    1. JWT via header Authorization: Bearer <token>
    2. API Key via header x-api-key: <key>

    Args:
        credentials: Credenciais JWT opcionais via Security
        x_api_key: API Key opcional via header

    Returns:
        True se autenticado com sucesso

    Raises:
        HTTPException: Status 403 se autenticação falhar

    Examples:
        # Com JWT
        Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...

        # Com API Key
        x-api-key: sua-chave-api-aqui
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
    """
    Verifica saúde da API.

    Endpoint público (sem autenticação necessária) que retorna o status
    da API e informações sobre o cache.

    Returns:
        HealthCheckResponse com status, TTL do cache e itens em cache
    """
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
    """
    Força atualização do cache.

    Endpoint protegido que limpa o cache em memória, forçando uma nova
    leitura dos dados da planilha Google Sheets na próxima requisição.

    Autenticação:
        - JWT: Header Authorization: Bearer <token>
        - API Key: Header x-api-key: <key>

    Returns:
        CacheRefreshResponse com mensagem de sucesso
    """
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
    """
    Busca projeto específico por número.

    Retorna todos os dados do projeto correspondente ao número fornecido.
    A busca é case-insensitive e normaliza os valores.

    Path Parameters:
        numero: Número do projeto (inteiro)

    Autenticação:
        - JWT: Header Authorization: Bearer <token>
        - API Key: Header x-api-key: <key>

    Returns:
        Dicionário com todos os dados do projeto

    Raises:
        404: Projeto não encontrado
    """
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
        description="Filtrar por status do projeto (case-insensitive). Exemplos: 'Ativo', 'Proposta', 'Parado'",
        example="Ativo"
    ),
    vendedor: Optional[str] = Query(
        None,
        description="Filtrar por responsável/vendedor (case-insensitive). Exemplos: 'João Silva', 'Maria Santos'",
        example="João Silva"
    ),
    _: bool = Depends(auth)
) -> List[dict[str, Any]]:
    """
    Lista projetos com filtros opcionais.

    Retorna lista de todos os projetos ou subconjunto filtrado.
    Ambos os filtros são case-insensitive e podem ser combinados.

    Query Parameters:
        status: Filtro por status (opcional, case-insensitive)
        vendedor: Filtro por vendedor (opcional, case-insensitive)

    Autenticação:
        - JWT: Header Authorization: Bearer <token>
        - API Key: Header x-api-key: <key>

    Returns:
        Lista de projetos que correspondem aos critérios

    Examples:
        GET /projetos - Retorna todos os projetos
        GET /projetos?status=Ativo - Apenas projetos ativos
        GET /projetos?vendedor=João%20Silva - Apenas de João
        GET /projetos?status=Ativo&vendedor=João - Ambos os filtros
    """
    logger.debug(f"Listando projetos com filtros: status={status}, vendedor={vendedor}")
    projetos = carregar_dados()

    if status:
        status_norm = normalizar_texto(status).casefold()
        projetos = [
            p for p in projetos
            if obter_valor_canonico(p, "status").casefold() == status_norm
        ]
        logger.debug(f"Filtro status aplicado: {len(projetos)} projetos encontrados")

    if vendedor:
        vendedor_norm = normalizar_texto(vendedor).casefold()
        projetos = [
            p for p in projetos
            if obter_valor_canonico(p, "vendedor").casefold() == vendedor_norm
        ]
        logger.debug(f"Filtro vendedor aplicado: {len(projetos)} projetos encontrados")

    logger.info(f"Retornando {len(projetos)} projetos")
    return projetos


# 🗺️ FILTRAR PROJETOS POR LOCALIDADE
@router.get(
    "/projetos/por-localidade",
    response_model=LocalityFilterResponse,
    summary="Filter Projects by Locality",
    description="Filtra projetos por cidade, bairro, distrito e/ou estado.",
    tags=["Projects"],
    operation_id="filterProjectsByLocality",
)
@limiter.limit("10/minute")
def filtrar_por_localidade(
    request: Request,
    cidade: Optional[str] = Query(
        None,
        description="Filtrar por cidade (case-insensitive). Ex: 'Manhuaçu'"
    ),
    bairro: Optional[str] = Query(
        None,
        description="Filtrar por bairro (case-insensitive). Ex: 'Centro'"
    ),
    distrito: Optional[str] = Query(
        None,
        description="Filtrar por distrito (case-insensitive)"
    ),
    estado: Optional[str] = Query(
        None,
        description="Filtrar por estado/UF (case-insensitive). Ex: 'MG', 'SP'"
    ),
    _: bool = Depends(auth)
) -> LocalityFilterResponse:
    """
    Filtra projetos por localidade.

    Retorna lista de projetos que correspondem aos critérios de localização.
    Todos os filtros são case-insensitive e podem ser combinados.

    Query Parameters:
        cidade: Filtro por cidade (opcional)
        bairro: Filtro por bairro (opcional)
        distrito: Filtro por distrito (opcional)
        estado: Filtro por estado/UF (opcional)

    Autenticação:
        - JWT: Header Authorization: Bearer <token>
        - API Key: Header x-api-key: <key>

    Returns:
        LocalityFilterResponse com:
        - total_encontrados: Quantidade de projetos encontrados
        - projetos: Lista de projetos que correspondem aos critérios
        - filtros_aplicados: Resumo dos filtros utilizados

    Examples:
        GET /projetos/por-localidade?cidade=Manhuaçu
        GET /projetos/por-localidade?cidade=Manhuaçu&estado=MG
        GET /projetos/por-localidade?bairro=Centro&estado=MG
    """
    logger.debug(
        f"Filtrando projetos por localidade: "
        f"cidade={cidade}, bairro={bairro}, distrito={distrito}, estado={estado}"
    )
    projetos = carregar_dados()

    # Normalizar filtros
    cidade_norm = cidade.strip().lower() if cidade else None
    bairro_norm = bairro.strip().lower() if bairro else None
    distrito_norm = distrito.strip().lower() if distrito else None
    estado_norm = estado.strip().lower() if estado else None

    # Filtrar projetos
    projetos_filtrados = []
    for projeto in projetos:
        # Extrair e normalizar valores
        proj_cidade = obter_valor_canonico(projeto, "cidade")
        proj_bairro = obter_valor_canonico(projeto, "bairro")
        proj_distrito = obter_valor_canonico(projeto, "distrito")
        proj_estado = obter_valor_canonico(projeto, "estado")

        # Aplicar filtros (AND logic)
        if cidade_norm and proj_cidade != cidade_norm:
            continue
        if bairro_norm and proj_bairro != bairro_norm:
            continue
        if distrito_norm and proj_distrito != distrito_norm:
            continue
        if estado_norm and proj_estado != estado_norm:
            continue

        projetos_filtrados.append(projeto)

    logger.info(
        f"Filtro de localidade retornou {len(projetos_filtrados)} projetos"
    )

    return LocalityFilterResponse(
        total_encontrados=len(projetos_filtrados),
        projetos=projetos_filtrados,
        filtros_aplicados={
            "cidade": cidade,
            "bairro": bairro,
            "distrito": distrito,
            "estado": estado,
        },
    )


# 🔴 FILTRAR POR STATUS
@router.get(
    "/projetos/por-status",
    response_model=StatusFilterResponse,
    summary="Filter Projects by Status",
    description="Filtra projetos por um ou múltiplos status.",
    tags=["Projects"],
    operation_id="filterProjectsByStatus",
)
@limiter.limit("10/minute")
def filtrar_por_status(
    request: Request,
    status: List[str] = Query(
        ...,
        description="Status para filtrar (case-insensitive). Ex: 'EM OPERAÇÃO', 'PENDÊNCIA', 'AGUARDANDO', 'MUITO ATRASADO'. Pode informar múltiplos."
    ),
    _: bool = Depends(auth)
) -> StatusFilterResponse:
    """
    Filtra projetos por um ou múltiplos status.

    Retorna lista de projetos que correspondem aos status especificados.
    Status é case-insensitive.

    Query Parameters:
        status: Um ou múltiplos status para filtrar (obrigatório)
                Exemplos de valores válidos:
                - EM OPERAÇÃO
                - PENDÊNCIA
                - AGUARDANDO
                - MUITO ATRASADO
                - CONCLUÍDO
                - ATRASADO
                - EM ANDAMENTO
                - N/A

    Autenticação:
        - JWT: Header Authorization: Bearer <token>
        - API Key: Header x-api-key: <key>

    Returns:
        StatusFilterResponse com:
        - total_encontrados: Quantidade de projetos encontrados
        - status_filtro: Status que foram filtrados
        - projetos: Lista de projetos que correspondem aos critérios

    Examples:
        GET /projetos/por-status?status=EM OPERAÇÃO
        GET /projetos/por-status?status=PENDÊNCIA&status=AGUARDANDO
        GET /projetos/por-status?status=MUITO ATRASADO
    """
    logger.debug(f"Filtrando projetos por status: {status}")
    projetos = carregar_dados()

    # Normalizar filtros de status
    status_norm = [s.strip().upper() for s in status]

    # Filtrar projetos
    projetos_filtrados = []
    for projeto in projetos:
        proj_status = obter_valor_canonico(projeto, "status")
        if proj_status and proj_status.upper() in status_norm:
            projetos_filtrados.append(projeto)

    logger.info(f"Filtro de status retornou {len(projetos_filtrados)} projetos")

    return StatusFilterResponse(
        total_encontrados=len(projetos_filtrados),
        status_filtro=status,
        projetos=projetos_filtrados,
    )


# ⚠️ PROJETOS CRÍTICOS (MUITO ATRASADO)
@router.get(
    "/projetos/criticos",
    response_model=CriticosResponse,
    summary="Critical Projects",
    description="Retorna projetos em status MUITO ATRASADO (críticos para ação imediata).",
    tags=["Projects"],
    operation_id="getCriticalProjects",
)
@limiter.limit("10/minute")
def projetos_criticos(
    request: Request,
    _: bool = Depends(auth)
) -> CriticosResponse:
    """
    Retorna projetos críticos (MUITO ATRASADO).

    Identifica projetos que estão há muito tempo sem progresso.
    Estes são prioritários para ação gerencial.

    Autenticação:
        - JWT: Header Authorization: Bearer <token>
        - API Key: Header x-api-key: <key>

    Returns:
        CriticosResponse com:
        - total_criticos: Quantidade de projetos muito atrasados
        - projetos: Lista de projetos críticos

    Examples:
        GET /projetos/criticos
    """
    logger.debug("Buscando projetos críticos (MUITO ATRASADO)")
    projetos = carregar_dados()

    # Filtrar apenas projetos MUITO ATRASADO
    projetos_criticos_list = []
    for projeto in projetos:
        proj_status = obter_valor_canonico(projeto, "status")
        if proj_status and "MUITO ATRASADO" in proj_status.upper():
            projetos_criticos_list.append(projeto)

    logger.info(f"Encontrados {len(projetos_criticos_list)} projetos críticos")

    return CriticosResponse(
        total_criticos=len(projetos_criticos_list),
        projetos=projetos_criticos_list,
    )


# 🚨 PROJETOS TRAVADOS (PENDÊNCIA + AGUARDANDO + MUITO ATRASADO)
@router.get(
    "/projetos/travados",
    response_model=StatusFilterResponse,
    summary="Blocked Projects",
    description="Retorna projetos travados no funil (PENDÊNCIA, AGUARDANDO, MUITO ATRASADO).",
    tags=["Projects"],
    operation_id="getBlockedProjects",
)
@limiter.limit("10/minute")
def projetos_travados(
    request: Request,
    _: bool = Depends(auth)
) -> StatusFilterResponse:
    """
    Retorna projetos travados no funil de vendas.

    Identifica projetos que estão com progresso parado:
    - PENDÊNCIA: Aguardando ação de terceiros
    - AGUARDANDO: Aguardando etapa seguinte
    - MUITO ATRASADO: Já passou do prazo esperado

    Estes projetos representam dinheiro parado e requerem destravamento.

    Autenticação:
        - JWT: Header Authorization: Bearer <token>
        - API Key: Header x-api-key: <key>

    Returns:
        StatusFilterResponse com:
        - total_encontrados: Quantidade de projetos travados
        - status_filtro: Status que foram filtrados
        - projetos: Lista de projetos travados

    Examples:
        GET /projetos/travados
    """
    logger.debug("Buscando projetos travados")
    projetos = carregar_dados()

    status_travados = ["PENDÊNCIA", "AGUARDANDO", "MUITO ATRASADO"]

    # Filtrar projetos travados
    projetos_travados_list = []
    for projeto in projetos:
        proj_status = obter_valor_canonico(projeto, "status")
        if proj_status:
            for status_trav in status_travados:
                if status_trav in proj_status.upper():
                    projetos_travados_list.append(projeto)
                    break

    logger.info(f"Encontrados {len(projetos_travados_list)} projetos travados")

    return StatusFilterResponse(
        total_encontrados=len(projetos_travados_list),
        status_filtro=status_travados,
        projetos=projetos_travados_list,
    )


# 📊 RESUMO AGREGADO
@router.get(
    "/resumo",
    response_model=SummaryResponse,
    summary="Get Summary",
    description="Retorna um resumo agregado com estatísticas de projetos por status e vendedor.",
    tags=["Analytics"],
    operation_id="getSummary",
)
@limiter.limit("10/minute")
def resumo(
    request: Request,
    _: bool = Depends(auth)
) -> SummaryResponse:
    """
    Retorna resumo agregado de projetos.

    Fornece estatísticas gerais incluindo:
    - Total de projetos
    - Contagem por status (Ativo, Proposta, Parado, etc.)
    - Contagem por vendedor
    - Informações sobre cache

    Autenticação:
        - JWT: Header Authorization: Bearer <token>
        - API Key: Header x-api-key: <key>

    Returns:
        SummaryResponse com:
        - total_projetos: Número total de projetos
        - por_status: Contagem de projetos por status
        - por_vendedor: Contagem de projetos por vendedor
        - cache: TTL, timestamp do último refresh, itens em cache

    Examples:
        GET /resumo
        Response:
        {
            "total_projetos": 42,
            "por_status": {"Ativo": 30, "Parado": 12},
            "por_vendedor": {"João": 20, "Maria": 22},
            "cache": {
                "ttl_seconds": 60,
                "last_refresh_epoch": 1712254800.5,
                "cached_items": 42
            }
        }
    """
    logger.debug("Gerando resumo de projetos")
    projetos = carregar_dados()

    por_status: dict[str, int] = {}
    por_vendedor: dict[str, int] = {}

    for projeto in projetos:
        status = obter_valor_canonico(projeto, "status") or "Sem status"
        vendedor = obter_valor_canonico(projeto, "vendedor") or "Sem vendedor"

        por_status[status] = por_status.get(status, 0) + 1
        por_vendedor[vendedor] = por_vendedor.get(vendedor, 0) + 1

    return SummaryResponse(
        total_projetos=len(projetos),
        por_status=dict(sorted(por_status.items())),
        por_vendedor=dict(sorted(por_vendedor.items())),
        cache=CacheInfo(
            ttl_seconds=settings.CACHE_TTL_SECONDS,
            last_refresh_epoch=_cache["timestamp"],
            cached_items=len(_cache["data"] or []),
        ),
    )