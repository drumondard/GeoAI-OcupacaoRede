"""GeoAI – Painel de Ocupação de Rede.

Streamlit application that:
  1. Connects to Google BigQuery to load geospatial data.
  2. Renders an interactive map with poles (points) and cables (lines).
  3. Provides a sidebar chat interface that translates natural language into
     BigQuery SQL via an AI agent (stub – ready for LLM integration).

Run locally:
    streamlit run app.py

Required secrets (via .streamlit/secrets.toml or environment variables):
    GCP_PROJECT_ID   – GCP project that owns the BigQuery dataset.
    BQ_DATASET       – Fully-qualified dataset in the form  project.dataset.
    GCP_CREDENTIALS  – (optional) JSON string of a service-account key.
                       Falls back to Application Default Credentials (ADC).
"""

from __future__ import annotations

import textwrap
from typing import Optional

import pandas as pd
import pydeck as pdk
import streamlit as st

import ai_agent
import bigquery_client


def _secret(key: str, default: str = "") -> str:
    """Safely read a Streamlit secret, returning *default* if unavailable."""
    try:
        return st.secrets.get(key, default)
    except Exception:
        return default

# ---------------------------------------------------------------------------
# Page configuration
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="GeoAI – Ocupação de Rede",
    page_icon="🗺️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Demo / sample data used when BigQuery is not configured
# ---------------------------------------------------------------------------
_DEMO_POLES = pd.DataFrame(
    [
        # id, latitude, longitude, status, ocupacao_pct, operadora
        ("P001", -23.5505, -46.6333, "disponivel", 35.0, "Operadora A"),
        ("P002", -23.5480, -46.6400, "ocupado", 75.0, "Operadora B"),
        ("P003", -23.5530, -46.6250, "cheio", 98.0, "Operadora A"),
        ("P004", -23.5460, -46.6310, "disponivel", 20.0, "Operadora C"),
        ("P005", -23.5550, -46.6370, "ocupado", 60.0, "Operadora B"),
        ("P006", -23.5515, -46.6290, "cheio", 95.0, "Operadora A"),
        ("P007", -23.5495, -46.6355, "disponivel", 10.0, "Operadora C"),
        ("P008", -23.5570, -46.6410, "ocupado", 80.0, "Operadora B"),
    ],
    columns=["id", "latitude", "longitude", "status", "ocupacao_pct", "operadora"],
)

_DEMO_CABLES = pd.DataFrame(
    [
        # id, lat_orig, lon_orig, lat_dest, lon_dest, tipo, status, cap, occ
        ("C001", -23.5505, -46.6333, -23.5480, -46.6400, "fibra", "ativo", 100.0, 55.0),
        ("C002", -23.5505, -46.6333, -23.5530, -46.6250, "fibra", "ativo", 100.0, 70.0),
        ("C003", -23.5480, -46.6400, -23.5460, -46.6310, "coaxial", "manutencao", 40.0, 0.0),
        ("C004", -23.5530, -46.6250, -23.5515, -46.6290, "fibra", "ativo", 100.0, 90.0),
        ("C005", -23.5460, -46.6310, -23.5495, -46.6355, "cobre", "inativo", 10.0, 0.0),
        ("C006", -23.5495, -46.6355, -23.5550, -46.6370, "fibra", "ativo", 100.0, 45.0),
        ("C007", -23.5550, -46.6370, -23.5570, -46.6410, "coaxial", "ativo", 40.0, 30.0),
    ],
    columns=[
        "id",
        "lat_origem", "lon_origem",
        "lat_destino", "lon_destino",
        "tipo", "status",
        "capacidade_gbps", "ocupacao_pct",
    ],
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _occupation_color(pct: float) -> list[int]:
    """Map an occupation percentage to an RGBA list for pydeck."""
    if pct >= 90:
        return [220, 53, 69, 220]   # red
    if pct >= 60:
        return [255, 193, 7, 220]   # yellow
    return [40, 167, 69, 220]       # green


def _cable_color(status: str) -> list[int]:
    """Map a cable status to an RGBA list for pydeck."""
    mapping = {
        "ativo":      [30, 144, 255, 200],   # blue
        "inativo":    [108, 117, 125, 200],  # grey
        "manutencao": [255, 140, 0, 200],    # orange
    }
    return mapping.get(status, [200, 200, 200, 200])


def _poles_to_pydeck(df: pd.DataFrame) -> pd.DataFrame:
    """Add pydeck-ready columns to the poles DataFrame."""
    df = df.copy()
    df["color"] = df["ocupacao_pct"].apply(_occupation_color)
    return df


def _cables_to_pydeck(df: pd.DataFrame) -> pd.DataFrame:
    """Build the source-target structure pydeck LineLayer expects."""
    df = df.copy()
    df["source_position"] = list(zip(df["lon_origem"], df["lat_origem"]))
    df["target_position"] = list(zip(df["lon_destino"], df["lat_destino"]))
    df["color"] = df["status"].apply(_cable_color)
    return df


def build_map(poles: pd.DataFrame, cables: pd.DataFrame) -> pdk.Deck:
    """Construct a pydeck Deck with a ScatterplotLayer (poles) and a
    LineLayer (cables)."""
    poles_layer = pdk.Layer(
        "ScatterplotLayer",
        data=_poles_to_pydeck(poles),
        get_position=["longitude", "latitude"],
        get_color="color",
        get_radius=60,
        radius_min_pixels=6,
        radius_max_pixels=20,
        pickable=True,
        auto_highlight=True,
    )

    cables_layer = pdk.Layer(
        "LineLayer",
        data=_cables_to_pydeck(cables),
        get_source_position="source_position",
        get_target_position="target_position",
        get_color="color",
        get_width=4,
        pickable=True,
        auto_highlight=True,
    )

    center_lat = poles["latitude"].mean() if not poles.empty else -23.55
    center_lon = poles["longitude"].mean() if not poles.empty else -46.63

    view_state = pdk.ViewState(
        latitude=center_lat,
        longitude=center_lon,
        zoom=13,
        pitch=30,
    )

    return pdk.Deck(
        layers=[cables_layer, poles_layer],
        initial_view_state=view_state,
        map_style="mapbox://styles/mapbox/dark-v10",
        tooltip={
            "html": (
                "<b>ID:</b> {id}<br/>"
                "<b>Status:</b> {status}<br/>"
                "<b>Ocupação:</b> {ocupacao_pct}%<br/>"
                "<b>Operadora:</b> {operadora}"
            ),
            "style": {"backgroundColor": "#1e2130", "color": "white"},
        },
    )


# ---------------------------------------------------------------------------
# BigQuery data loading (cached per connection parameters)
# ---------------------------------------------------------------------------

@st.cache_data(ttl=300, show_spinner=False)
def load_data(
    project_id: str,
    dataset: str,
    credentials_json: Optional[str],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Load poles and cables from BigQuery, caching results for 5 minutes."""
    client = bigquery_client.get_client(project_id, credentials_json)
    poles = bigquery_client.load_poles(client, dataset)
    cables = bigquery_client.load_cables(client, dataset)
    return poles, cables


@st.cache_data(ttl=60, show_spinner=False)
def run_custom_query(
    project_id: str,
    dataset: str,
    credentials_json: Optional[str],
    sql: str,
) -> pd.DataFrame:
    """Execute an arbitrary SQL query and return results as a DataFrame."""
    client = bigquery_client.get_client(project_id, credentials_json)
    return bigquery_client.run_query(client, sql)


# ---------------------------------------------------------------------------
# Sidebar – configuration + chat interface
# ---------------------------------------------------------------------------

def render_sidebar(dataset: str) -> tuple[bool, str, str, Optional[str]]:
    """Render the sidebar and return ``(use_demo, project_id, dataset, creds)``."""
    st.sidebar.image(
        "https://img.icons8.com/fluency/96/map-marker.png",
        width=60,
    )
    st.sidebar.title("GeoAI – Ocupação de Rede")
    st.sidebar.markdown("---")

    # --- Connection settings -------------------------------------------
    with st.sidebar.expander("⚙️ Configuração BigQuery", expanded=False):
        project_id = st.text_input(
            "GCP Project ID",
            value=st.session_state.get(
                "project_id",
                _secret("GCP_PROJECT_ID", "meu-projeto"),
            ),
            key="project_id_input",
        )
        bq_dataset = st.text_input(
            "Dataset (projeto.dataset)",
            value=st.session_state.get(
                "bq_dataset",
                _secret("BQ_DATASET", dataset),
            ),
            key="bq_dataset_input",
        )
        credentials_json = st.text_area(
            "Credenciais JSON (opcional)",
            value=_secret("GCP_CREDENTIALS", ""),
            height=120,
            help=(
                "Cole aqui o conteúdo do arquivo de chave JSON da conta de "
                "serviço.  Deixe em branco para usar ADC / "
                "GOOGLE_APPLICATION_CREDENTIALS."
            ),
            key="credentials_input",
        )
        use_demo = st.checkbox(
            "Usar dados de demonstração",
            value=st.session_state.get("use_demo", True),
            help="Ativa dados fictícios sem precisar de conexão com o BigQuery.",
            key="use_demo_checkbox",
        )

    st.sidebar.markdown("---")

    # --- Chat interface ------------------------------------------------
    st.sidebar.subheader("💬 Agente de Consulta (NL → SQL)")
    st.sidebar.caption(
        "Faça perguntas em linguagem natural sobre a rede. "
        "O agente de IA traduzirá sua pergunta em SQL e executará a consulta."
    )

    # Initialise chat history
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    # Render past messages
    chat_container = st.sidebar.container()
    with chat_container:
        for msg in st.session_state.chat_history:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

    # New message input
    user_input = st.sidebar.chat_input("Ex.: Quais postes estão cheios?")

    return (
        use_demo,
        project_id,
        bq_dataset,
        credentials_json if credentials_json.strip() else None,
        user_input,
    )


# ---------------------------------------------------------------------------
# Main layout
# ---------------------------------------------------------------------------

def render_main(poles: pd.DataFrame, cables: pd.DataFrame, is_demo: bool) -> None:
    """Render the KPI metrics and the interactive map."""
    col_title, col_badge = st.columns([4, 1])
    with col_title:
        st.title("🗺️ Painel de Ocupação de Rede")
    with col_badge:
        if is_demo:
            st.warning("Modo demonstração")

    # KPIs
    total_poles = len(poles)
    full_poles = int((poles["ocupacao_pct"] >= 90).sum()) if not poles.empty else 0
    avg_occ = round(poles["ocupacao_pct"].mean(), 1) if not poles.empty else 0.0
    active_cables = int((cables["status"] == "ativo").sum()) if not cables.empty else 0

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Total de Postes", total_poles)
    k2.metric("Postes Cheios (≥90%)", full_poles)
    k3.metric("Ocupação Média", f"{avg_occ}%")
    k4.metric("Cabos Ativos", active_cables)

    st.markdown("---")

    # Map + legend layout
    map_col, legend_col = st.columns([5, 1])

    with map_col:
        if poles.empty and cables.empty:
            st.info("Sem dados para exibir. Verifique a configuração do BigQuery.")
        else:
            deck = build_map(poles, cables)
            st.pydeck_chart(deck, use_container_width=True)

    with legend_col:
        st.markdown("**Postes**")
        st.markdown("🟢 Disponível (<60%)")
        st.markdown("🟡 Ocupado (60–89%)")
        st.markdown("🔴 Cheio (≥90%)")
        st.markdown("")
        st.markdown("**Cabos**")
        st.markdown("🔵 Ativo")
        st.markdown("🟠 Manutenção")
        st.markdown("⚪ Inativo")


def render_data_tables(poles: pd.DataFrame, cables: pd.DataFrame) -> None:
    """Show filterable data tables below the map."""
    with st.expander("📋 Tabela de Postes", expanded=False):
        status_filter = st.multiselect(
            "Filtrar por status",
            options=poles["status"].unique().tolist() if not poles.empty else [],
            default=[],
            key="poles_status_filter",
        )
        filtered = (
            poles[poles["status"].isin(status_filter)]
            if status_filter
            else poles
        )
        st.dataframe(filtered, use_container_width=True)

    with st.expander("📋 Tabela de Cabos", expanded=False):
        st.dataframe(cables, use_container_width=True)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    DEFAULT_DATASET = "meu-projeto.rede_telecom"

    sidebar_result = render_sidebar(DEFAULT_DATASET)
    use_demo, project_id, bq_dataset, credentials_json, user_input = sidebar_result

    # Persist sidebar state
    st.session_state["project_id"] = project_id
    st.session_state["bq_dataset"] = bq_dataset
    st.session_state["use_demo"] = use_demo

    # --- Load data --------------------------------------------------------
    if use_demo:
        poles, cables = _DEMO_POLES.copy(), _DEMO_CABLES.copy()
        bq_error = None
    else:
        try:
            with st.spinner("Carregando dados do BigQuery…"):
                poles, cables = load_data(project_id, bq_dataset, credentials_json)
            bq_error = None
        except Exception as exc:
            poles, cables = _DEMO_POLES.copy(), _DEMO_CABLES.copy()
            bq_error = str(exc)

    # --- Main panel -------------------------------------------------------
    if bq_error:
        st.error(
            f"❌ Falha ao conectar ao BigQuery: {bq_error}\n\n"
            "Verifique as credenciais ou ative o **Modo demonstração** na barra lateral."
        )

    render_main(poles, cables, is_demo=use_demo)
    render_data_tables(poles, cables)

    # --- Chat processing --------------------------------------------------
    if user_input:
        # Add user message to history
        st.session_state.chat_history.append(
            {"role": "user", "content": user_input}
        )

        history = [
            ai_agent.ConversationMessage(role=m["role"], content=m["content"])
            for m in st.session_state.chat_history
        ]

        response = ai_agent.translate_to_sql(
            user_message=user_input,
            dataset=bq_dataset,
            history=history,
        )

        sql_block = f"```sql\n{response.sql}\n```"
        assistant_content = f"{response.explanation}\n\n{sql_block}"
        st.session_state.chat_history.append(
            {"role": "assistant", "content": assistant_content}
        )

        # Execute query and show results (skip in pure demo mode or if SQL has TODO)
        if not use_demo and "TODO" not in response.sql:
            try:
                with st.spinner("Executando consulta…"):
                    result_df = run_custom_query(
                        project_id, bq_dataset, credentials_json, response.sql
                    )
                with st.expander("📊 Resultado da consulta", expanded=True):
                    st.dataframe(result_df, use_container_width=True)
            except Exception as exc:
                st.sidebar.error(f"Erro na consulta: {exc}")
        elif use_demo:
            # Show a placeholder result in demo mode
            with st.expander("📊 Resultado da consulta (demo)", expanded=True):
                st.info(
                    "Modo demonstração: a consulta acima seria executada no BigQuery. "
                    "Mostrando dados de exemplo."
                )
                if "postes" in response.sql.lower():
                    st.dataframe(poles.head(10), use_container_width=True)
                else:
                    st.dataframe(cables.head(10), use_container_width=True)

        # Force re-render so the new messages appear in the sidebar
        st.rerun()


if __name__ == "__main__":
    main()
