"""
Configurações centralizadas da aplicação.
Carrega variáveis de ambiente com validações e valores padrão.
"""
import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

# Carrega variáveis de ambiente
load_dotenv()


class Settings:
    """Configurações da aplicação."""

    # ========================
    # Google Sheets Config
    # ========================
    SPREADSHEET_ID: str = os.getenv(
        "SPREADSHEET_ID",
        "1AFnXPQEfgBFOzbNrjqnhBiHrMxC-LLc9TyeTxZnPDJY"
    )
    RANGE_NAME: str = os.getenv("RANGE_NAME", "Projetos")
    SERVICE_ACCOUNT_FILE: str = str(
        Path(__file__).resolve().parent.parent / "config" / "esol-pbi-api.json"
    )
    SCOPES: list[str] = ["https://www.googleapis.com/auth/spreadsheets.readonly"]

    # ========================
    # Cache Config
    # ========================
    CACHE_TTL_SECONDS: int = int(os.getenv("CACHE_TTL_SECONDS", "60"))
    CACHE_MAX_SIZE: int = 100

    # ========================
    # Security - JWT
    # ========================
    SECRET_KEY: str = os.getenv("SECRET_KEY", "change-me-in-production")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # ========================
    # Security - API Key
    # ========================
    API_KEY_MASTER: Optional[str] = os.getenv("API_KEY_MASTER")
    ESOL_API_KEY: Optional[str] = os.getenv("ESOL_API_KEY")

    # ========================
    # Server Config
    # ========================
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))

    # ========================
    # Validações
    # ========================
    @classmethod
    def validate(cls) -> None:
        """Valida configurações críticas."""
        errors = []

        # Validar SECRET_KEY em produção
        if not cls.DEBUG and cls.SECRET_KEY == "change-me-in-production":
            errors.append("SECRET_KEY deve ser alterada em produção")

        # Validar se SERVICE_ACCOUNT_FILE existe
        if not Path(cls.SERVICE_ACCOUNT_FILE).exists():
            errors.append(
                f"Arquivo de credenciais não encontrado: {cls.SERVICE_ACCOUNT_FILE}"
            )

        # Validar autenticação
        if not cls.API_KEY_MASTER and not cls.ESOL_API_KEY and not cls.SECRET_KEY:
            errors.append(
                "Configure pelo menos API_KEY_MASTER, ESOL_API_KEY ou SECRET_KEY"
            )

        if errors:
            error_msg = "\n".join(f"  - {e}" for e in errors)
            raise ValueError(f"Configuração inválida:\n{error_msg}")

    @classmethod
    def to_dict(cls) -> dict:
        """Retorna configurações como dicionário (sem valores sensíveis)."""
        return {
            "SPREADSHEET_ID": "***" if cls.SPREADSHEET_ID else None,
            "CACHE_TTL_SECONDS": cls.CACHE_TTL_SECONDS,
            "DEBUG": cls.DEBUG,
            "HOST": cls.HOST,
            "PORT": cls.PORT,
        }


# Instância global de configurações
settings = Settings()

# Validar configurações ao importar
try:
    settings.validate()
except ValueError as e:
    print(f"⚠️  Aviso de configuração: {e}")
