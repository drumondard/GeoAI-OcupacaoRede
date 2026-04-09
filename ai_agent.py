"""AI agent placeholder for natural-language → SQL translation.

This module provides the interface that the Streamlit sidebar chat will call.
Initially, it returns a rule-based SQL stub so the application is fully
functional even before an LLM is wired in.  The integration point is clearly
marked with ``TODO`` comments so it can be swapped for any LLM provider
(Vertex AI, OpenAI, Anthropic, etc.).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class AgentResponse:
    """Response returned by the AI agent."""

    sql: str
    explanation: str
    error: Optional[str] = None


@dataclass
class ConversationMessage:
    """A single turn in the chat history."""

    role: str  # 'user' | 'assistant'
    content: str


def translate_to_sql(
    user_message: str,
    dataset: str,
    history: Optional[list[ConversationMessage]] = None,
) -> AgentResponse:
    """Translate a natural-language question into a BigQuery SQL query.

    Parameters
    ----------
    user_message:
        The question typed by the user.
    dataset:
        Fully-qualified BigQuery dataset (``project.dataset``).
    history:
        Previous turns of the conversation for context.

    Returns
    -------
    AgentResponse
        Contains the generated SQL, a plain-language explanation, and
        optionally an error string if translation failed.

    Notes
    -----
    TODO: Replace the rule-based stub below with a call to an LLM such as:
      * ``vertexai.generative_models.GenerativeModel`` (Vertex AI Gemini)
      * ``openai.OpenAI`` (OpenAI GPT)
      * ``anthropic.Anthropic`` (Claude)

    A prompt template for the LLM should include:
      * The BigQuery dataset/table schema (postes, cabos).
      * The conversation history for multi-turn support.
      * Instructions to return **only** a valid BigQuery SQL statement.
    """
    msg_lower = user_message.lower()

    # --- Simple keyword-based stub ----------------------------------------
    if any(kw in msg_lower for kw in ("poste", "poste", "pole", "postes")):
        if "ocupad" in msg_lower or "cheio" in msg_lower or "full" in msg_lower:
            sql = (
                f"SELECT *\n"
                f"FROM `{dataset}.postes`\n"
                f"WHERE status IN ('ocupado', 'cheio')\n"
                f"ORDER BY ocupacao_pct DESC\n"
                f"LIMIT 100"
            )
            explanation = (
                "Consultando postes com status 'ocupado' ou 'cheio', "
                "ordenados pelo percentual de ocupação."
            )
        else:
            sql = (
                f"SELECT *\n"
                f"FROM `{dataset}.postes`\n"
                f"LIMIT 100"
            )
            explanation = "Consultando todos os postes (limitado a 100 registros)."

    elif any(kw in msg_lower for kw in ("cabo", "cabos", "cable", "cables")):
        if "inativ" in msg_lower or "inactiv" in msg_lower:
            sql = (
                f"SELECT *\n"
                f"FROM `{dataset}.cabos`\n"
                f"WHERE status = 'inativo'\n"
                f"LIMIT 100"
            )
            explanation = "Consultando cabos com status 'inativo'."
        elif "manut" in msg_lower or "maintenance" in msg_lower:
            sql = (
                f"SELECT *\n"
                f"FROM `{dataset}.cabos`\n"
                f"WHERE status = 'manutencao'\n"
                f"LIMIT 100"
            )
            explanation = "Consultando cabos em manutenção."
        else:
            sql = (
                f"SELECT *\n"
                f"FROM `{dataset}.cabos`\n"
                f"LIMIT 100"
            )
            explanation = "Consultando todos os cabos (limitado a 100 registros)."

    elif any(kw in msg_lower for kw in ("ocupa", "taxa", "media", "average")):
        sql = (
            f"SELECT\n"
            f"  operadora,\n"
            f"  ROUND(AVG(ocupacao_pct), 2) AS media_ocupacao,\n"
            f"  COUNT(*) AS total_postes\n"
            f"FROM `{dataset}.postes`\n"
            f"GROUP BY operadora\n"
            f"ORDER BY media_ocupacao DESC"
        )
        explanation = (
            "Calculando a taxa média de ocupação por operadora em todos os postes."
        )

    else:
        # Generic fallback
        sql = (
            f"-- Pergunta: {user_message}\n"
            f"-- TODO: Integre um LLM para gerar SQL a partir de linguagem natural.\n"
            f"SELECT *\n"
            f"FROM `{dataset}.postes`\n"
            f"LIMIT 10"
        )
        explanation = (
            "Não foi possível identificar uma consulta específica. "
            "Mostrando os primeiros 10 postes como exemplo. "
            "⚠️ A integração com um agente de IA (LLM) gerará SQL preciso "
            "para perguntas em linguagem natural."
        )

    return AgentResponse(sql=sql, explanation=explanation)
