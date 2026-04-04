# Integração ESOL PBI API com GPT Personalizado OpenAI

Guia completo para integrar a API ESOL como Custom Action em um GPT personalizado da OpenAI.

## 📋 Pré-requisitos

- ✅ API deployada em Render (ou servidor com HTTPS público)
- ✅ URL pública da API: `https://seu-dominio.onrender.com`
- ✅ OpenAPI JSON acessível em: `https://seu-dominio.onrender.com/openapi.json`
- ✅ API Key gerada (mesmo valor de `API_KEY_MASTER`)
- ✅ Acesso a OpenAI GPT Builder (ChatGPT Plus ou API access)

## 🎯 Passo 1: Verificar OpenAPI Schema

Antes de começar, verificar se o schema está correto:

```bash
# Acessar no navegador
https://seu-dominio.onrender.com/openapi.json

# Ou via curl
curl https://seu-dominio.onrender.com/openapi.json | jq '.paths'
```

Deve retornar:
```json
{
  "paths": {
    "/health": { ... },
    "/projeto/{numero}": { ... },
    "/projetos": { ... },
    "/resumo": { ... },
    "/cache/refresh": { ... }
  }
}
```

## 🔑 Passo 2: Preparar Chaves

### 2.1 - API Key

Usar o valor de `API_KEY_MASTER` do `.env` em produção:

```bash
# Exemplo:
API_KEY_MASTER=seu-valor-super-secreto-aqui
```

**⚠️ Importante:** Não compartilhe essa chave! Use apenas em integração com seu GPT privado.

### 2.2 - Verificar acesso

Testar que a autenticação funciona:

```bash
curl -H "x-api-key: YOUR_API_KEY_HERE" \
  https://seu-dominio.onrender.com/projetos
```

Deve retornar uma lista de projetos (ou array vazio).

## 🤖 Passo 3: Configurar Custom Action no OpenAI GPT Builder

### 3.1 - Acessar GPT Builder

1. Ir para https://chat.openai.com
2. Clicar seu nome (canto inferior esquerdo)
3. Selecionar "My GPTs"
4. Clicar "Create a GPT" ou editar um GPT existente

### 3.2 - Acessar Custom Actions

1. Na aba "Configure", ir para "Custom Actions"
2. Clicar "Create new action"
3. Escolher "Import from URL"
4. Colar: `https://seu-dominio.onrender.com/openapi.json`
5. Clicar "Import"

### 3.3 - Configurar Autenticação

OpenAI automaticamente detectará os endpoints, mas precisa configurar autenticação:

1. Scroll até "Authentication"
2. Selecionar tipo: **"API Key"**
3. Preencher:
   - **Auth Type:** "Header"
   - **Header Name:** `x-api-key`
   - **Header Value:** Cole sua `API_KEY_MASTER`

### 3.4 - Configurações Avançadas (Opcional)

Se quiser customizar:

1. **Request Body Encoding:** "JSON"
2. **URL:** Deixar como está (auto-preenchido)
3. **Rate Limiting:** Deixar em branco (API cuida disso)

## ✅ Passo 4: Testar Custom Action

### 4.1 - Teste Automático

Após configurar, OpenAI oferece um preview:

1. Clicar botão "Test" ou preview
2. Selecionar um endpoint (ex: `/projetos`)
3. Clicar "Test action"

Deve retornar resposta com sucesso (200).

### 4.2 - Testes Manuais de Endpoint

**Test 1: List Projects**
```
GET /projetos
```
Resposta esperada: Lista de projetos

**Test 2: Get Project by Number**
```
GET /projeto/1010
```
Resposta esperada: Projeto com número 1010

**Test 3: Filter by Status**
```
GET /projetos?status=Ativo
```
Resposta esperada: Apenas projetos com status "Ativo"

**Test 4: Get Summary**
```
GET /resumo
```
Resposta esperada: Resumo com total, por_status, por_vendedor

## 💬 Passo 5: Usar no GPT

### 5.1 - Construir o GPT

Na seção de "Configure", adicione instruções para o GPT:

```markdown
You have access to the ESOL Project Management API.
You can help users:
- Find project information
- Filter projects by status or vendor
- Get project summaries and statistics
- Refresh cached data

Available actions:
- listProjects: Get all projects or filter by status/vendor
- getProject: Get specific project by number
- getSummary: Get aggregated statistics
- healthCheck: Verify API is online
- refreshCache: Force data synchronization

Always use exact project numbers when requested.
Provide clear summaries of project data.
Mention cache information when relevant.
```

### 5.2 - Prompts de Teste

Teste com prompts como:

```
"Quantos projetos temos?"
→ Usa /resumo

"Me mostra os projetos do João"
→ Usa /projetos?vendedor=João

"Qual é o status do projeto 1010?"
→ Usa /projeto/1010

"Quantos projetos estão em proposta?"
→ Usa /resumo e filtra por status

"Sincronize os dados mais recentes"
→ Usa /cache/refresh
```

### 5.3 - Dicas de Uso

- **Ser específico**: "Projeto 1010" em vez de "aquele projeto"
- **Usar nomes consistentes**: Vendedor "João Silva" em vez de "João"
- **Pedir resumos**: "Dê um resumo dos projetos" usa menos requisições
- **Contexto**: Mencione filtros desejados no mesmo prompt

## 🔒 Segurança

### Boas Práticas

1. **API Key:** Protegida no GPT, não compartilhada publicamente
2. **HTTPS:** Todas as conexões são encriptadas
3. **CORS:** Apenas openai.com pode acessar
4. **Rate Limiting:** Máximo 10 requisições/minuto
5. **Google Sheets:** Apenas leitura, sem edições

### Mudar API Key

Se a chave foi comprometida:

1. Gerar nova chave:
   ```bash
   python -c "import secrets; print(secrets.token_urlsafe(32))"
   ```

2. Atualizar em Render (variável `API_KEY_MASTER`)

3. Atualizar no GPT (Custom Action → Authentication)

## 🆘 Troubleshooting

### Erro: "Authentication failed"

```
Error: Authentication failed. Please check your API key.
```

**Solução:**
- Verificar que `API_KEY_MASTER` está correto no Render
- Verificar que header name é `x-api-key` (case-sensitive)
- Testar com curl:
  ```bash
  curl -H "x-api-key: YOUR_KEY" https://seu-dominio.onrender.com/health
  ```

### Erro: "Unable to parse OpenAPI schema"

```
Invalid OpenAPI schema
```

**Solução:**
- Acessar JSON schema diretamente no navegador:
  `https://seu-dominio.onrender.com/openapi.json`
- Se retornar erro 500, há problema na API
- Verificar logs em Render: Dashboard → Logs

### Erro: "Action not available"

```
Custom action is not available right now
```

**Solução:**
- Esperar alguns minutos (OpenAI processa)
- Refresh página do GPT Builder
- Verificar que API está online:
  ```bash
  curl https://seu-dominio.onrender.com/health
  ```

### GPT não consegue encontrar projetos

Se o GPT retorna "no projects found":

1. Verificar que /resumo retorna dados:
   ```bash
   curl -H "x-api-key: KEY" https://seu-dominio.onrender.com/resumo
   ```

2. Se houver `total_projetos: 0`:
   - Verificar SPREADSHEET_ID
   - Verificar Google Sheets compartilhada
   - Verificar dados na planilha na aba "Projetos"

### Rate limit atingido

```
Rate limit exceeded. Máximo 10 requisições por minuto.
```

**Solução:**
- Aguardar 1 minuto
- Usar /resumo em vez de /projetos quando possível (menos requisições)
- Consolidar múltiplos filtros em 1 requisição

## 📊 Monitoramento

### Verificar Uso

Em Render Dashboard:
- **Logs:** Ver requisições da API
- **Metrics:** CPU, memória, requests/min

### Exemplos de Requisições Vistas em Logs

```
GET /projetos?status=Ativo - 200 OK
GET /projeto/1010 - 200 OK
GET /resumo - 200 OK
```

## 🎓 Guias Avançados

### Customizar Prompts do GPT

```markdown
# ESOL Project Management Assistant

You are an expert at helping manage solar energy projects.

## Your capabilities:
- Access to real-time project database
- Filter and search functionality
- Generate summaries and reports

## Guidelines:
- Always confirm project numbers before showing details
- Use status filters to help prioritize
- Mention cache status when fetching data
- Offer related projects when relevant
```

### Integrar com Outras Ações

Se tiver múltiplas custom actions:

```markdown
1. ESOL PBI API: Project management
2. Email Integration: Send reports
3. Google Drive: Save files

When user asks for "send report", use ESOL API to get data, 
then Email Integration to send.
```

## 🚀 Próximos Passos

1. ✅ API deployada no Render
2. ✅ Custom Action configurada no OpenAI
3. ✅ Testes funcionando
4. → Publicar GPT para equipe
5. → Monitorar uso e logs
6. → Adicionar mais funcionalidades

## 📞 Suporte

Problemas? Verifique:

1. Documentação OpenAPI: `/docs`
2. Logs em Render: Dashboard → Logs
3. Health Check: `/health`
4. Teste de autenticação: `curl com -H "x-api-key"`

## 📝 Checklist Final

Antes de usar em produção:

- [ ] API está deployada e acessível via HTTPS
- [ ] `/health` retorna status "ok"
- [ ] `/openapi.json` retorna schema válido
- [ ] Custom Action importada no GPT Builder
- [ ] Autenticação configurada (x-api-key header)
- [ ] Preview testa endpoints com sucesso
- [ ] GPT consegue fazer requisições
- [ ] Prompts retornam respostas esperadas
- [ ] Cache está funcionando
- [ ] Logs em Render mostram requisições

Quando tudo passar no checklist, seu GPT está pronto! 🎉
