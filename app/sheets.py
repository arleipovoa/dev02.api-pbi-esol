"""
Módulo para integração com Google Sheets.
Focado em operações de escrita (Append e Update).
"""
from google.oauth2 import service_account
from googleapiclient.discovery import build
import os
import time
from dotenv import load_dotenv
from app.cache import cache

load_dotenv()

SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
SERVICE_ACCOUNT_FILE = 'config/esol-pbi-api.json'
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID", "1AFnXPQEfgBFOzbNrjqnhBiHrMxC-LLc9TyeTxZnPDJY")
RANGE_NAME = 'Projetos'


def _build_service():
    credentials = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=SCOPES
    )
    return build("sheets", "v4", credentials=credentials)


def _col_idx_to_letter(idx: int) -> str:
    """Converte índice 0-based para letra de coluna.
    0→A, 25→Z, 26→AA, 51→AZ, 93→CP, etc.
    """
    result = ""
    idx += 1
    while idx > 0:
        idx, rem = divmod(idx - 1, 26)
        result = chr(65 + rem) + result
    return result


def atualizar_projeto_sheet(numero: str, novos_dados: dict) -> bool:
    service = _build_service()
    sheet = service.spreadsheets()

    try:
        result = sheet.values().get(
            spreadsheetId=SPREADSHEET_ID,
            range=RANGE_NAME
        ).execute()
        values = result.get('values', [])
        if not values:
            return False
        headers = values[0]
        header_to_idx = {h.strip(): i for i, h in enumerate(headers)}
    except Exception:
        return False

    p_idx = header_to_idx.get("P")
    if p_idx is None:
        return False

    row_to_update = -1
    for i, row in enumerate(values[1:], start=2):
        if len(row) > p_idx and str(row[p_idx]).strip() == str(numero).strip():
            row_to_update = i
            break

    if row_to_update == -1:
        return False

    for col_name, value in novos_dados.items():
        if col_name in header_to_idx:
            c_idx = header_to_idx[col_name]
            col_letter = _col_idx_to_letter(c_idx)          # ← fix aqui
            update_range = f"{RANGE_NAME}!{col_letter}{row_to_update}"
            sheet.values().update(
                spreadsheetId=SPREADSHEET_ID,
                range=update_range,
                valueInputOption="USER_ENTERED",
                body={"values": [[str(value)]]}
            ).execute()

    return True


def criar_projeto_sheet(dados_novo: dict) -> bool:
    service = _build_service()
    sheet = service.spreadsheets()

    result = sheet.values().get(
        spreadsheetId=SPREADSHEET_ID,
        range=RANGE_NAME
    ).execute()
    values = result.get('values', [])
    if not values:
        return False

    headers = values[0]
    new_row = [""] * len(headers)
    for key, value in dados_novo.items():
        if key in headers:
            idx = headers.index(key)
            new_row[idx] = str(value)

    if "Data de Cadastro" in headers:
        idx = headers.index("Data de Cadastro")
        if not new_row[idx]:
            new_row[idx] = time.strftime("%Y-%m-%d %H:%M:%S")

    body = {"values": [new_row]}
    sheet.values().append(
        spreadsheetId=SPREADSHEET_ID,
        range=RANGE_NAME,
        valueInputOption="USER_ENTERED",
        insertDataOption="INSERT_ROWS",
        body=body
    ).execute()

    return True