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

# Abas adicionais onde inserir linha junto com "Projetos"
ABAS_EXTRAS = ("Fiscal", "OPEX", "NPS", "Mídias")


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


def criar_projeto_sheet(dados_novo: dict) -> int:
    """
    Insere novo projeto na linha 2 (após cabeçalho) e retorna o número P atribuído.

    Abordagem:
      1. Insere linha em branco na posição 2 em Projetos + abas extras
      2. Copia FÓRMULAS da row 3 para row 2 em Projetos (preserva fórmulas calculadas)
      3. Copia TUDO da row 3 para row 2 nas abas extras (Fiscal, OPEX, NPS, Mídias)
      4. Escreve apenas as células de dados (batchUpdate individual — não sobrescreve fórmulas)
    """
    service = _build_service()
    sheet = service.spreadsheets()

    # ── 1. Obter cabeçalhos e dados existentes ──────────────────────────────────
    result = sheet.values().get(
        spreadsheetId=SPREADSHEET_ID,
        range=RANGE_NAME
    ).execute()
    values = result.get('values', [])
    if not values:
        raise ValueError("Planilha vazia ou sem cabecalho")

    headers = values[0]
    header_to_idx = {h.strip(): i for i, h in enumerate(headers)}
    num_cols = len(headers)

    # ── 2. Calcular próximo número P (para retorno — célula usará fórmula) ──────
    p_col_idx = None
    for candidate in ("Código P", "P", "Codigo P", "A2"):
        if candidate in header_to_idx:
            p_col_idx = header_to_idx[candidate]
            break

    next_p = 1
    if p_col_idx is not None:
        p_values = []
        for row in values[1:]:
            if len(row) > p_col_idx:
                raw = str(row[p_col_idx]).strip().lstrip("Pp")
                try:
                    p_values.append(int(raw))
                except ValueError:
                    pass
        if p_values:
            next_p = max(p_values) + 1

    # ── 3. Descobrir sheetIds de todas as abas ──────────────────────────────────
    meta = service.spreadsheets().get(spreadsheetId=SPREADSHEET_ID).execute()
    sheets_meta = {}
    for s in meta.get('sheets', []):
        props = s['properties']
        sheets_meta[props['title']] = {
            'sheetId': props['sheetId'],
            'cols': props.get('gridProperties', {}).get('columnCount', 100),
        }

    projetos_meta = sheets_meta.get(RANGE_NAME)
    if projetos_meta is None:
        raise ValueError(f"Aba '{RANGE_NAME}' nao encontrada")

    # ── 4. Batch requests: inserir linhas + copiar fórmulas ─────────────────────
    requests = []

    # Projetos: inserir linha 2 + copiar FÓRMULAS de row 3
    requests.append({
        "insertDimension": {
            "range": {
                "sheetId": projetos_meta['sheetId'],
                "dimension": "ROWS",
                "startIndex": 1,
                "endIndex": 2,
            },
            "inheritFromBefore": False,
        }
    })
    requests.append({
        "copyPaste": {
            "source": {
                "sheetId": projetos_meta['sheetId'],
                "startRowIndex": 2, "endRowIndex": 3,
                "startColumnIndex": 0, "endColumnIndex": num_cols,
            },
            "destination": {
                "sheetId": projetos_meta['sheetId'],
                "startRowIndex": 1, "endRowIndex": 2,
                "startColumnIndex": 0, "endColumnIndex": num_cols,
            },
            "pasteType": "PASTE_FORMULA",
        }
    })

    # Abas extras: inserir linha 2 + copiar TUDO (fórmulas + dados) de row 3
    for aba_name in ABAS_EXTRAS:
        if aba_name not in sheets_meta:
            continue
        aba = sheets_meta[aba_name]
        requests.append({
            "insertDimension": {
                "range": {
                    "sheetId": aba['sheetId'],
                    "dimension": "ROWS",
                    "startIndex": 1,
                    "endIndex": 2,
                },
                "inheritFromBefore": False,
            }
        })
        requests.append({
            "copyPaste": {
                "source": {
                    "sheetId": aba['sheetId'],
                    "startRowIndex": 2, "endRowIndex": 3,
                    "startColumnIndex": 0, "endColumnIndex": aba['cols'],
                },
                "destination": {
                    "sheetId": aba['sheetId'],
                    "startRowIndex": 1, "endRowIndex": 2,
                    "startColumnIndex": 0, "endColumnIndex": aba['cols'],
                },
                "pasteType": "PASTE_NORMAL",
            }
        })

    service.spreadsheets().batchUpdate(
        spreadsheetId=SPREADSHEET_ID,
        body={"requests": requests}
    ).execute()

    # ── 5. Escrever dados nas células específicas (preserva fórmulas) ───────────
    batch_data = []
    written_indices = set()

    for key, value in dados_novo.items():
        if key in header_to_idx:
            c_idx = header_to_idx[key]
            col_letter = _col_letter(c_idx)
            batch_data.append({
                "range": f"{RANGE_NAME}!{col_letter}2",
                "values": [[str(value)]]
            })
            written_indices.add(c_idx)

    # Data de Cadastro (se não veio no payload)
    if "Data de Cadastro" in header_to_idx:
        ts_idx = header_to_idx["Data de Cadastro"]
        if ts_idx not in written_indices:
            ts_col = _col_letter(ts_idx)
            batch_data.append({
                "range": f"{RANGE_NAME}!{ts_col}2",
                "values": [[time.strftime("%Y-%m-%d %H:%M:%S")]]
            })

    if batch_data:
        sheet.values().batchUpdate(
            spreadsheetId=SPREADSHEET_ID,
            body={"valueInputOption": "USER_ENTERED", "data": batch_data}
        ).execute()

    return next_p
