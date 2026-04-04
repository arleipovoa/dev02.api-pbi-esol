"""
Aplicação FastAPI principal.
Configura a aplicação com middleware, exception handlers e rotas.
"""
from fastapi import FastAPI
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