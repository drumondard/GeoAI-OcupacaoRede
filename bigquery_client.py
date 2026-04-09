"""BigQuery client helpers for GeoAI-OcupacaoRede."""

from __future__ import annotations

import os
from typing import Optional

import pandas as pd

try:
    from google.cloud import bigquery
    from google.oauth2 import service_account

    BIGQUERY_AVAILABLE = True
except ImportError:  # pragma: no cover
    BIGQUERY_AVAILABLE = False


def get_client(
    project_id: str,
    credentials_json: Optional[str] = None,
) -> "bigquery.Client":
    """Return an authenticated BigQuery client.

    Authentication is resolved in the following order:
    1. ``credentials_json`` – a JSON string with a service-account key.
    2. The ``GOOGLE_APPLICATION_CREDENTIALS`` environment variable (path to a
       service-account key file).
    3. Application Default Credentials (ADC) – works on GCP-managed environments
       (Cloud Run, Vertex AI, GCE, etc.).

    Parameters
    ----------
    project_id:
        GCP project that will be billed for queries.
    credentials_json:
        Optional JSON string of a service-account key (from, e.g., a Streamlit
        secret).
    """
    if not BIGQUERY_AVAILABLE:
        raise RuntimeError(
            "google-cloud-bigquery is not installed. "
            "Run `pip install google-cloud-bigquery`."
        )

    if credentials_json:
        import json

        info = json.loads(credentials_json)
        creds = service_account.Credentials.from_service_account_info(
            info,
            scopes=["https://www.googleapis.com/auth/cloud-platform"],
        )
        return bigquery.Client(project=project_id, credentials=creds)

    # Fall back to ADC / GOOGLE_APPLICATION_CREDENTIALS
    return bigquery.Client(project=project_id)


def run_query(client: "bigquery.Client", sql: str) -> pd.DataFrame:
    """Execute *sql* against BigQuery and return results as a DataFrame."""
    query_job = client.query(sql)
    return query_job.to_dataframe()


def load_poles(
    client: "bigquery.Client",
    dataset: str,
    table: str = "postes",
) -> pd.DataFrame:
    """Fetch pole records with at minimum ``latitude``, ``longitude`` columns.

    Expected schema (additional columns are passed through):
        id           STRING
        latitude     FLOAT64
        longitude    FLOAT64
        status       STRING   (e.g. 'disponivel', 'ocupado', 'cheio')
        ocupacao_pct FLOAT64  (0-100)
        operadora    STRING
    """
    sql = f"""
        SELECT *
        FROM `{dataset}.{table}`
        WHERE latitude IS NOT NULL
          AND longitude IS NOT NULL
    """
    return run_query(client, sql)


def load_cables(
    client: "bigquery.Client",
    dataset: str,
    table: str = "cabos",
) -> pd.DataFrame:
    """Fetch cable records.

    Expected schema:
        id              STRING
        lat_origem      FLOAT64
        lon_origem      FLOAT64
        lat_destino     FLOAT64
        lon_destino     FLOAT64
        tipo            STRING   (e.g. 'fibra', 'coaxial', 'cobre')
        status          STRING   (e.g. 'ativo', 'inativo', 'manutencao')
        capacidade_gbps FLOAT64
        ocupacao_pct    FLOAT64  (0-100)
    """
    sql = f"""
        SELECT *
        FROM `{dataset}.{table}`
        WHERE lat_origem IS NOT NULL
          AND lon_origem IS NOT NULL
          AND lat_destino IS NOT NULL
          AND lon_destino IS NOT NULL
    """
    return run_query(client, sql)
