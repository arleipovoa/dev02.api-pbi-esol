# Quick Start: Deploy & Integração com OpenAI GPT

Guia rápido (5 passos) para colocar sua API no GPT em ~30 minutos.

## 📋 O que você precisa

- [ ] GitHub account
- [ ] Render account (grátis: render.com)
- [ ] OpenAI GPT Builder access
- [ ] Google Sheets + Service Account configurado
- [ ] API Key (`API_KEY_MASTER`)

## 🚀 Passo 1: Deploy no Render (10 min)

```bash
# 1. Push do código para GitHub
git push origin main

# 2. Ir para https://render.com
# 3. Clicar "New +" → "Web Service"
# 4. Conectar seu repositório dev02.api-pbi-esol
# 5. Preencher:
#    - Name: esol-pbi-api
#    - Environment: Docker
#    - Region: Sa˜o Paulo
```

## 🔐 Passo 2: Variáveis de Ambiente no Render (5 min)

No formulário Render, ir para "Environment" e adicionar:

```
SPREADSHEET_ID=seu-id-aqui
SECRET_KEY=gerar-com-python-c-import-secrets
API_KEY_MASTER=sua-chave-api
CACHE_TTL_SECONDS=60
DEBUG=false
```

Clicar "Deploy" e aguardar 3-5 minutos.

## ✅ Passo 3: Testar API (5 min)

Após deploy, testar:

```bash
# Health check
curl https://esol-pbi-api.onrender.com/health

# Com API Key
curl -H "x-api-key: YOUR_KEY" \
  https://esol-pbi-api.onrender.com/projetos
```

Deve retornar dados.

## 🤖 Passo 4: Criar Custom Action no OpenAI (8 min)

1. Ir para https://chat.openai.com
2. Criar novo GPT ou editar existente
3. Aba "Configure" → "Custom Actions"
4. "Create new action" → "Import from URL"
5. URL: `https://esol-pbi-api.onrender.com/openapi.json`
6. Preencher autenticação:
   - Type: API Key
   - Auth Type: Header
   - Header Name: `x-api-key`
   - Value: Sua `API_KEY_MASTER`
7. Clicar "Test" (deve passar)
8. Clicar "Save"

## 💬 Passo 5: Usar no GPT (2 min)

No mesmo GPT:

1. Aba "Instructions", adicionar:

```
You have access to ESOL Project Management API.
You can help users find projects, filter by status/vendor,
get project summaries, and refresh data.

Available actions:
- listProjects: List all or filter by status/vendor
- getProject: Get specific project by number
- getSummary: Get statistics
```

2. Salvar GPT

## 🎉 Pronto!

Teste com:
- "Quantos projetos temos?"
- "Me mostra projetos do João"
- "Status do projeto 1010?"

## 📝 Próximos Passos

- Ler `docs/DEPLOYMENT_RENDER.md` para detalhes
- Ler `docs/OPENAI_INTEGRATION.md` para customização
- Compartilhar GPT com sua equipe

## 🆘 Rápido Troubleshooting

| Problema | Solução |
|----------|---------|
| API não responde | Verificar Render logs: `curl seu-dominio.onrender.com/health` |
| Auth falha | Conferir `API_KEY_MASTER` = header value no Custom Action |
| "Unable to parse OpenAPI" | Acessar openapi.json no navegador e checar se é válido |
| No projects returned | Verificar SPREADSHEET_ID e se Google Sheets está compartilhada |

## 📚 Documentação Completa

- Deployment: `docs/DEPLOYMENT_RENDER.md`
- OpenAI: `docs/OPENAI_INTEGRATION.md`
- Architecture: `docs/ARCHITECTURE.md`
- API: `/docs` (após deploy)
