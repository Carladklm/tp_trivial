"""Accès aux tables Gold de la base DuckDB.

Chaque requête ouvre une connexion en lecture seule puis la referme, pour que
`dbt build` puisse écrire dans la base pendant que l'application est ouverte.
"""

from pathlib import Path

import duckdb
import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[2]
DB_PATH = ROOT / "warehouse" / "trivial_questions.duckdb"
SCHEMA = "gold"

MARTS = (
    "mart_leaderboard",
    "mart_model_profile",
    "mart_prompt_format",
    "mart_temperature_effect",
    "mart_perf_by_category",
    "mart_perf_by_difficulty",
    "mart_position_bias",
    "mart_question_insights",
)


@st.cache_data(show_spinner=False)
def query(sql: str) -> pd.DataFrame:
    """Exécute une requête en lecture seule et referme aussitôt la connexion."""
    with duckdb.connect(str(DB_PATH), read_only=True) as con:
        return con.sql(sql).df()


def ensure_db() -> None:
    """Arrête la page avec un message si la base n'a pas encore été construite."""
    if not DB_PATH.exists():
        st.error(f"Base introuvable ({DB_PATH.relative_to(ROOT)}) : lance `dbt build` depuis la racine du projet.")
        st.stop()


def available_marts() -> set[str]:
    """Noms des tables présentes dans le schéma Gold."""
    tables = query(
        f"select table_name from information_schema.tables where table_schema = '{SCHEMA}'"
    )
    return set(tables["table_name"])


def load_mart(name: str) -> pd.DataFrame:
    """Charge une table `gold.mart_*`, ou arrête la page proprement si elle manque."""
    ensure_db()
    if name not in MARTS:
        raise ValueError(f"Table inconnue : {name}")
    if name not in available_marts():
        st.warning(f"La table `{SCHEMA}.{name}` est absente de la base : relance `dbt build` pour la créer.")
        st.stop()
    return query(f"select * from {SCHEMA}.{name}")


def load_leaderboard() -> pd.DataFrame:
    """1 ligne = 1 modèle × 1 prompt."""
    return load_mart("mart_leaderboard")


def load_model_profile() -> pd.DataFrame:
    """1 ligne = 1 modèle (prompts à température 0)."""
    return load_mart("mart_model_profile")


def load_prompt_format() -> pd.DataFrame:
    """1 ligne = 1 modèle × 1 format de prompt (température 0)."""
    return load_mart("mart_prompt_format")


def load_temperature_effect() -> pd.DataFrame:
    """1 ligne = 1 modèle × 1 difficulté, plus une ligne `all` par modèle."""
    return load_mart("mart_temperature_effect")


def load_perf_by_category() -> pd.DataFrame:
    """1 ligne = 1 modèle × 1 prompt × 1 catégorie."""
    return load_mart("mart_perf_by_category")


def load_perf_by_difficulty() -> pd.DataFrame:
    """1 ligne = 1 modèle × 1 prompt × 1 difficulté × 1 type de question."""
    return load_mart("mart_perf_by_difficulty")


def load_position_bias() -> pd.DataFrame:
    """1 ligne = 1 modèle × 1 prompt × 1 type de question × 1 position."""
    return load_mart("mart_position_bias")


def load_question_insights() -> pd.DataFrame:
    """1 ligne = 1 question, agrégée sur tous les modèles et prompts à T=0."""
    return load_mart("mart_question_insights")


def reload_button() -> None:
    """Bouton de barre latérale qui vide le cache pour relire la base après un `dbt build`."""
    if st.sidebar.button("Recharger les données", width="stretch"):
        st.cache_data.clear()
        st.rerun()
