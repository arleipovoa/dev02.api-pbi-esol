"""
Módulo para integração com Google Sheets.
Nota: Este módulo está deprecado. Use app.routes para carregamento de dados.
"""
from google.oauth2 import service_account
from googleapiclient.discovery import build

from app.cache import cache
from app.config import settings


def _build_service():
    """Constrói o serviço de Sheets (privado)."""
    credentials = service_account.Credentials.from_service_account_file(
        settings.SERVICE_ACCOUNT_FILE, scopes=settings.SCOPES
    )
    return build("sheets", "v4", credentials=credentials)


def carregar_dados() -> list[dict]:
    """
    Carrega dados da planilha Google Sheets (DEPRECADO).

    Use app.routes.carregar_dados() em vez disso.

    Returns:
        Lista de projetos
    """
    if "dados" in cache:
        return cache["dados"]

    service = _build_service()
    sheet = service.spreadsheets()
    result = sheet.values().get(
        spreadsheetId=settings.SPREADSHEET_ID,
        range=settings.RANGE_NAME
    ).execute()

    values = result.get("values", [])

    headers = values[0]
    data = values[1:]

    projetos = [dict(zip(headers, row)) for row in data]

    cache["dados"] = projetos
    return projetos