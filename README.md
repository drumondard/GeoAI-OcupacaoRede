# GeoAI – Ocupação de Rede

Painel inteligente de monitoramento de ocupação de postes e cabos utilizando BigQuery, Streamlit e agentes de IA.

## Funcionalidades

- 🗺️ **Mapa interativo** com postes (pontos) e cabos (linhas) georreferenciados
- 🔴🟡🟢 **Coloração por ocupação** – verde < 60 %, amarelo 60–89 %, vermelho ≥ 90 %
- 📊 **KPIs** em tempo real (total de postes, postes cheios, ocupação média, cabos ativos)
- 💬 **Chat de agente de IA** na barra lateral – traduz linguagem natural em SQL BigQuery
- 🏗️ **Modo demonstração** – funciona sem credenciais GCP com dados fictícios

## Arquitetura

```
app.py               # Aplicação Streamlit principal
bigquery_client.py   # Conexão e helpers para o BigQuery
ai_agent.py          # Stub do agente NL → SQL (pronto para integração LLM)
requirements.txt     # Dependências Python
.streamlit/
  config.toml        # Tema escuro do Streamlit
```

## Pré-requisitos

- Python ≥ 3.10
- Conta GCP com BigQuery habilitado *(opcional – modo demonstração não requer)*

## Instalação

```bash
pip install -r requirements.txt
```

## Configuração

Crie o arquivo `.streamlit/secrets.toml` (não versionado):

```toml
GCP_PROJECT_ID = "meu-projeto"
BQ_DATASET     = "meu-projeto.rede_telecom"

# Opcional – deixe em branco para usar Application Default Credentials (ADC)
GCP_CREDENTIALS = ""
```

Ou exporte variáveis de ambiente:

```bash
export GCP_PROJECT_ID="meu-projeto"
export BQ_DATASET="meu-projeto.rede_telecom"
export GOOGLE_APPLICATION_CREDENTIALS="/caminho/para/chave.json"
```

### Schema esperado no BigQuery

**Tabela `postes`**

| Coluna        | Tipo    | Descrição                              |
|---------------|---------|----------------------------------------|
| id            | STRING  | Identificador do poste                 |
| latitude      | FLOAT64 | Latitude WGS-84                        |
| longitude     | FLOAT64 | Longitude WGS-84                       |
| status        | STRING  | `disponivel` / `ocupado` / `cheio`     |
| ocupacao_pct  | FLOAT64 | Percentual de ocupação (0–100)         |
| operadora     | STRING  | Nome da operadora                      |

**Tabela `cabos`**

| Coluna          | Tipo    | Descrição                                    |
|-----------------|---------|----------------------------------------------|
| id              | STRING  | Identificador do cabo                        |
| lat_origem      | FLOAT64 | Latitude do ponto de origem                  |
| lon_origem      | FLOAT64 | Longitude do ponto de origem                 |
| lat_destino     | FLOAT64 | Latitude do ponto de destino                 |
| lon_destino     | FLOAT64 | Longitude do ponto de destino                |
| tipo            | STRING  | `fibra` / `coaxial` / `cobre`                |
| status          | STRING  | `ativo` / `inativo` / `manutencao`           |
| capacidade_gbps | FLOAT64 | Capacidade total em Gbps                     |
| ocupacao_pct    | FLOAT64 | Percentual de ocupação (0–100)               |

## Execução

```bash
streamlit run app.py
```

Acesse `http://localhost:8501` no navegador.

## Integração com LLM (agente de IA)

O arquivo `ai_agent.py` contém a função `translate_to_sql()` com um stub baseado em palavras-chave.  Para habilitar um LLM real, substitua o conteúdo do stub pela chamada ao provedor desejado (comentários `TODO` indicam os pontos de integração):

- **Vertex AI Gemini** – `vertexai.generative_models.GenerativeModel`
- **OpenAI GPT** – `openai.OpenAI`
- **Anthropic Claude** – `anthropic.Anthropic`

