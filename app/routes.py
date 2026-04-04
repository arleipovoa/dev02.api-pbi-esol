from fastapi import APIRouter, Depends, HTTPException, Header, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.security import verify_jwt, verify_api_key
from app.sheets import carregar_dados

router = APIRouter()
security = HTTPBearer(auto_error=False)

# Rate limiter
limiter = Limiter(key_func=get_remote_address)


# 🔐 AUTENTICAÇÃO HÍBRIDA (JWT OU API KEY)
def auth(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    x_api_key: str = Header(None)
):
    # 1️⃣ Verifica JWT
    if credentials:
        payload = verify_jwt(credentials.credentials)
        if payload:
            return True

    # 2️⃣ Verifica API Key
    if x_api_key and verify_api_key(x_api_key):
        return True

    raise HTTPException(status_code=403, detail="Acesso não autorizado")


# 🔎 BUSCAR PROJETO POR NÚMERO
@router.get("/projeto/{numero}")
@limiter.limit("10/minute")
def buscar_projeto(
    numero: int,
    request: Request,
    _=Depends(auth)
):
    projetos = carregar_dados()

    for projeto in projetos:
        if projeto.get("P") == str(numero):
            return projeto

    raise HTTPException(status_code=404, detail="Projeto não encontrado")

# 📋 LISTAR PROJETOS COM FILTROS
@router.get("/projetos")
@limiter.limit("10/minute")
def listar_projetos(
    request: Request,
    status: str = None,
    vendedor: str = None,
    _=Depends(auth)
):
    projetos = carregar_dados()

    if status:
        projetos = [
            p for p in projetos
            if p.get("Status da Usina") == status
        ]

    if vendedor:
        projetos = [
            p for p in projetos
            if p.get("Vendedor") == vendedor
        ]

    return projetos