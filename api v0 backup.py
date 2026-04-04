from pathlib import Path

from fastapi import FastAPI, HTTPException
from google.oauth2 import service_account
from googleapiclient.discovery import build

app = FastAPI(title="E-sol PBI API")

SERVICE_ACCOUNT_FILE = str(Path(__file__).resolve().parent / "config" / "esol-pbi-api.json")
SCOPES = ['https://www.googleapis.com/auth/spreadsheets.readonly']
SPREADSHEET_ID = '1AFnXPQEfgBFOzbNrjqnhBiHrMxC-LLc9TyeTxZnPDJY'
RANGE_NAME = 'Projetos'

credentials = service_account.Credentials.from_service_account_file(
    SERVICE_ACCOUNT_FILE, scopes=SCOPES)

service = build('sheets', 'v4', credentials=credentials)

def carregar_dados():
    sheet = service.spreadsheets()
    result = sheet.values().get(
        spreadsheetId=SPREADSHEET_ID,
        range=RANGE_NAME
    ).execute()

    values = result.get('values', [])

    headers = values[0]
    data = values[1:]

    projetos = []
    for row in data:
        projeto_dict = dict(zip(headers, row))
        projetos.append(projeto_dict)

    return projetos

@app.get("/projeto/{numero}")
def buscar_projeto(numero: int):
    projetos = carregar_dados()

    for projeto in projetos:
        if projeto.get("P") == str(numero):
            return projeto

    raise HTTPException(status_code=404, detail="Projeto não encontrado")

@app.get("/projetos")
def listar_projetos(status: str = None, vendedor: str = None):
    projetos = carregar_dados()

    if status:
        projetos = [p for p in projetos if p.get("Status da Usina") == status]

    if vendedor:
        projetos = [p for p in projetos if p.get("Vendedor") == vendedor]

    return projetos
