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

def _col_letter(n: int) -> str:
    """Converte índice 0-based para letra(s) de coluna — suporta A-Z, AA-ZZ, etc."""
    s, n = "", n + 1
    while n:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


def atualizar_projeto_sheet(numero: str, novos_dados: dict) -> bool:
    """
    Atualiza um projeto na planilha Google Sheets.

    Busca o projeto pela coluna do código P e atualiza cada campo
    enviado no dicionário correspondente ao cabeçalho.
    """
    service = _build_service()
    sheet = service.spreadsheets()

    # 1. Recuperar cabeçalhos para mapeamento
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

    # 2. Encontrar a linha correta — a coluna pode se chamar "Código P" ou "P"
    p_idx = None
    for _key in ("Código P", "P", "Codigo P", "A2"):
        if _key in header_to_idx:
            p_idx = header_to_idx[_key]
            break
    if p_idx is None:
        return False

    # Strip "P" prefix from cell values when comparing (e.g. "P1046" → "1046")
    numero_normalizado = str(numero).strip().lstrip("Pp")

    row_to_update = -1
    for i, row in enumerate(values[1:], start=2):
        if len(row) > p_idx:
            cell = str(row[p_idx]).strip().lstrip("Pp")
            if cell == numero_normalizado:
                row_to_update = i
                break

    if row_to_update == -1:
        return False

    # 3. Atualizar todos os campos em um único batchUpdate (evita rate limit)
    batch_data = []
    for col_name, value in novos_dados.items():
        if col_name in header_to_idx:
            c_idx = header_to_idx[col_name]
            col_letter = _col_letter(c_idx)
            batch_data.append({
                "range": f"{RANGE_NAME}!{col_letter}{row_to_update}",
                "values": [[str(value)]]
            })

    if batch_data:
        sheet.values().batchUpdate(
            spreadsheetId=SPREADSHEET_ID,
            body={"valueInputOption": "USER_ENTERED", "data": batch_data}
        ).execute()

    return True


def criar_projeto_sheet(dados_novo: dict) -> bool:
    service = _build_service()
    sheet = service.spreadsheets()

    # 1. Obter cabeçalhos
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

    # 2. Descobrir o sheetId numérico da aba "Projetos"
    meta = service.spreadsheets().get(spreadsheetId=SPREADSHEET_ID).execute()
    sheet_id = None
    for s in meta.get('sheets', []):
        if s['properties']['title'] == RANGE_NAME:
            sheet_id = s['properties']['sheetId']
            break
    if sheet_id is None:
        return False

    # 3. Inserir linha em branco na posição 2 (índice 1, logo após o cabeçalho)
    #    inheritFromBefore=False → herda formatação/fórmulas da linha abaixo (row anterior row 2)
    service.spreadsheets().batchUpdate(
        spreadsheetId=SPREADSHEET_ID,
        body={
            "requests": [{
                "insertDimension": {
                    "range": {
                        "sheetId": sheet_id,
                        "dimension": "ROWS",
                        "startIndex": 1,
                        "endIndex": 2
                    },
                    "inheritFromBefore": False
                }
            }]
        }
    ).execute()

    # 4. Escrever os dados na nova linha 2
    col_end = _col_letter(len(headers) - 1)
    sheet.values().update(
        spreadsheetId=SPREADSHEET_ID,
        range=f"{RANGE_NAME}!A2:{col_end}2",
        valueInputOption="USER_ENTERED",
        body={"values": [new_row]}
    ).execute()

    return True