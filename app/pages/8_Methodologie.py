"""Page 8 — Méthodologie : pipeline, protocole, règle de correction, indicateurs et limites."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd
import streamlit as st

from lib.data import load_volumes
from lib.style import DEFINITIONS, HELP, PROMPT_LABELS, kpi, page_setup, section

page_setup("Méthodologie", "comment les résultats ont-ils été produits, et jusqu'où peut-on leur faire confiance ?")


def _int(n: float) -> str:
    """Entier avec espace comme séparateur de milliers."""
    return f"{int(n):,}".replace(",", " ")


# --- Volumes ------------------------------------------------------------------------
volumes = load_volumes()
cols = st.columns(4)
with cols[0]:
    kpi("Réponses", _int(volumes["n_responses"]), "blue", delta=f"{_int(volumes['n_runs'])} exécutions")
with cols[1]:
    kpi("Questions", _int(volumes["n_questions"]), "green", delta="Open Trivia DB, nettoyées")
with cols[2]:
    kpi("Modèles", _int(volumes["n_models"]), "orange", delta="exécutés en local")
with cols[3]:
    kpi("Prompts", _int(volumes["n_prompts"]), "pink", delta="dont 1 à température 1")

# --- Pipeline -----------------------------------------------------------------------
section("Le pipeline")
st.markdown(
    "Architecture médaillon : **Bronze** (données brutes) → **Silver** (données nettoyées et réponses brutes, "
    "puis notation) → **Gold** (une table par question d'analyse). Outils : Python, LM Studio, dbt, DuckDB, Streamlit."
)
st.graphviz_chart(
    """
    digraph {
      rankdir=LR; bgcolor="transparent";
      node [shape=box, style="rounded,filled", fontname="Helvetica", fontsize=11, color="#2A3566", fontcolor="#EEF1FB", fillcolor="#151D3F"];
      edge [color="#9AA6CF"];
      api   [label="API OpenTDB"];
      bronze[label="Bronze\\nquestions_raw.csv", fillcolor="#7A4A10"];
      clean [label="Silver\\nquestions_clean.parquet", fillcolor="#4A5568"];
      lm    [label="LM Studio\\n4 modèles × 4 prompts"];
      raw   [label="Silver\\nai_responses/*.parquet", fillcolor="#4A5568"];
      stg   [label="dbt staging\\nstg_*"];
      int   [label="dbt intermediate\\ncorrection des réponses"];
      gold  [label="Gold\\n8 marts", fillcolor="#7A6410"];
      app   [label="Streamlit"];
      api -> bronze -> clean -> lm -> raw -> stg -> int -> gold -> app;
      clean -> stg;
    }
    """,
    width="stretch",
)

# --- Protocole -------------------------------------------------------------------------
section("Le protocole")
st.markdown(
    "- **Mêmes questions pour tous** : chaque exécution pose les mêmes questions, tirées avec la même graine.\n"
    "- **Options mélangées avec une graine** (`question_id`) : une question a le même ordre d'options pour tous les "
    "modèles et tous les prompts. Sans ce mélange, la bonne réponse serait toujours la première. Pour un vrai/faux, "
    "l'ordre est fixe : A = True, B = False.\n"
    "- **Température 0** (réponse la plus probable, reproductible), sauf pour le prompt lettres à température 1.\n"
    "- **`max_tokens` = 5** (40 pour le prompt texte) : le modèle doit répondre en une étiquette, pas en une phrase.\n"
    "- **Réponse brute conservée** : la notation se fait ensuite dans dbt, ce qui permet de la corriger sans reposer les questions."
)
st.dataframe(
    pd.DataFrame(
        [
            ("v1_letters", PROMPT_LABELS["v1_letters"], "0", "A, B, C ou D (A/B pour un vrai/faux)"),
            ("v2_numbers", PROMPT_LABELS["v2_numbers"], "0", "1 à 4 (1/2 pour un vrai/faux)"),
            ("v3_text", PROMPT_LABELS["v3_text"], "0", "le texte exact de l'option (True/False)"),
            ("v4_letters_hot", PROMPT_LABELS["v4_letters_hot"], "1", "comme v1_letters : sert uniquement à l'analyse de la température"),
        ],
        columns=["Prompt", "Libellé", "Température", "Réponse attendue"],
    ),
    hide_index=True,
)

# --- Règle de correction ------------------------------------------------------------------
section("La règle de correction")
st.markdown(
    "1. Le raisonnement éventuel (`<think>…</think>`) et le préfixe « Answer: » sont retirés.\n"
    "2. **Prompts lettres et chiffres** : le premier mot doit être une étiquette autorisée (`C`, `(C)`, `C.`). "
    "« C. Canada » est accepté si le texte correspond bien à l'option C.\n"
    "3. **Prompt texte** : la première ligne, mise en minuscules et sans ponctuation finale, doit être égale à une option.\n"
    "4. Sinon la réponse est **au format invalide** (par exemple « The answer is C ») et **compte comme fausse** dans la précision."
)

# --- Définitions ------------------------------------------------------------------------
section("Définitions des indicateurs")
st.dataframe(
    pd.DataFrame([(name, column, HELP[key]) for name, column, key in DEFINITIONS], columns=["Indicateur", "Colonne", "Définition"]),
    hide_index=True,
    column_config={"Définition": st.column_config.TextColumn(width="large")},
)

# --- Limites ----------------------------------------------------------------------------
section("Les limites")
st.markdown(
    "- **4 modèles seulement** : le pays et l'éditeur sont confondus avec la taille, on observe sans généraliser.\n"
    "- **Une seule exécution par configuration** : pas de mesure de la variabilité d'une exécution à l'autre.\n"
    "- **Température 1 non reproductible** à l'identique : une nouvelle exécution donnerait des chiffres légèrement différents.\n"
    "- **Questions OpenTDB en anglais**, orientées culture occidentale, et publiques : les modèles ont pu les voir à l'entraînement.\n"
    "- **Petites catégories peu fiables** : sous 30 questions, l'intervalle de confiance est très large (éléments estompés dans l'app).\n"
    "- **Temps de réponse liés à la machine** : ils ne se comparent qu'entre modèles exécutés au même endroit."
)
