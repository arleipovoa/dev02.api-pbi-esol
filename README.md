# ESOL PBI API

![Version](https://img.shields.io/badge/version-1.0.0-blue)
![Python](https://img.shields.io/badge/python-3.8%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)

API REST para integração com Google Sheets, fornecendo acesso seguro a dados de projetos ESOL com autenticação dupla (JWT + API Key), cache inteligente e rate limiting.

## 📋 Índice

- [Características](#características)
- [Pré-requisitos](#pré-requisitos)
- [Instalação](#instalação)
- [Configuração](#configuração)
- [Uso](#uso)
- [Documentação da API](#documentação-da-api)
- [Estrutura do Projeto](#estrutura-do-projeto)
- [Testes](#testes)
- [Deployment](#deployment)
- [Troubleshooting](#troubleshooting)

## ✨ Características

- ✅ **API REST moderna** com FastAPI
- ✅ **Autenticação dupla**: JWT e API Key
- ✅ **Rate limiting**: 10 requisições/minuto por IP
- ✅ **Cache inteligente**: TTL configurável (padrão 60s)
- ✅ **Google Sheets integrado**: Leitura em tempo real
- ✅ **Filtros avançados**: Status, vendedor (case-insensitive)
- ✅ **Logging completo**: Arquivo + console
- ✅ **Testes automatizados**: Pytest com 70%+ coverage
- ✅ **Type hints**: 100% tipagem de tipos
- ✅ **Documentação automática**: Swagger/OpenAPI

## 📦 Pré-requisitos

- Python 3.8+
- pip ou Poetry
- Credenciais de Google Service Account
- Google Sheets com dados de projetos

## 🚀 Instalação

### 1. Clone o repositório

```bash
git clone https://github.com/arleipovoa/dev02.api-pbi-esol.git
cd dev02.api-pbi-esol
```

### 2. Crie um ambiente virtual

```bash
python -m venv venv

# Linux/Mac
source venv/bin/activate

# Windows
venv\Scripts\activate
```

### 3. Instale as dependências

```bash
pip install -r requirements.txt
```

### 4. Configure as variáveis de ambiente

```bash
# Copie o arquivo de exemplo
cp .env.example .env

# Edite o .env com suas configurações
nano .env  # ou use seu editor favorito
```

## ⚙️ Configuração

### Variáveis de Ambiente Obrigatórias

```env
# Google Sheets
SPREADSHEET_ID=seu-id-aqui
SECRET_KEY=sua-chave-jwt-super-secreta

# Autenticação
API_KEY_MASTER=sua-chave-api-master

# Cache
CACHE_TTL_SECONDS=60
```

### Variáveis de Ambiente Opcionais

```env
# Server
HOST=0.0.0.0
PORT=8000
DEBUG=false

# Alternativa para API Key
ESOL_API_KEY=sua-chave-alternativa
```

### Configurar Google Sheets

1. Crie um projeto no [Google Cloud Console](https://console.cloud.google.com)
2. Ative a API de Google Sheets
3. Crie uma Service Account e baixe o JSON
4. Salve o JSON em `config/esol-pbi-api.json`
5. Compartilhe a planilha com o email da Service Account
6. Configure `SPREADSHEET_ID` no `.env`

## 📖 Uso

### Iniciar a API

```bash
python run.py
```

API estará disponível em `http://localhost:8000`

### Documentação Interativa

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

### Exemplos de Uso

#### 1. Health Check

```bash
curl http://localhost:8000/health
```

#### 2. Listar Projetos (com API Key)

```bash
curl -H "x-api-key: sua-api-key" \
  http://localhost:8000/projetos
```

#### 3. Buscar Projeto Específico

```bash
curl -H "x-api-key: sua-api-key" \
  http://localhost:8000/projeto/1010
```

#### 4. Filtrar por Status

```bash
curl -H "x-api-key: sua-api-key" \
  "http://localhost:8000/projetos?status=Ativo"
```

#### 5. Filtrar por Vendedor

```bash
curl -H "x-api-key: sua-api-key" \
  "http://localhost:8000/projetos?vendedor=João"
```

#### 6. Obter Resumo

```bash
curl -H "x-api-key: sua-api-key" \
  http://localhost:8000/resumo
```

#### 7. Atualizar Cache (forçar sincronização)

```bash
curl -X POST \
  -H "x-api-key: sua-api-key" \
  http://localhost:8000/cache/refresh
```

### Autenticação com JWT

```bash
# 1. Gerar token (em sua aplicação)
token=$(python -c "from app.security import create_access_token; print(create_access_token({'sub': 'user'}))")

# 2. Usar token
curl -H "Authorization: Bearer $token" \
  http://localhost:8000/projetos
```

## 📚 Documentação da API

Veja [docs/API.md](docs/API.md) para documentação completa de endpoints.

### Endpoints Principais

| Método | Endpoint | Descrição | Autenticação |
|--------|----------|-----------|--------------|
| GET | `/health` | Verificar saúde da API | Opcional |
| GET | `/projeto/{numero}` | Buscar projeto por número | Obrigatória |
| GET | `/projetos` | Listar projetos com filtros | Obrigatória |
| GET | `/resumo` | Resumo agregado | Obrigatória |
| POST | `/cache/refresh` | Atualizar cache | Obrigatória |

## 📁 Estrutura do Projeto

```
dev02.api-pbi-esol/
├── app/
│   ├── __init__.py           # Inicialização do pacote
│   ├── main.py               # Configuração FastAPI
│   ├── routes.py             # Endpoints da API
│   ├── security.py           # Autenticação (JWT + API Key)
│   ├── config.py             # Configurações centralizadas
│   ├── logger.py             # Setup de logging
│   ├── exceptions.py         # Exceções customizadas
│   ├── sheets.py             # Integração Google Sheets
│   ├── cache.py              # Cache em memória
│   └── __pycache__/          # Cache Python
├── config/
│   └── esol-pbi-api.json     # Credenciais Google (GITIGNORED)
├── tests/
│   ├── __init__.py
│   ├── conftest.py           # Fixtures compartilhadas
│   ├── test_routes.py        # Testes dos endpoints
│   └── test_security.py      # Testes de autenticação
├── docs/
│   ├── API.md                # Documentação de endpoints
│   └── ARCHITECTURE.md       # Arquitetura do projeto
├── logs/                     # Arquivos de log (GITIGNORED)
├── .env.example              # Exemplo de variáveis
├── .env                      # Variáveis de ambiente (GITIGNORED)
├── .gitignore                # Git ignore rules
├── .gitattributes            # Git attributes
├── run.py                    # Script para iniciar
├── requirements.txt          # Dependências Python
├── pytest.ini                # Configuração de testes
├── Dockerfile                # Container Docker
├── docker-compose.yml        # Orchestração Docker
└── README.md                 # Este arquivo
```

## 🧪 Testes

### Rodar Testes

```bash
# Todos os testes
pytest

# Com cobertura
pytest --cov

# Verboso
pytest -v

# Teste específico
pytest tests/test_routes.py::TestHealthEndpoint
```

### Cobertura de Testes

- Testes unitários para autenticação
- Testes de integração para endpoints
- Rate limiting validation
- Mock de Google Sheets

Cobertura mínima: 70%

## 🐳 Deployment

### Docker

```bash
# Build
docker build -t esol-pbi-api .

# Run
docker run -p 8000:8000 --env-file .env esol-pbi-api
```

### Docker Compose

```bash
docker-compose up

# Detached mode
docker-compose up -d

# Ver logs
docker-compose logs -f

# Parar
docker-compose down
```

### Deploy em Produção

Veja [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) (coming soon)

## 🆘 Troubleshooting

### Erro: "Arquivo de credenciais não encontrado"

```
FileNotFoundError: [Errno 2] No such file or directory: 'config/esol-pbi-api.json'
```

**Solução:**
1. Baixe o JSON da Service Account no Google Cloud Console
2. Salve em `config/esol-pbi-api.json`
3. Reinicie a aplicação

### Erro: "Invalid spreadsheet ID"

```
HttpError 404: Not found
```

**Solução:**
1. Verifique o `SPREADSHEET_ID` no `.env`
2. Confirme que a planilha existe
3. Confirme que a Service Account tem permissão de acesso

### Erro: 403 Forbidden

```
{"detail": "Acesso não autorizado"}
```

**Solução:**
1. Verifique a API Key no header `x-api-key`
2. Ou verifique o JWT no header `Authorization: Bearer <token>`
3. Confirme que as credenciais são válidas

### Rate Limit Excedido

```
{"detail": "Rate limit exceeded. Máximo 10 requisições por minuto."}
```

**Solução:**
1. Aguarde 1 minuto e tente novamente
2. Ou aumente o limite (veja `slowapi` docs)

## 🔐 Segurança

- ✅ Credenciais Google não são commitadas
- ✅ API Key configurável via ambiente
- ✅ JWT com expiração
- ✅ Rate limiting por IP
- ✅ Logging de tentativas falhas

⚠️ **IMPORTANTE**: Altere `SECRET_KEY` em produção!

## 📝 Licença

MIT

## 👥 Autor

ESOL Team

---

## 📞 Suporte

Para reportar bugs ou sugerir features, abra uma [issue](https://github.com/arleipovoa/dev02.api-pbi-esol/issues).
