import streamlit as st
import leafmap.foliumap as leafmap
import pandas as pd
import geopandas as gpd
from sqlalchemy import create_engine
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_community.utilities import SQLDatabase
from langchain_community.agent_toolkits.sql.base import create_sql_agent
from langchain_community.agent_toolkits import SQLDatabaseToolkit
import os
from dotenv import load_dotenv

# 1. AUTENTICAÇÃO GOOGLE CLOUD (BIGQUERY)
# Certifique-se de que o caminho abaixo está correto e o arquivo existe
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "C:/Users/Alexandre/OneDrive - V.tal/GeoAI-OcupacaoRede/credenciais-bigquery.json"

# 2. CARREGAR CHAVE GEMINI (AI STUDIO)
load_dotenv()
api_key = os.getenv("GOOGLE_API_KEY")

# CONFIGURAÇÕES DO PROJETO VTAL
PROJETO_ID = "vtal-inventariorede-prd"
DATASET_ID = "demandas"

# CONFIGURAÇÃO DA PÁGINA STREAMLIT
st.set_page_config(page_title="GeoAI: Monitoramento de Ocupação", layout="wide")
st.markdown("# 🛰️ GeoAI: Monitoramento de Ocupação de Poste")

# --- SIDEBAR ---
with st.sidebar:
    st.image("https://upload.wikimedia.org/wikipedia/commons/b/b2/Google_Cloud_logo.svg", width=50)
    st.subheader("Assistente de Rede")
    
    if api_key:
        st.success(f"Conectado ao Dataset: {DATASET_ID}")
    else:
        st.error("Erro: GOOGLE_API_KEY não encontrada no arquivo .env")

    pergunta = st.text_input("Faça uma pergunta sobre a ocupação dos postes:")

# --- AGENTE DE INTELIGÊNCIA ARTIFICIAL ---
@st.cache_resource
def configurar_agente_ia():
    try:
        # Usando o nome simples do modelo (a biblioteca cuida do prefixo)
        llm = ChatGoogleGenerativeAI(
            model="gemini-pro", # Trocando para o nome mais estável da API
            google_api_key=api_key,
            temperature=0
        )
        
        # Conexão com o BigQuery
        db = SQLDatabase.from_uri(f"bigquery://{PROJETO_ID}/{DATASET_ID}")
        toolkit = SQLDatabaseToolkit(db=db, llm=llm)
        
        # O parâmetro allow_dangerous_requests=True é necessário em versões recentes
        return create_sql_agent(
            llm=llm,
            toolkit=toolkit,
            verbose=True,
            agent_type="tool-calling",
            allow_dangerous_requests=True 
        )
    except Exception as e:
        return f"Erro ao configurar a IA: {e}"

# --- CARREGAMENTO GEOSPATIAL ---
@st.cache_data
def carregar_dados_postes():
    try:
        query = f"""
        SELECT ID_POSTE, geom, PROPRIETARIO_POSTE, ALTURA_POSTE 
        FROM `{PROJETO_ID}.{DATASET_ID}.tb_cabos_bdgd_cobre` 
        LIMIT 50
        """
        engine = create_engine(f"bigquery://{PROJETO_ID}")
        df = pd.read_sql(query, engine)
        
        # Converte a coluna 'geom' (WKT) para o formato Geopandas
        df['geometry'] = gpd.GeoSeries.from_wkt(df['geom'])
        return gpd.GeoDataFrame(df, geometry='geometry')
    except Exception as e:
        st.error(f"Erro ao carregar dados do BigQuery: {e}")
        return pd.DataFrame()

# --- EXECUÇÃO DO AGENTE ---
agent_executor = configurar_agente_ia()

if pergunta and api_key:
    with st.spinner("Analisando infraestrutura..."):
        try:
            # Se agent_executor retornou string de erro, exibe o erro
            if isinstance(agent_executor, str):
                st.error(agent_executor)
            else:
                resposta = agent_executor.invoke({"input": pergunta})
                st.sidebar.info(resposta["output"])
        except Exception as e:
            st.sidebar.error(f"Erro na consulta: {e}")

# --- RENDERIZAÇÃO DO MAPA ---
gdf_postes = carregar_dados_postes()

# Centralizado no Rio de Janeiro
m = leafmap.Map(center=[-22.9068, -43.1729], zoom=12)

if not gdf_postes.empty:
    for idx, row in gdf_postes.iterrows():
        # Latitude (y) e Longitude (x)
        m.add_marker(
            location=[row.geometry.y, row.geometry.x], 
            icon_url="https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-blue.png",
            icon_size=[25, 41],
            popup=(
                f"<b>ID Poste:</b> {row['ID_POSTE']}<br>"
                f"<b>Proprietário:</b> {row['PROPRIETARIO_POSTE']}<br>"
                f"<b>Altura:</b> {row['ALTURA_POSTE']}m"
            )
        )

m.to_streamlit(height=600)