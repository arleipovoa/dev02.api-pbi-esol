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

# Lista canônica de instaladores (ordem fixa, mantendo acentos)
INSTALADORES = [
    "Elivelton", "Fábio", "Moisés", "Gabriel T", "Gabriel M", "Hyan",
    "Gustavo", "Kauã", "Gustavo P", "Enderson", "Flávio", "Ley", "Élder",
]

# Mapeamento de aliases de coluna para normalizar nomes
COLUMN_ALIASES = {
    "numero_projeto": ["P", "Projeto", "Número do Projeto", "Numero do Projeto", "Código", "Codigo"],
    "status": ["Status da Usina", "Status", "Situação", "Situacao"],
    "vendedor": ["Vendedor", "Consultor", "Responsável Comercial", "Responsavel Comercial"],
    "cidade": ["Cidade", "Municipio", "Município"],
    "bairro": ["Bairro"],
    "estado": ["UF", "Estado"],
}

# Cache
_cache: dict[str, Any] = {
    "data": None,
    "timestamp": 0.0,
}


def normalizar_texto(valor: Any) -> str:
    return str(valor).strip()


def obter_valor_canonico(projeto: dict[str, Any], campo_canonico: str) -> str:
    for alias in COLUMN_ALIASES.get(campo_canonico, []):
        valor = projeto.get(alias)
        if valor is not None and normalizar_texto(valor) != "":
            return normalizar_texto(valor)
    return ""


def carregar_dados_planilha() -> list[dict[str, Any]]:
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
    agora = time.time()
    if _cache["data"] is None or (agora - _cache["timestamp"]) > settings.CACHE_TTL_SECONDS:
        _cache["data"] = carregar_dados_planilha()
        _cache["timestamp"] = agora
        logger.debug("Cache atualizado")
    return _cache["data"]


def limpar_cache() -> None:
    _cache["data"] = None
    _cache["timestamp"] = 0.0
    logger.debug("Cache limpo")


# 🔐 AUTENTICAÇÃO HÍBRIDA (JWT OU API KEY)
def auth(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    x_api_key: str = Header(None)
) -> bool:
    if credentials:
        payload = verify_jwt(credentials.credentials)
        if payload:
            return True

    if x_api_key and verify_api_key(x_api_key):
        return True

    raise HTTPException(status_code=403, detail="Acesso não autorizado")


# ❤️ HEALTH CHECK
@router.get(
    "/health",
    response_model=HealthCheckResponse,
    summary="Health Check",
    tags=["Health"],
    operation_id="healthCheck",
)
@limiter.limit("30/minute")
def healthcheck(request: Request) -> HealthCheckResponse:
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
    tags=["Cache Management"],
    operation_id="refreshCache",
)
@limiter.limit("10/minute")
def atualizar_cache(
    request: Request,
    _: bool = Depends(auth)
) -> CacheRefreshResponse:
    limpar_cache()
    carregar_dados()
    return CacheRefreshResponse(detail="Cache atualizado com sucesso")


# 🔎 BUSCAR PROJETO POR NÚMERO
@router.get(
    "/projeto/{numero}",
    response_model=ProjectResponse,
    summary="Get Project",
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
    projetos = carregar_dados()

    for projeto in projetos:
        if obter_valor_canonico(projeto, "numero_projeto") == numero_str:
            return projeto

    raise HTTPException(status_code=404, detail="Projeto não encontrado")


# 📋 LISTAR PROJETOS COM FILTROS E PAGINAÇÃO
@router.get(
    "/projetos",
    summary="List Projects",
    description="Lista projetos com filtros opcionais e paginação. Retorna {total, data, limit, offset}.",
    tags=["Projects"],
    operation_id="listProjects",
)
@limiter.limit("10/minute")
def listar_projetos(
    request: Request,
    status: Optional[str] = Query(None, description="Filtrar por status (case-insensitive)."),
    vendedor: Optional[str] = Query(None, description="Filtrar por vendedor (case-insensitive)."),
    cidade: Optional[str] = Query(None, description="Filtrar por cidade (case-insensitive)."),
    limit: int = Query(default=1000, ge=1, le=2000, description="Máximo de itens por página."),
    offset: int = Query(default=0, ge=0, description="Itens a pular (paginação)."),
    _: bool = Depends(auth)
) -> dict[str, Any]:
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

    if cidade:
        cidade_norm = normalizar_texto(cidade).casefold()
        projetos = [
            p for p in projetos
            if obter_valor_canonico(p, "cidade").casefold() == cidade_norm
        ]

    total = len(projetos)
    paginated = projetos[offset: offset + limit]

    return {"total": total, "data": paginated, "limit": limit, "offset": offset}


# 📊 RESUMO / ESTATÍSTICAS
@router.get(
    "/resumo",
    response_model=SummaryResponse,
    summary="Summary Statistics",
    description="Retorna estatísticas agregadas: total de projetos, contagem por status e vendedor.",
    tags=["Projects"],
    operation_id="getSummary",
)
@limiter.limit("10/minute")
def resumo(
    request: Request,
    _: bool = Depends(auth)
) -> SummaryResponse:
    projetos = carregar_dados()

    por_status: dict[str, int] = {}
    por_vendedor: dict[str, int] = {}

    for p in projetos:
        s = obter_valor_canonico(p, "status") or "—"
        v = obter_valor_canonico(p, "vendedor") or "—"
        por_status[s] = por_status.get(s, 0) + 1
        por_vendedor[v] = por_vendedor.get(v, 0) + 1

    # Ordenar por contagem descendente
    por_status = dict(sorted(por_status.items(), key=lambda x: x[1], reverse=True))
    por_vendedor = dict(sorted(por_vendedor.items(), key=lambda x: x[1], reverse=True))

    return SummaryResponse(
        total_projetos=len(projetos),
        por_status=por_status,
        por_vendedor=por_vendedor,
        cache=CacheInfo(
            ttl_seconds=settings.CACHE_TTL_SECONDS,
            last_refresh_epoch=_cache["timestamp"],
            cached_items=len(_cache["data"] or []),
        ),
    )


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
    success = atualizar_projeto_sheet(str(numero), dados)

    if not success:
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
    try:
        numero_p = criar_projeto_sheet(dados)
        limpar_cache()
        return {"detail": "Projeto criado com sucesso", "numero_p": numero_p}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao criar projeto: {str(e)}")


# 📄 GERAR DOCUMENTOS (CONTRATO / PROCURAÇÃO) VIA APPS SCRIPT
@router.post(
    "/gerar-documentos/{numero}",
    summary="Generate Documents",
    tags=["Projects"],
)
@limiter.limit("5/minute")
def gerar_documentos(
    numero: int,
    request: Request,
    _: bool = Depends(auth),
):
    import os, re, httpx
    apps_script_url = os.getenv("APPS_SCRIPT_URL")
    if not apps_script_url:
        raise HTTPException(status_code=503, detail="APPS_SCRIPT_URL não configurada no servidor")

    # Busca os dados do projeto na planilha (via cache)
    projetos = carregar_dados()
    numero_str = str(numero)
    projeto_dados = None
    for p in projetos:
        cod = str(p.get("Código P") or p.get("P") or p.get("A2") or "").strip().lstrip("Pp")
        if cod == numero_str:
            projeto_dados = p
            break

    if projeto_dados is None:
        raise HTTPException(status_code=404, detail=f"Projeto {numero} não encontrado")

    # Limpa valores formatados pt-BR (ex: "R$ 23.000,00" → 23000.0)
    # A API lê FORMATTED_VALUE por padrão; o Apps Script precisa de números limpos.
    _CAMPOS_NUMERICOS = {
        "CAPEX", "Potência (kWp)", "Potência dos Módulos", "Potência Inversor",
        "Potência CA Total (kW)", "Geração Estimada (kWh/mês)",
        "Geração Média Espec. (kWh/mês/kWp)", "Qnt. de Módulos", "Qnt. Inversores",
    }
    projeto_dados = dict(projeto_dados)  # cópia para não alterar o cache
    for campo in _CAMPOS_NUMERICOS:
        val = projeto_dados.get(campo)
        if val is None or isinstance(val, (int, float)):
            continue
        if isinstance(val, str) and val.strip():
            # Remove tudo exceto dígitos, vírgula e sinal negativo
            limpo = re.sub(r'[^\d,-]', '', val).replace(',', '.')
            try:
                projeto_dados[campo] = float(limpo)
            except ValueError:
                pass

    # Chama o Apps Script Web App com os dados do projeto
    try:
        resp = httpx.post(
            apps_script_url,
            json={"numero": numero_str, "dados": projeto_dados},
            timeout=120.0,
            follow_redirects=True,
        )
        resp.raise_for_status()
        resultado = resp.json()
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Apps Script demorou muito para responder")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Erro ao chamar Apps Script: {str(e)}")

    if not resultado.get("success"):
        raise HTTPException(status_code=502, detail=resultado.get("error", "Erro no Apps Script"))

    # Salva as URLs geradas de volta na planilha
    urls = resultado.get("urls", {})
    if urls:
        from app.sheets import atualizar_projeto_sheet
        campos_url = {}
        if urls.get("contrato"):
            campos_url["URL Contrato"] = urls["contrato"]
        if urls.get("procuracao"):
            campos_url["URL Procuração"] = urls["procuracao"]
        if campos_url:
            atualizar_projeto_sheet(numero_str, campos_url)
            limpar_cache()

    return urls


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
    estado_norm = estado.strip().lower() if estado else None

    projetos_filtrados = []
    for projeto in projetos:
        if cidade_norm and obter_valor_canonico(projeto, "cidade").lower() != cidade_norm:
            continue
        if bairro_norm and obter_valor_canonico(projeto, "bairro").lower() != bairro_norm:
            continue
        if estado_norm and obter_valor_canonico(projeto, "estado").lower() != estado_norm:
            continue
        projetos_filtrados.append(projeto)

    return LocalityFilterResponse(
        total_encontrados=len(projetos_filtrados),
        projetos=projetos_filtrados,
        filtros_aplicados={"cidade": cidade, "bairro": bairro, "distrito": distrito, "estado": estado},
    )

import os

@router.get("/avaliacoes", tags=["Avaliações"])
@limiter.limit("10/minute")
def listar_avaliacoes(request: Request, _: bool = Depends(auth)):
    spreadsheet_id = os.getenv("1JVgAmMknpUlV7MHy1kkNJsmHnDibvSzHA2wp265bu2I")
    sheet_name = os.getenv("SHEET_NAME_AVALIACOES", "Avaliações")
    if not spreadsheet_id:
        raise HTTPException(status_code=500, detail="SPREADSHEET_ID_AVALIACOES não configurado")
    try:
        credentials = service_account.Credentials.from_service_account_file(
            settings.SERVICE_ACCOUNT_FILE, scopes=settings.SCOPES,
        )
        service = build("sheets", "v4", credentials=credentials)
        result = service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id, range=sheet_name
        ).execute()
        values = result.get("values", [])
        if not values:
            return {"total": 0, "data": []}
        headers = [str(h).strip() for h in values[0]]
        rows = [dict(zip(headers, row + [""] * (len(headers) - len(row)))) for row in values[1:]]
        return {"total": len(rows), "data": rows}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao ler avaliações: {str(e)}")



# 💰 TARIFAS — histórico anual lido da aba "Tarifa"
_tarifas_cache: dict[str, Any] = {"data": None, "timestamp": 0.0}
_TARIFAS_TTL_SECONDS = 3600  # 1h — tarifa muda 1x/ano


def _parse_tarifa_valor(raw: Any) -> Optional[float]:
    """Converte '  R$  1,02 ' → 1.02. Retorna None se não parsear."""
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        return float(raw)
    import re
    s = re.sub(r"[^\d,.\-]", "", str(raw)).replace(",", ".")
    try:
        return float(s) if s else None
    except ValueError:
        return None


@router.get(
    "/tarifas",
    summary="Histórico de tarifas de energia",
    description="Retorna {ano: tarifa_R$_kWh} lido da aba 'Tarifa'. Usado no cálculo de Economia Estimada.",
    tags=["Tarifas"],
    operation_id="getTarifas",
)
@limiter.limit("30/minute")
def listar_tarifas(request: Request, _: bool = Depends(auth)) -> dict:
    agora = time.time()
    if (
        _tarifas_cache["data"] is None
        or (agora - _tarifas_cache["timestamp"]) > _TARIFAS_TTL_SECONDS
    ):
        try:
            credentials = service_account.Credentials.from_service_account_file(
                settings.SERVICE_ACCOUNT_FILE, scopes=settings.SCOPES,
            )
            service = build("sheets", "v4", credentials=credentials)
            result = service.spreadsheets().values().get(
                spreadsheetId=settings.SPREADSHEET_ID, range="Tarifa!A1:B"
            ).execute()
            values = result.get("values", [])
            if not values or len(values) < 2:
                raise HTTPException(status_code=500, detail="Aba 'Tarifa' vazia ou sem dados")

            tarifas: dict[str, float] = {}
            # Primeira linha é cabeçalho; demais são (ano, valor)
            for row in values[1:]:
                if len(row) < 2:
                    continue
                ano_raw = str(row[0]).strip()
                tarifa = _parse_tarifa_valor(row[1])
                if not ano_raw or tarifa is None:
                    continue
                # ano pode vir como "2026" ou "2026.0"
                try:
                    ano = str(int(float(ano_raw)))
                except ValueError:
                    continue
                tarifas[ano] = tarifa

            _tarifas_cache["data"] = tarifas
            _tarifas_cache["timestamp"] = agora
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Erro ao ler aba Tarifa: {e}")
            raise HTTPException(status_code=500, detail=f"Erro ao ler tarifas: {str(e)}")

    return {"tarifas": _tarifas_cache["data"]}


# 👷 EQUIPE DE INSTALADORES — GET
@router.get(
    "/projeto/{numero}/equipe",
    summary="Get Project Team",
    description="Retorna {nome: bool} indicando quem está na equipe da obra.",
    tags=["Projects"],
    operation_id="getProjectTeam",
)
@limiter.limit("10/minute")
def get_equipe(
    numero: int = Path(..., description="Número do projeto", example=1044),
    request: Request = Request,
    _: bool = Depends(auth),
) -> dict:
    projetos = carregar_dados()
    numero_str = str(numero).strip()
    proj = next(
        (p for p in projetos if obter_valor_canonico(p, "numero_projeto") == numero_str),
        None,
    )
    if not proj:
        raise HTTPException(status_code=404, detail="Projeto não encontrado")
    return {
        nome: str(proj.get(f"Inst. {nome}", "")).strip().upper() == "TRUE"
        for nome in INSTALADORES
    }


# 👷 EQUIPE DE INSTALADORES — PUT
@router.put(
    "/projeto/{numero}/equipe",
    summary="Update Project Team",
    description=(
        "Recebe {nome: bool} e atualiza as colunas `Inst. *` correspondentes. "
        "Apenas nomes presentes no body são atualizados (campos ausentes ficam inalterados)."
    ),
    tags=["Projects"],
    operation_id="updateProjectTeam",
)
@limiter.limit("10/minute")
def set_equipe(
    numero: int,
    equipe: dict,
    request: Request,
    _: bool = Depends(auth),
):
    from app.sheets import atualizar_projeto_sheet

    novos = {}
    for nome in INSTALADORES:
        if nome in equipe:
            novos[f"Inst. {nome}"] = "TRUE" if equipe[nome] else ""

    if not novos:
        raise HTTPException(
            status_code=400, detail="Nenhum instalador válido informado"
        )

    success = atualizar_projeto_sheet(str(numero), novos)
    if not success:
        raise HTTPException(
            status_code=404, detail="Projeto não encontrado ou erro ao atualizar"
        )

    limpar_cache()
    return {"detail": "Equipe atualizada com sucesso", "atualizados": list(novos.keys())}


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


# 🗺️ GOOGLE MAPS — DISTANCE MATRIX PROXY
# Server-side proxy to Google Maps Distance Matrix API.
# Distance Matrix doesn't support browser CORS, so the frontend can't call it directly in production.
@router.get(
    "/gmaps/distancematrix",
    summary="Distance Matrix (Google Maps proxy)",
    tags=["Google Maps"],
    operation_id="gmapsDistanceMatrix",
)
@limiter.limit("60/minute")
async def gmaps_distance_matrix(
    request: Request,
    origins: str = Query(..., description="Origem (endereço, lat,lng ou plus code)"),
    destinations: str = Query(..., description="Destino (endereço ou lat,lng)"),
    units: str = Query("metric", description="metric ou imperial"),
    _: bool = Depends(auth),
):
    if not settings.GOOGLE_MAPS_API_KEY:
        raise HTTPException(
            status_code=503,
            detail="GOOGLE_MAPS_API_KEY não configurada no servidor",
        )
    import httpx
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                "https://maps.googleapis.com/maps/api/distancematrix/json",
                params={
                    "origins": origins,
                    "destinations": destinations,
                    "units": units,
                    "key": settings.GOOGLE_MAPS_API_KEY,
                },
            )
            resp.raise_for_status()
            return resp.json()
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Timeout ao consultar Google Maps")
    except httpx.HTTPError as e:
        logger.error(f"Erro ao chamar Google Distance Matrix: {e}")
        raise HTTPException(status_code=502, detail="Erro ao consultar Google Maps")


# 🔑 ADMIN — ALTERAR SENHA DE USUÁRIO (Supabase)
@router.put(
    "/admin/usuarios/{uid}/senha",
    summary="Admin: Change User Password",
    tags=["Admin"],
    operation_id="adminChangeUserPassword",
)
@limiter.limit("10/minute")
async def admin_change_password(
    uid: str,
    body: dict,
    request: Request,
    _: bool = Depends(auth),
):
    import httpx as _httpx
    supabase_url = settings.SUPABASE_URL
    service_role_key = settings.SUPABASE_SERVICE_ROLE_KEY
    if not supabase_url or not service_role_key:
        raise HTTPException(status_code=503, detail="Supabase admin não configurado no servidor")

    senha = body.get("senha", "").strip()
    if not senha:
        raise HTTPException(status_code=400, detail="Senha não informada")

    url = f"{supabase_url}/auth/v1/admin/users/{uid}"
    headers = {
        "apikey": service_role_key,
        "Authorization": f"Bearer {service_role_key}",
        "Content-Type": "application/json",
    }
    try:
        async with _httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.put(url, json={"password": senha}, headers=headers)
            if resp.status_code >= 400:
                body_err = resp.json() if resp.content else {}
                raise HTTPException(
                    status_code=resp.status_code,
                    detail=body_err.get("message", f"Supabase error {resp.status_code}"),
                )
    except _httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Timeout ao chamar Supabase Admin API")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Erro ao alterar senha: {str(e)}")

    return {"detail": "Senha alterada com sucesso"}


# 🔑 ADMIN — ATUALIZAR USUÁRIO COMPLETO (nome, email, area, senha)
@router.put(
    "/admin/usuarios/{uid}",
    summary="Admin: Update User",
    tags=["Admin"],
    operation_id="adminUpdateUser",
)
@limiter.limit("10/minute")
async def admin_update_user(
    uid: str,
    body: dict,
    request: Request,
    _: bool = Depends(auth),
):
    import httpx as _httpx
    supabase_url = settings.SUPABASE_URL
    service_role_key = settings.SUPABASE_SERVICE_ROLE_KEY
    if not supabase_url or not service_role_key:
        raise HTTPException(status_code=503, detail="Supabase admin não configurado")

    _headers = {
        "apikey": service_role_key,
        "Authorization": f"Bearer {service_role_key}",
        "Content-Type": "application/json",
    }

    try:
        async with _httpx.AsyncClient(timeout=15.0) as client:
            # 1. Update auth user (email and/or password)
            auth_payload: dict = {}
            if body.get("email"):
                auth_payload["email"] = body["email"].strip()
            if body.get("senha"):
                auth_payload["password"] = body["senha"].strip()
            if auth_payload:
                resp = await client.put(
                    f"{supabase_url}/auth/v1/admin/users/{uid}",
                    json=auth_payload,
                    headers=_headers,
                )
                if resp.status_code >= 400:
                    err = resp.json() if resp.content else {}
                    raise HTTPException(
                        status_code=resp.status_code,
                        detail=err.get("message", f"Supabase auth error {resp.status_code}"),
                    )

            # 2. Update profiles table
            profile_payload: dict = {}
            if "nome" in body:
                profile_payload["nome"] = body["nome"].strip()
            if "area" in body:
                profile_payload["area"] = body["area"].strip()
            if body.get("email"):
                profile_payload["email"] = body["email"].strip()
            if profile_payload:
                resp = await client.patch(
                    f"{supabase_url}/rest/v1/profiles?id=eq.{uid}",
                    json=profile_payload,
                    headers={**_headers, "Prefer": "return=minimal"},
                )
                if resp.status_code >= 400:
                    err = resp.json() if resp.content else {}
                    raise HTTPException(
                        status_code=resp.status_code,
                        detail=err.get("message", f"Supabase profiles error {resp.status_code}"),
                    )
    except _httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Timeout ao chamar Supabase")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Erro ao atualizar usuário: {str(e)}")

    return {"detail": "Usuário atualizado com sucesso"}


# 🗑️ ADMIN — EXCLUIR USUÁRIO (Supabase)
@router.delete(
    "/admin/usuarios/{uid}",
    summary="Admin: Delete User",
    tags=["Admin"],
    operation_id="adminDeleteUser",
)
@limiter.limit("10/minute")
async def admin_delete_user(
    uid: str,
    request: Request,
    _: bool = Depends(auth),
):
    import httpx as _httpx
    supabase_url = settings.SUPABASE_URL
    service_role_key = settings.SUPABASE_SERVICE_ROLE_KEY
    if not supabase_url or not service_role_key:
        raise HTTPException(status_code=503, detail="Supabase admin não configurado")

    _headers = {
        "apikey": service_role_key,
        "Authorization": f"Bearer {service_role_key}",
    }

    try:
        async with _httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.delete(
                f"{supabase_url}/auth/v1/admin/users/{uid}",
                headers=_headers,
            )
            if resp.status_code >= 400:
                err = resp.json() if resp.content else {}
                raise HTTPException(
                    status_code=resp.status_code,
                    detail=err.get("message", f"Supabase error {resp.status_code}"),
                )
    except _httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Timeout ao chamar Supabase")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Erro ao excluir usuário: {str(e)}")

    return {"detail": "Usuário excluído com sucesso"}
