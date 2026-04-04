"""
Configuração centralizada de logging.
"""
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from app.config import settings


def setup_logging() -> logging.Logger:
    """Configura logging da aplicação."""
    # Criar diretório de logs se não existir
    log_dir = Path(__file__).resolve().parent.parent / "logs"
    log_dir.mkdir(exist_ok=True)

    # Configurar logger
    logger = logging.getLogger("esol_api")
    logger.setLevel(logging.DEBUG if settings.DEBUG else logging.INFO)

    # Handler para arquivo com rotação
    file_handler = RotatingFileHandler(
        log_dir / "esol_api.log",
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
    )
    file_handler.setLevel(logging.DEBUG)

    # Handler para console
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO if not settings.DEBUG else logging.DEBUG)

    # Formato de log
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    # Adicionar handlers
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger


# Instância global
logger = setup_logging()
