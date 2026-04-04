from google.oauth2 import service_account
from googleapiclient.discovery import build
import os
from dotenv import load_dotenv
from app.cache import cache

load_dotenv()

SCOPES = ['https://www.googleapis.com/auth/spreadsheets.readonly']
SERVICE_ACCOUNT_FILE = 'config/esol-pbi-api.json'
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")
RANGE_NAME = 'Projetos'

credentials = service_account.Credentials.from_service_account_file(
    SERVICE_ACCOUNT_FILE, scopes=SCOPES)

service = build('sheets', 'v4', credentials=credentials)

def carregar_dados():
    if "dados" in cache:
        return cache["dados"]

    sheet = service.spreadsheets()
    result = sheet.values().get(
        spreadsheetId=SPREADSHEET_ID,
        range=RANGE_NAME
    ).execute()

    values = result.get('values', [])

    headers = values[0]
    data = values[1:]

    projetos = [dict(zip(headers, row)) for row in data]

    cache["dados"] = projetos
    return projetos