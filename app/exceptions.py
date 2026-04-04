"""
Exceções customizadas da aplicação.
"""


class EsolAPIException(Exception):
    """Exceção base para a API ESOL."""

    def __init__(self, message: str, status_code: int = 500):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class AuthenticationError(EsolAPIException):
    """Erro de autenticação."""

    def __init__(self, message: str = "Autenticação falhou"):
        super().__init__(message, status_code=403)


class ProjectNotFoundError(EsolAPIException):
    """Projeto não encontrado."""

    def __init__(self, message: str = "Projeto não encontrado"):
        super().__init__(message, status_code=404)


class SheetsError(EsolAPIException):
    """Erro ao acessar Google Sheets."""

    def __init__(self, message: str = "Erro ao acessar dados"):
        super().__init__(message, status_code=500)


class ConfigurationError(EsolAPIException):
    """Erro de configuração."""

    def __init__(self, message: str = "Configuração inválida"):
        super().__init__(message, status_code=500)
