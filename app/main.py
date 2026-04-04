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
        },
        {
            "url": "http://localhost:8000",
            "description": "Local development"
        }
    ]
)

# CORS Configuration
# Necessário para OpenAI Custom Actions conseguir fazer requisições
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://chat.openai.com",  # OpenAI GPT Builder
        "https://openai.com",       # OpenAI platform
        "https://platform.openai.com",  # OpenAI platform
        "http://localhost:3000",    # Local development
        "http://localhost:8000",    # Local development
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=[
        "Content-Type",
        "Authorization",
        "x-api-key",  # Custom header para API Key
    ],
)

# Rate limiter global
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

# Middleware
app.add_middleware(SlowAPIMiddleware)

# Incluir rotas
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