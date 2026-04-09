import streamlit as st
import leafmap.foliumap as leafmap
from google.cloud import bigquery
import pandas as pd
import geopandas as gpd
from shapely import wkt
import os

# IA e Agentes
from langchain_google_vertexai import ChatVertexAI
from langchain_community.agent_toolkits import create_sql_agent
from langchain_community.agent_toolkits import SQLDatabaseToolkit
from langchain_community.utilities import SQLDatabase

# 1. Configurações Iniciais e Segurança
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "credenciais-bigquery.json"

# IDs do Projeto V.tal
PROJETO_ID = "vtal-inventariorede-prd"
DATASET_ID = "demandas"
TABELA_POSTES = "tb_cabos_bdgd_cobre"

st.set_page_config(layout="wide", page_title="GeoAI - Monitoramento de Rede")

# Inicializa cliente BigQuery
client = bigquery.Client(project=PROJETO_ID)

# 2. Configuração do Cérebro (IA)
@st.cache_resource
def configurar_agente_ia():
    try:
        llm = ChatVertexAI(
            model_name="gemini-1.5-flash", 
            location="southamerica-east1", # Mudando para São Paulo
            temperature=0
        )
        
        db = SQLDatabase.from_uri(f"bigquery://{PROJETO_ID}/{DATASET_ID}")
        toolkit = SQLDatabaseToolkit(db=db, llm=llm)
        
        return create_sql_agent(
            llm=llm,
            toolkit=toolkit,
            verbose=True,
            agent_type="tool-calling",
        )
    except Exception as e:
        return f"Erro ao configurar IA: {e}"

# 3. Função para Carregar Dados Espaciais
@st.cache_data
def carregar_dados_postes(query):
    try:
        df = client.query(query).to_dataframe()
        if not df.empty and 'geometria' in df.columns:
            # Converte WKT (ST_ASTEXT) para geometria Geopandas
            df['geometry'] = df['geometria'].apply(lambda x: wkt.loads(x) if x and isinstance(x, str) else None)
            gdf = gpd.GeoDataFrame(df, geometry='geometry', crs="EPSG:4326")
            return gdf
    except Exception as e:
        st.error(f"Erro na consulta ao BigQuery: {e}")
    return gpd.GeoDataFrame()

# --- INTERFACE STREAMLIT ---
st.title("🛰️ GeoAI: Monitoramento de Ocupação de Poste")

# SIDEBAR: Chat com IA
with st.sidebar:
    st.header("🤖 Assistente de Rede")
    st.info(f"Conectado: {DATASET_ID}")
    
    pergunta = st.text_input("Faça uma pergunta sobre ocupação de postes:")
    
    if pergunta:
        with st.spinner("O Agente está consultando o BigQuery..."):
            agente = configurar_agente_ia()
            if isinstance(agente, str): # Se retornou erro
                st.error(agente)
            else:
                try:
                    resposta = agente.run(pergunta)
                    st.success("Análise Finalizada")
                    st.markdown(f"**Resposta:** {resposta}")
                except Exception as e:
                    st.error(f"Ocorreu um erro na IA: {e}")

# --- PROCESSAMENTO DO MAPA ---

# Query Padrão para visualização inicial
QUERY_PADRAO = f"""
SELECT 
  ID_POSTE AS id_poste,
  COUNT(ID_CABO) AS ocupacao_cabos,
  ANY_VALUE(ST_ASTEXT(geom)) AS geometria
FROM `{PROJETO_ID}.{DATASET_ID}.{TABELA_POSTES}`
GROUP BY ID_POSTE
HAVING ocupacao_cabos > 5
limit 100
"""

gdf_postes = carregar_ativos = carregar_dados_postes(QUERY_PADRAO)

# Centralização automática do mapa
if not gdf_postes.empty:
    centro_lat = gdf_postes.geometry.y.mean()
    centro_lon = gdf_postes.geometry.x.mean()
    m = leafmap.Map(center=[centro_lat, centro_lon], zoom=14, google_map="HYBRID")
else:
    m = leafmap.Map(center=[-22.90, -43.17], zoom=12, google_map="HYBRID")

# Link estável de um ícone que remete a infraestrutura/ponto
# Ícone azul oficial do Leaflet para garantir que funcione agora
icon_url = "https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-blue.png"

if not gdf_postes.empty:
    for idx, row in gdf_postes.iterrows():
        m.add_marker(
            location=[row.geometry.y, row.geometry.x],
            icon_url=icon_url,
            icon_size=[25, 41],
            icon_anchor=[12, 41],
            popup=f"Poste: {row['id_poste']}<br>Cabos: {row['ocupacao_cabos']}",
        )
    else:
        st.warning("Ícone 'pole.png' não encontrado. Usando marcadores padrão.")
        m.add_gdf(gdf_postes, layer_name="Postes")

# Renderiza o mapa no Streamlit
m.to_streamlit(height=700)

if not gdf_postes.empty:
    st.write(f"✅ Exibindo {len(gdf_postes)} postes com alta ocupação.")
    # Exibe a tabela de atributos abaixo do mapa para conferência
    with st.expander("Ver Tabela de Dados"):
        st.dataframe(gdf_postes.drop(columns='geometry'))