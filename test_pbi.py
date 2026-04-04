from pathlib import Path

from google.oauth2 import service_account
from googleapiclient.discovery import build

SERVICE_ACCOUNT_FILE = str(Path(__file__).resolve().parent / "config" / "esol-pbi-api.json")
SCOPES = ['https://www.googleapis.com/auth/spreadsheets.readonly']

credentials = service_account.Credentials.from_service_account_file(
    SERVICE_ACCOUNT_FILE, scopes=SCOPES)

service = build('sheets', 'v4', credentials=credentials)

SPREADSHEET_ID = '1AFnXPQEfgBFOzbNrjqnhBiHrMxC-LLc9TyeTxZnPDJY'
RANGE_NAME = 'Projetos'

sheet = service.spreadsheets()
result = sheet.values().get(
    spreadsheetId=SPREADSHEET_ID,
    range=RANGE_NAME
).execute()

values = result.get('values', [])

headers = values[0]
data = values[1:]

def buscar_projeto(numero):
    for row in data:
        if row[0] == str(numero):
            return dict(zip(headers, row))
    return None

projeto = buscar_projeto(1010)

print(projeto)
