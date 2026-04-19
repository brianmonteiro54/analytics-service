# analytics-service (Python)

Este é o serviço de análise (analytics) do projeto ToggleMaster. Ele é um *worker* de backend e não possui uma API pública (exceto `/health`).

Sua única função é:
1.  Ouvir constantemente a fila do **AWS SQS** (que o `evaluation-service` preenche).
2.  Consumir as mensagens de evento da fila.
3.  Gravar os dados de análise em uma tabela do **AWS DynamoDB**.
 
## Visão Geral
 
O Analytics Service opera como um consumer assíncrono. Ele consome mensagens da fila SQS (enviadas pelo Evaluation Service a cada avaliação de flag) e persiste os dados na tabela DynamoDB `ToggleMasterAnalytics`. Isso permite rastrear o uso das feature flags, taxas de ativação e comportamento ao longo do tempo.
 
## Tecnologias
 
| Componente | Tecnologia |
|---|---|
| Linguagem | Python 3.11 |
| Framework | Flask |
| Mensageria | Amazon SQS (consumer) |
| Banco de Dados | Amazon DynamoDB |
| Container | Docker (multi-stage build) |
| Orquestração | Kubernetes (EKS) |
| Registry | Amazon ECR |
| CI/CD | GitHub Actions + ArgoCD (GitOps) |
 
## Endpoints
 
| Método | Rota | Descrição |
|---|---|---|
| `GET` | `/health` | Health check do serviço |
 
> O serviço opera primariamente como consumer de fila SQS em background thread, não expondo endpoints REST de dados.
 
## Variáveis de Ambiente
 
| Variável | Descrição |
|---|---|
| `AWS_REGION` | Região AWS |
| `AWS_SQS_URL` | URL da fila SQS para consumir eventos |
| `AWS_DYNAMODB_TABLE` | Nome da tabela DynamoDB (`ToggleMasterAnalytics`) |
| `AWS_ENDPOINT_URL` | Endpoint customizado (para LocalStack em dev) |
 
## Pipeline CI/CD (DevSecOps)
 
O workflow do GitHub Actions executa os seguintes estágios:
 
1. **Build & Unit Test** — Instalação de dependências e execução dos testes com `pytest`
2. **Linter** — Análise estática com `flake8`
3. **Security Scan** — SAST com `bandit` + SCA com `Trivy` (bloqueia vulnerabilidades críticas)
4. **Docker Build & Push** — Build da imagem, scan com Trivy e push para o ECR
5. **GitOps Update** — Atualiza a tag da imagem no repositório `deploy-analytics-service`
 
## Deploy (GitOps)
 
O deploy segue o modelo GitOps com ArgoCD. Ao final do pipeline de CI, a tag da imagem é atualizada automaticamente no repositório [`deploy-analytics-service`](https://github.com/brianmonteiro54/deploy-analytics-service), e o ArgoCD sincroniza a mudança no cluster EKS.
 
## Executando Localmente
 
```bash
# Configurar variáveis
cp .env.example .env
 
# Instalar dependências
pip install -r requirements.txt
 
# Rodar
python app.py
```
 
## Estrutura do Projeto
 
```
├── .github/workflows/ci.yaml       # Pipeline CI/CD
├── tests/test_health.py             # Teste do health check
├── tests/test_process_message.py    # Teste do processamento de mensagens
├── Dockerfile                       # Build multi-stage (Python)
├── app.py                           # Aplicação Flask + SQS consumer
├── requirements.txt                 # Dependências Python
└── README.md
```

## 📦 Pré-requisitos (Local)

* [Python](https://www.python.org/) (versão 3.9 ou superior)
* **Credenciais da AWS:** Este serviço **DEVE** ter credenciais da AWS para acessar SQS e DynamoDB. Configure-as em seu terminal (via `aws configure`) ou defina as variáveis de ambiente:
    * `AWS_ACCESS_KEY_ID`
    * `AWS_SECRET_ACCESS_KEY`
    * `AWS_SESSION_TOKEN` (se estiver usando o AWS Academy)
* **Recursos da AWS:** Você precisa ter criado a Fila SQS e a Tabela DynamoDB no console.

## 🚀 Preparando o DynamoDB

Este serviço espera que uma tabela específica exista no DynamoDB.

**Nome da Tabela:** `ToggleMasterAnalytics`
**Chave Primária (Partition Key):** `event_id` (do tipo String)

Você pode criar esta tabela usando o console da AWS ou com o seguinte comando da AWS CLI:

```bash
aws dynamodb create-table \
    --table-name ToggleMasterAnalytics \
    --attribute-definitions \
        AttributeName=event_id,AttributeType=S \
    --key-schema \
        AttributeName=event_id,KeyType=HASH \
    --provisioned-throughput \
        ReadCapacityUnits=1,WriteCapacityUnits=1
```
(Nota: O throughput provisionado acima é o mínimo possível, ideal para o free tier/testes).

## 🚀 Rodando Localmente
**1. Clone o repositório** e entre na pasta `analytics-service`.

**2. Configure as Variáveis de Ambiente:** Crie um arquivo chamado `.env` na raiz desta pasta (`analytics-service/`) com o seguinte conteúdo. **Garanta que suas credenciais da AWS também estejam configuradas no seu ambiente.**
```.env
# Porta que este serviço (health check) irá rodar
PORT="8005"

# --- Configuração da AWS ---
# Cole a URL da fila SQS que você criou
AWS_SQS_URL="httpsiso://[sqs.us-east-1.amazonaws.com/123456789012/sua-fila](https://sqs.us-east-1.amazonaws.com/123456789012/sua-fila)"

# Nome da tabela DynamoDB que você criou
AWS_DYNAMODB_TABLE="ToggleMasterAnalytics"

# Região dos seus serviços SQS e DynamoDB
AWS_REGION="us-east-1"
```

**3. Instale as Dependências:**
```bash
pip install -r requirements.txt
```

**4. Inicie o Serviço:**
```bash
gunicorn --bind 0.0.0.0:8005 app:app
```
O servidor estará rodando em `http://localhost:8005`. Você verá logs no terminal assim que o worker SQS iniciar e (eventualmente) processar mensagens.

## 🧪 Testando o Serviço

Testar este serviço é diferente. Você não vai chamar uma API dele.

**1. Verifique a Saúde:**
```bash
curl http://localhost:8005/health
```
Saída esperada: `{"status":"ok"}``

**2. Gere Eventos:**

- Vá para o `evaluation-service` (que deve estar rodando) e faça algumas requisições de avaliação:
```bash
curl "http://localhost:8004/evaluate?user_id=test-user-1&flag_name=enable-new-dashboard"
curl "http://localhost:8004/evaluate?user_id=test-user-2&flag_name=enable-new-dashboard"
```
- **Alternativa:** Envie uma mensagem manualmente pelo Console da AWS SQS.

**3. Observe os Logs:**

No terminal do `analytics-service`, você deverá ver os logs aparecendo, indicando que as mensagens foram recebidas e salvas no DynamoDB:
```bash
INFO:Iniciando o worker SQS...
INFO:Recebidas 2 mensagens.
INFO:Processando mensagem ID: ...
INFO:Evento ... (Flag: enable-new-dashboard) salvo no DynamoDB.
INFO:Processando mensagem ID: ...
INFO:Evento ... (Flag: enable-new-dashboard) salvo no DynamoDB.
```

**4. Verifique o DynamoDB:**

Vá até o console da AWS, abra o **DynamoDB**, selecione a tabela `ToggleMasterAnalytics` e clique em "Explore table items".

Você verá os itens que o worker acabou de inserir.
