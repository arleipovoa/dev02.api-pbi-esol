# Arquitetura da ESOL PBI API

## Visão Geral

A ESOL PBI API é uma aplicação FastAPI que funciona como middleware entre aplicações cliente e uma planilha Google Sheets. A arquitetura foi projetada para ser modular, segura, testável e escalável.

## Diagrama de Componentes

```
┌─────────────────────────────────────────────────────────────────┐
│                         Cliente HTTP                             │
│                    (Web, Mobile, Desktop)                        │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         │ (JWT ou API Key)
                         ▼
        ┌────────────────────────────────────────┐
        │     FastAPI Application                │
        │  ┌──────────────────────────────────┐  │
        │  │  app/main.py                     │  │
        │  │  - Setup FastAPI                 │  │
        │  │  - Middleware (Rate Limiting)    │  │
        │  │  - Exception Handlers            │  │
        │  └──────────────────────────────────┘  │
        │                                        │
        │  ┌──────────────────────────────────┐  │
        │  │  app/routes.py                   │  │
        │  │  - GET /health                   │  │
        │  │  - GET /projeto/{numero}         │  │
        │  │  - GET /projetos                 │  │
        │  │  - GET /resumo                   │  │
        │  │  - POST /cache/refresh           │  │
        │  └──────────────────────────────────┘  │
        │                                        │
        │  ┌──────────────────────────────────┐  │
        │  │  app/security.py                 │  │
        │  │  - verify_jwt()                  │  │
        │  │  - verify_api_key()              │  │
        │  │  - create_access_token()         │  │
        │  └──────────────────────────────────┘  │
        │                                        │
        │  ┌──────────────────────────────────┐  │
        │  │  app/config.py                   │  │
        │  │  - Configurações centralizadas   │  │
        │  │  - Validação de ambiente         │  │
        │  └──────────────────────────────────┘  │
        │                                        │
        │  ┌──────────────────────────────────┐  │
        │  │  app/logger.py                   │  │
        │  │  - Setup de logging              │  │
        │  │  - File + Console handlers       │  │
        │  └──────────────────────────────────┘  │
        │                                        │
        │  ┌──────────────────────────────────┐  │
        │  │  Cache (Memory)                  │  │
        │  │  - TTL: 60s (configurável)       │  │
        │  │  - Dados de projetos em memória  │  │
        │  └──────────────────────────────────┘  │
        └────────────────────────────────────────┘
                         │
                         │ (Google API Client)
                         ▼
        ┌────────────────────────────────────────┐
        │     Google Sheets API                  │
        │                                        │
        │  - Service Account Authentication     │
        │  - Read-only access                   │
        │  - OAuth 2.0                          │
        └────────────────────────────────────────┘
                         │
                         ▼
        ┌────────────────────────────────────────┐
        │   Google Sheets Document               │
        │   (Planilha "Projetos")                │
        │                                        │
        │   Colunas: P, Projeto, Status,        │
        │            Vendedor, Valor, ...       │
        └────────────────────────────────────────┘
```

## Módulos Principais

### 1. `app/main.py`
**Responsabilidade:** Configuração e bootstrapping da aplicação

```python
- FastAPI app setup
- Middleware registration (SlowAPI para rate limiting)
- Exception handlers
- Startup/shutdown events
- Request/response logging
```

**Dependências:** FastAPI, slowapi, routes

### 2. `app/routes.py`
**Responsabilidade:** Definição de endpoints e lógica de negócio

```python
- Endpoints HTTP (GET, POST)
- Cache management
- Data normalization and aliasing
- Google Sheets integration
- Request validation and filtering
```

**Dependências:** config, security, logger, exceptions

**Endpoints:**
- `GET /health` - Health check
- `GET /projeto/{numero}` - Buscar projeto
- `GET /projetos` - Listar projetos com filtros
- `GET /resumo` - Resumo agregado
- `POST /cache/refresh` - Refresh de cache

### 3. `app/security.py`
**Responsabilidade:** Autenticação e autorização

```python
- JWT token creation (create_access_token)
- JWT token validation (verify_jwt)
- API Key validation (verify_api_key)
- Hybrid authentication (JWT + API Key)
```

**Dependências:** python-jose

**Métodos de Autenticação:**
1. **JWT**: Via header `Authorization: Bearer <token>`
2. **API Key**: Via header `x-api-key: <key>`

### 4. `app/config.py`
**Responsabilidade:** Gerenciamento centralizado de configurações

```python
- Settings class com todas as configurações
- Carregamento de .env
- Validação de variáveis obrigatórias
- Valores padrão seguros
```

**Dependências:** python-dotenv

**Configurações:**
- Google Sheets (SPREADSHEET_ID, RANGE_NAME)
- Cache (TTL_SECONDS)
- Security (SECRET_KEY, API_KEY_MASTER)
- Server (HOST, PORT, DEBUG)

### 5. `app/logger.py`
**Responsabilidade:** Setup centralizado de logging

```python
- Configuração de loggers
- File handlers com rotação
- Console handlers
- Formatação de logs
```

**Dependências:** logging, logging.handlers

**Saídas:**
- Arquivo: `logs/esol_api.log`
- Console: stdout/stderr

### 6. `app/exceptions.py`
**Responsabilidade:** Exceções customizadas da aplicação

```python
- EsolAPIException (base)
- AuthenticationError
- ProjectNotFoundError
- SheetsError
- ConfigurationError
```

### 7. `app/sheets.py`
**Responsabilidade:** Integração com Google Sheets (DEPRECADO)

⚠️ Este módulo está deprecado. Use `app/routes.py` para carregamento de dados.

```python
- carregar_dados() - Carrega dados da planilha
```

### 8. `app/cache.py`
**Responsabilidade:** Cache em memória

```python
- TTLCache do cachetools
- Configuração: maxsize=100, ttl=60
```

## Fluxo de Dados

### Requisição GET /projetos?status=Ativo

```
1. Cliente envia requisição HTTP
   GET /projetos?status=Ativo
   Header: x-api-key: <key>

2. FastAPI recebe em app/routes.py::listar_projetos()
   │
   ├─→ Valida autenticação via auth()
   │   ├─→ Verifica JWT (app/security.py::verify_jwt)
   │   └─→ OU verifica API Key (app/security.py::verify_api_key)
   │
   ├─→ Se falhar → HTTPException(403)
   │
   ├─→ Carrega dados via carregar_dados()
   │   ├─→ Verifica cache
   │   │   ├─→ Se valid → retorna dados em cache
   │   │   └─→ Se expired → carregar_dados_planilha()
   │   │       └─→ Google Sheets API
   │   └─→ Atualiza timestamp de cache
   │
   ├─→ Filtra por status (case-insensitive)
   │   └─→ obter_valor_canonico(projeto, "status")
   │
   └─→ Retorna lista de projetos

3. FastAPI serializa resposta como JSON
4. Cliente recebe resposta
```

## Camadas da Aplicação

### 1. Camada de Apresentação (API)
- **Arquivos:** `app/main.py`, `app/routes.py`
- **Responsabilidade:** HTTP requests/responses
- **Protocolo:** REST/HTTP

### 2. Camada de Negócio
- **Arquivos:** `app/routes.py` (lógica)
- **Responsabilidade:** Filtros, normalizações, agregações

### 3. Camada de Segurança
- **Arquivos:** `app/security.py`, `app/config.py`
- **Responsabilidade:** Autenticação, autorização

### 4. Camada de Integração
- **Arquivos:** `app/sheets.py`
- **Responsabilidade:** Comunicação com Google Sheets API

### 5. Camada de Cache
- **Arquivos:** `app/cache.py`
- **Responsabilidade:** Armazenamento em memória

### 6. Camada de Logging
- **Arquivos:** `app/logger.py`
- **Responsabilidade:** Rastreamento de eventos

## Padrões de Design

### 1. Dependency Injection (DI)
FastAPI usa injeção de dependências para:
- Autenticação (`Depends(auth)`)
- Rate limiting (`@limiter.limit()`)
- Validação automática

### 2. Singleton
- `settings` em `app/config.py` - configurações globais
- `logger` em `app/logger.py` - logger global
- `_cache` em `app/routes.py` - cache em memória

### 3. Strategy
- **Autenticação dupla** (JWT vs API Key)
- **Normalização de valores** (múltiplos aliases)

### 4. Factory
- `create_access_token()` - cria JWT tokens

## Performance

### Cache Strategy
- **TTL:** 60 segundos (configurável)
- **Escopo:** Memória local
- **Size:** Max 100 entradas
- **Hit Rate:** Esperado ~90% em uso normal

### Rate Limiting
- **Estratégia:** Por IP (slowapi)
- **Limite:** 10 requisições/minuto para endpoints críticos
- **Status:** 429 Too Many Requests

### Latência Estimada

| Operação | Tempo |
|----------|-------|
| Health check | ~1ms |
| Buscar projeto (cache hit) | ~5ms |
| Buscar projeto (cache miss) | ~500-2000ms (Google Sheets) |
| Listar projetos (cache hit) | ~10ms |
| Listar projetos (cache miss) | ~500-2000ms |

## Segurança

### Autenticação
- **JWT:** Token-based, com expiração (60 min)
- **API Key:** Header-based, sem expiração

### Validação
- Variáveis de ambiente obrigatórias
- Credenciais Google não commitadas
- Sanitização de entrada (case-insensitive)

### Logging
- Tenta de auth falhas registradas
- Todos os erros são logados

## Extensibilidade

### Adicionar Novo Endpoint

1. Adicione função em `app/routes.py`
2. Decore com `@router.get()` ou `@router.post()`
3. Use `Depends(auth)` para autenticação
4. Use `@limiter.limit()` para rate limiting
5. Adicione testes em `tests/test_routes.py`

### Adicionar Novo Campo de Filtro

1. Adicione alias em `COLUMN_ALIASES` (app/routes.py)
2. Use `obter_valor_canonico()` no filtro
3. Atualize testes

## Testes

- **Unitários:** `tests/test_security.py`
- **Integração:** `tests/test_routes.py`
- **Fixtures:** `tests/conftest.py`
- **Cobertura:** 70%+ requerida

## Deployment

- **Container:** Docker + docker-compose
- **Port:** 8000 (configurável)
- **Workers:** 1 (uvicorn)
- **Env:** Production-ready (DEBUG=false)

---

## Diagrama de Componentes (Expandido)

```
┌──────────────────────────────────────────────────────────────────────┐
│                     ESOL PBI API v1.0                               │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │  HTTP Layer (FastAPI + Uvicorn)                               │ │
│  │  - Request parsing and validation                             │ │
│  │  - Response serialization (JSON)                              │ │
│  └────────────────────────────────────────────────────────────────┘ │
│                           │                                         │
│                           ▼                                         │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │  Middleware Layer (SlowAPI)                                   │ │
│  │  - Rate limiting (10/min per IP)                              │ │
│  │  - Request/Response logging                                   │ │
│  └────────────────────────────────────────────────────────────────┘ │
│                           │                                         │
│                           ▼                                         │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │  Routes Layer (app/routes.py)                                 │ │
│  │  ┌────────────────────────────────────────────────────────┐  │ │
│  │  │ GET /health → healthcheck()                            │  │ │
│  │  │ GET /projeto/{n} → buscar_projeto()                   │  │ │
│  │  │ GET /projetos → listar_projetos()                     │  │ │
│  │  │ GET /resumo → resumo()                                │  │ │
│  │  │ POST /cache/refresh → atualizar_cache()               │  │ │
│  │  └────────────────────────────────────────────────────────┘  │ │
│  └────────────────────────────────────────────────────────────────┘ │
│                           │                                         │
│  ┌────────────────────────┴──────────────────────────────────────┐  │
│  │  Security Layer (app/security.py)                            │  │
│  │  - JWT validation                                             │  │
│  │  - API Key validation                                         │  │
│  └────────────────────────────────────────────────────────────────┘ │
│                           │                                         │
│  ┌────────────────────────┴──────────────────────────────────────┐  │
│  │  Business Logic Layer                                         │  │
│  │  - Data filtering                                             │  │
│  │  - Data normalization                                         │  │
│  │  - Column aliasing                                            │  │
│  └────────────────────────────────────────────────────────────────┘ │
│                           │                                         │
│  ┌────────────────────────┴──────────────────────────────────────┐  │
│  │  Cache Layer (app/cache.py)                                  │  │
│  │  - TTLCache (60s)                                             │  │
│  └────────────────────────────────────────────────────────────────┘ │
│                           │                                         │
│  ┌────────────────────────┴──────────────────────────────────────┐  │
│  │  Data Layer (app/sheets.py)                                  │  │
│  │  - Google Sheets API integration                              │  │
│  └────────────────────────────────────────────────────────────────┘ │
│                           │                                         │
│  ┌────────────────────────┴──────────────────────────────────────┐  │
│  │  Configuration Layer (app/config.py)                         │  │
│  │  - Environment variable management                            │  │
│  │  - Settings validation                                        │  │
│  └────────────────────────────────────────────────────────────────┘ │
│                           │                                         │
│  ┌────────────────────────┴──────────────────────────────────────┐  │
│  │  Logging Layer (app/logger.py)                               │  │
│  │  - File logging (logs/esol_api.log)                           │  │
│  │  - Console logging                                            │  │
│  └────────────────────────────────────────────────────────────────┘ │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

---

**Documentação atualizada:** 2026-04-04
**Versão da API:** 1.0.0
