from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from google.oauth2 import service_account
from googleapiclient.discovery import build

app = FastAPI(title="E-sol PBI API")

SERVICE_ACCOUNT_FILE = str(Path(__file__).resolve().parent / "config" / "esol-pbi-api.json")
SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
SPREADSHEET_ID = "1AFnXPQEfgBFOzbNrjqnhBiHrMxC-LLc9TyeTxZnPDJY"
RANGE_NAME = "Projetos"

# Segurança simples via header x-api-key.
# Defina no ambiente do servidor:
# export ESOL_API_KEY="sua-chave-forte-aqui"
API_KEY = os.getenv("ESOL_API_KEY")
CACHE_TTL_SECONDS = int(os.getenv("CACHE_TTL_SECONDS", "60"))

credentials = service_account.Credentials.from_service_account_file(
    SERVICE_ACCOUNT_FILE,
    scopes=SCOPES,
)

service = build("sheets", "v4", credentials=credentials)

# Mapeamento interno para reduzir dependência direta do nome exato das colunas da planilha.
COLUMN_ALIASES = {
    "numero_projeto": ["P", "Projeto", "Número do Projeto", "Numero do Projeto", "Código", "Codigo"],
    "status": ["Status da Usina", "Status", "Situação", "Situacao"],
    "vendedor": ["Vendedor", "Consultor", "Responsável Comercial", "Responsavel Comercial"],
}

_cache: dict[str, Any] = {
    "data": None,
    "timestamp": 0.0,
}


def verificar_api_key(x_api_key: str | None = Header(default=None)) -> None:
    """
    Proteção simples por API key.
    Se ESOL_API_KEY não estiver definida, a API continua aberta para facilitar desenvolvimento local.
    """
    if not API_KEY:
        return

    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Não autorizado")


def normalizar_texto(valor: Any) -> str:
    return str(valor).strip()


def obter_valor_canonico(projeto: dict[str, Any], campo_canonico: str) -> str:
    for alias in COLUMN_ALIASES.get(campo_canonico, []):
        valor = projeto.get(alias)
        if valor is not None and normalizar_texto(valor) != "":
            return normalizar_texto(valor)
    return ""


def carregar_dados_planilha() -> list[dict[str, Any]]:
    sheet = service.spreadsheets()
    result = sheet.values().get(
        spreadsheetId=SPREADSHEET_ID,
        range=RANGE_NAME
    ).execute()

    values = result.get("values", [])
    if not values:
        return []

    headers = [normalizar_texto(h) for h in values[0]]
    data = values[1:]

    projetos: list[dict[str, Any]] = []
    for row in data:
        # Completa a linha para garantir alinhamento com os headers.
        row_padded = row + [""] * (len(headers) - len(row))
        projeto_dict = dict(zip(headers, row_padded))
        projetos.append(projeto_dict)

    return projetos


def carregar_dados() -> list[dict[str, Any]]:
    agora = time.time()
    if _cache["data"] is None or (agora - _cache["timestamp"]) > CACHE_TTL_SECONDS:
        _cache["data"] = carregar_dados_planilha()
        _cache["timestamp"] = agora
    return _cache["data"]


def limpar_cache() -> None:
    _cache["data"] = None
    _cache["timestamp"] = 0.0


@app.get("/health")
def healthcheck() -> dict[str, Any]:
    return {
        "status": "ok",
        "cache_ttl_seconds": CACHE_TTL_SECONDS,
        "api_key_protegida": bool(API_KEY),
    }


@app.post("/cache/refresh")
def atualizar_cache(_: None = Depends(verificar_api_key)) -> dict[str, str]:
    limpar_cache()
    carregar_dados()
    return {"detail": "Cache atualizado com sucesso"}


@app.get("/projeto/{numero}")
def buscar_projeto(numero: int, _: None = Depends(verificar_api_key)) -> dict[str, Any]:
    numero_str = str(numero).strip()
    projetos = carregar_dados()

    for projeto in projetos:
        if obter_valor_canonico(projeto, "numero_projeto") == numero_str:
            return projeto

    raise HTTPException(status_code=404, detail="Projeto não encontrado")


@app.get("/projetos")
def listar_projetos(
    status: str | None = Query(default=None),
    vendedor: str | None = Query(default=None),
    _: None = Depends(verificar_api_key),
) -> list[dict[str, Any]]:
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


@app.get("/resumo")
def resumo(_: None = Depends(verificar_api_key)) -> dict[str, Any]:
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
            "ttl_seconds": CACHE_TTL_SECONDS,
            "last_refresh_epoch": _cache["timestamp"],
            "cached_items": len(_cache["data"] or []),
        },
    }
