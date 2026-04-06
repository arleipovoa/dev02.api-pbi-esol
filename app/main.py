"""
Aplicação FastAPI principal.
Configura a aplicação com middleware, exception handlers e rotas.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address

from app.config import settings
from app.logger import logger
from app.routes import router

# Criar aplicação
app = FastAPI(
    title="ESOL PBI API",
    description="API para acesso a dados de projetos ESOL via Google Sheets",
    version="1.0.0",
    debug=settings.DEBUG,
    servers=[
        {
            "url": "https://esol-pbi-api.onrender.com",
            "description": "Production API (Render)"
        }
    ]
)

# 1. Rate limiter configuration
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter

# Exception handler para rate limit
app.add_exception_handler(
    RateLimitExceeded,
    lambda request, exc: JSONResponse(
        status_code=429,
        content={"detail": "Rate limit exceeded. Máximo 10 requisições por minuto."},
    ),
)

# 2. Add Middlewares (A ordem importa!)
# Starlette/FastAPI executa middlewares em ordem LIFO (o último adicionado é o mais externo)

# Rate Limiter (Executado DEPOIS do CORS no processamento da resposta)
app.add_middleware(SlowAPIMiddleware)

# CORS Middleware (Deve ser o MAIS EXTERNO para garantir os headers em todas as respostas)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://chat.openai.com",
        "https://openai.com",
        "https://platform.openai.com",
        "http://localhost:3000",
        "http://localhost:8000",
        "http://localhost:8080",
        "http://127.0.0.1:8080",
        "https://form-to-pbi.vercel.app", # Exemplo de possível origin production
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# 3. Incluir rotas
app.include_router(router)

# Startup event
@app.on_event("startup")
async def startup_event() -> None:
    """Executado ao iniciar a aplicação."""
    logger.info("Aplicação ESOL API iniciada")
    logger.info(f"Debug mode: {settings.DEBUG}")


# Shutdown event
@app.on_event("shutdown")
async def shutdown_event() -> None:
    """Executado ao desligar a aplicação."""
    logger.info("Aplicação ESOL API desligada")