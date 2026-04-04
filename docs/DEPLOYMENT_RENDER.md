# Deploy da ESOL PBI API no Render

Guia passo-a-passo para fazer deploy da API no Render e deixá-la acessível publicamente.

## 📋 Pré-requisitos

- ✅ Repositório GitHub (ou GitLab)
- ✅ Conta no Render (grátis em https://render.com)
- ✅ Projeto Google Cloud com credenciais da Service Account
- ✅ Planilha Google Sheets compartilhada com a Service Account
- ✅ API pronta (todas as fases completadas)

## 🚀 Passo 1: Preparar o Repositório

### 1.1 - Fazer commit final

```bash
git add -A
git commit -m "Prepare for Render deployment"
git push origin main
```

### 1.2 - Verificar arquivo Dockerfile

O `Dockerfile` já está pronto, mas verifique:

```bash
cat Dockerfile | head -20
```

Deve ter:
- ✅ Python 3.11-slim
- ✅ Multi-stage build
- ✅ HEALTHCHECK configurado

## 🎯 Passo 2: Criar Conta no Render

1. Acessar https://render.com
2. Clicar "Sign up"
3. Usar GitHub para autenticação (mais fácil)
4. Autorizar Render a acessar seus repositórios

## ⚙️ Passo 3: Criar Web Service

### 3.1 - Novo serviço

1. No dashboard Render, clicar "New +"
2. Selecionar "Web Service"
3. Conectar repositório do GitHub
4. Buscar por `dev02.api-pbi-esol`
5. Clicar "Connect"

### 3.2 - Configurar serviço

Preencher o formulário:

| Campo | Valor |
|-------|-------|
| **Name** | `esol-pbi-api` |
| **Environment** | `Docker` |
| **Region** | `São Paulo` (sa-east-1) |
| **Branch** | `main` |
| **Build Command** | (deixar em branco) |
| **Start Command** | (deixar em branco) |

### 3.3 - Plano

- Render fornece **free tier com limite**
- Recomendação: **Starter Plan** ($7/mês) para uso confiável
- Free tier funciona para testes

## 🔐 Passo 4: Configurar Variáveis de Ambiente

No formulário do Render, ir para **Environment** e adicionar:

```
SPREADSHEET_ID=seu-id-da-planilha-aqui
SECRET_KEY=gere-uma-chave-super-segura-aqui
API_KEY_MASTER=sua-chave-api-para-o-gpt
CACHE_TTL_SECONDS=60
DEBUG=false
HOST=0.0.0.0
PORT=10000
```

### Como gerar SECRET_KEY forte:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

### Como obter SPREADSHEET_ID:

Na URL da sua planilha Google Sheets:
```
https://docs.google.com/spreadsheets/d/1AFnXPQEfgBFOzbNrjqnhBiHrMxC-LLc9TyeTxZnPDJY/edit
                                       ^_____________________________________^
                                       Este é o SPREADSHEET_ID
```

## 🔧 Passo 5: Compartilhar Planilha no Google

1. Abrir sua planilha no Google Sheets
2. Clicar botão "Compartilhar" (canto superior direito)
3. Adicionar email: `esol-pbi-api@cobalt-academy-488306-m5.iam.gserviceaccount.com`
4. Dar permissão de "Visualizador" (não precisa editar)
5. Clicar "Share"

## 📦 Passo 6: Deploy

### 6.1 - Iniciar deploy

Após configurar tudo, clicar "Deploy" no Render.

O deploy levará:
- ~2-5 minutos para build
- ~1-2 minutos para iniciar

### 6.2 - Acompanhar progresso

Na aba "Logs", ver o progresso do build:

```
Building...
[====================] 100%
Deploying...
```

Quando terminar, verá a URL:

```
https://esol-pbi-api.onrender.com
```

### 6.3 - Verificar se está online

No final dos logs, ver algo como:

```
Uvicorn running on 0.0.0.0:10000
```

## ✅ Passo 7: Testar API

```bash
# Health check (sem autenticação)
curl https://esol-pbi-api.onrender.com/health

# Deve retornar:
# {"status":"ok","cache_ttl_seconds":60,"cached_items":0}
```

### Com autenticação:

```bash
# Listar projetos
curl -H "x-api-key: SUA_API_KEY_MASTER" \
  https://esol-pbi-api.onrender.com/projetos

# Deve retornar lista de projetos
```

### Acessar OpenAPI:

- **Swagger UI**: https://esol-pbi-api.onrender.com/docs
- **ReDoc**: https://esol-pbi-api.onrender.com/redoc
- **JSON Schema**: https://esol-pbi-api.onrender.com/openapi.json

## 🐛 Troubleshooting

### Erro: "Service failed to start"

```
Error: exec /bin/bash: no such file
```

**Solução:** Verificar `docker-compose.yml` e `Dockerfile`. Render usa Dockerfile automaticamente.

### Erro: "Build failed - pip install"

```
ERROR: Could not find a version that satisfies the requirement
```

**Solução:**
- Verificar `requirements.txt` - todas as versões válidas
- Tentar remover versões pinned: `fastapi` em vez de `fastapi==0.104.1`

### Erro: "Credentials not found"

```
FileNotFoundError: [Errno 2] No such file or directory: 'config/esol-pbi-api.json'
```

**Solução:**
- O arquivo JSON não pode estar no repositório (por segurança)
- Você pode:
  1. Copiar manualmente para o servidor Render via SSH
  2. Usar Base64 em variável de ambiente
  3. Usar Google Application Credentials

**Recomendado:** Copiar o arquivo JSON manualmente via Render Shell:

```bash
# 1. No dashboard Render, ir para "Shell"
# 2. Criar o arquivo:
mkdir -p config
cat > config/esol-pbi-api.json << 'EOF'
{
  "type": "service_account",
  "project_id": "...",
  ...colar conteúdo JSON aqui...
}
EOF
```

### Erro: 403 Forbidden em /projetos

```json
{"detail": "Acesso não autorizado"}
```

**Solução:**
- Verificar `API_KEY_MASTER` nas variáveis de ambiente
- Testar com curl:
  ```bash
  curl -H "x-api-key: VALUE_FROM_ENV" https://seu-dominio.onrender.com/projetos
  ```

### Planilha retorna vazia

Se `/resumo` retorna `total_projetos: 0`:

1. Verificar `SPREADSHEET_ID` está correto
2. Verificar Service Account tem acesso à planilha
3. Verificar aba se chama `Projetos` exatamente

## 📊 Monitoramento

### Ver logs em tempo real:

No dashboard Render → "Logs"

### Métricas:

Render fornece dashboard com:
- CPU usage
- Memory usage
- Request count
- Response times

## 🔄 Atualizações

Para fazer deploy de atualizações:

1. Fazer commit em `main`
2. Push para GitHub
3. Render automaticamente redeploy

```bash
git commit -m "Update API"
git push origin main
# Render fará deploy automaticamente em ~2 minutos
```

Para parar auto-deploy:

Dashboard Render → Settings → Build & Deploy → Disable Auto-Deploy

## 💰 Custos

### Free Tier
- 750 horas/mês de uptime
- Sleep após 15 min de inatividade
- Reinicia em 24h

### Starter Plan ($7/mês)
- Uptime 24/7
- Sem limites de tempo
- Recomendado para uso em produção

## 🎉 Próximo Passo

Agora que a API está online, integrar com OpenAI Custom Actions:

→ Veja `docs/OPENAI_INTEGRATION.md`
