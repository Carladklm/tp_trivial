"""Page d'accueil : classement général des modèles (source : gold.mart_leaderboard)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import altair as alt
import streamlit as st

from lib import charts
from lib.data import load_leaderboard
from lib.style import (
    ALL_PROMPTS,
    HELP,
    PROMPT_ORDER,
    as_percent,
    fmt_pct,
    fmt_pts,
    kpi,
    model_order,
    page_setup,
    pct_number,
    pct_progress,
    prompt_filter,
    prompt_label,
    model_filter,
    section,
    stop_if_empty,
)

page_setup("Classement général", "quel modèle, avec quel prompt, répond le mieux ?")

leaderboard = load_leaderboard()
stop_if_empty(leaderboard)

st.sidebar.header("Filtres")
prompt = prompt_filter(leaderboard, allow_all=True)
models = model_filter(leaderboard)

selection = leaderboard[leaderboard["model_key"].isin(models)].assign(
    prompt_label=lambda d: d["prompt_version"].map(prompt_label)
)
# « Tous les prompts » classe les exécutions (modèle × prompt) sans jamais les moyenner.
all_prompts = prompt == ALL_PROMPTS
current = selection if all_prompts else selection[selection["prompt_version"] == prompt]
stop_if_empty(current)

label = "run_label" if all_prompts else "model_name"
ranking = (
    current.assign(run_label=current["model_name"] + " · " + current["prompt_label"])
    .sort_values("accuracy", ascending=False)
    .reset_index(drop=True)
)
best = ranking.iloc[0]
second = ranking.iloc[1] if len(ranking) > 1 else None


def questions_per_model() -> str:
    """Nombre de questions par modèle, ou la plage si les modèles n'en ont pas le même nombre."""
    low, high = ranking["n_questions"].min(), ranking["n_questions"].max()
    return f"{low:,}".replace(",", " ") if low == high else f"{low:,} – {high:,}".replace(",", " ")


# --- Indicateurs -----------------------------------------------------------
cols = st.columns(4)
with cols[0]:
    kpi("Meilleur modèle", best["model_name"], "blue", delta=prompt_label(best["prompt_version"]))
with cols[1]:
    kpi(
        "Sa précision",
        fmt_pct(best["accuracy"]),
        "green",
        delta=f"IC 95 % : {fmt_pct(best['accuracy_ci_low'])} – {fmt_pct(best['accuracy_ci_high'])}",
        help=HELP["accuracy"],
    )
with cols[2]:
    gap = None if second is None else best["accuracy"] - second["accuracy"]
    kpi(
        "Écart avec le 2e",
        "—" if gap is None else fmt_pts(gap).replace("+", ""),
        "orange",
        delta=None if second is None else f"devant {second[label]}",
    )
with cols[3]:
    compared = f"{len(ranking)} exécutions comparées" if all_prompts else f"{len(ranking)} modèles comparés"
    kpi("Questions par modèle", questions_per_model(), "pink", delta=compared)

# --- Graphiques principaux ---------------------------------------------------
section("Précision et nature des erreurs")
left, right = st.columns([3, 2], gap="large")
with left:
    charts.show(charts.accuracy_bars(ranking, f"Précision — {prompt_label(prompt)}", label=label))
with right:
    charts.show(
        charts.status_stack(ranking, "Juste, faux ou format invalide", order=ranking[label].tolist(), label=label)
    )

# --- Vue d'ensemble des 16 exécutions ----------------------------------------
section("Vue d'ensemble des exécutions")
present_prompts = [p for p in PROMPT_ORDER if p in set(selection["prompt_version"])]
charts.show(
    charts.heatmap(
        selection,
        x="prompt_label",
        y="model_name",
        value="accuracy",
        title="Précision par modèle et par prompt",
        x_title="Prompt",
        y_title="Modèle",
        x_sort=[prompt_label(p) for p in present_prompts],
        y_sort=model_order(selection),
        tooltip=[
            alt.Tooltip("model_name:N", title="Modèle"),
            alt.Tooltip("prompt_label:N", title="Prompt"),
            alt.Tooltip("accuracy:Q", title="Précision", format=".1%"),
            alt.Tooltip("accuracy_ci_low:Q", title="IC 95 % bas", format=".1%"),
            alt.Tooltip("accuracy_ci_high:Q", title="IC 95 % haut", format=".1%"),
            alt.Tooltip("valid_format_rate:Q", title="Format valide", format=".1%"),
            alt.Tooltip("sample_note:N", title="Effectif"),
        ],
    )
)

# --- Tableau détaillé ----------------------------------------------------------
section(f"Détail — {prompt_label(prompt)}")
pct_cols = [
    "accuracy",
    "accuracy_ci_low",
    "accuracy_ci_high",
    "random_baseline",
    "valid_format_rate",
    "accuracy_when_valid",
    "truncated_rate",
]
table = as_percent(ranking, pct_cols)
st.dataframe(
    table,
    hide_index=True,
    column_order=[
        "accuracy_rank",
        "model_name",
        *(["prompt_label", "temperature"] if all_prompts else []),
        "model_publisher",
        "model_country",
        "model_params_b",
        "accuracy",
        "accuracy_ci_low",
        "accuracy_ci_high",
        "random_baseline",
        "chance_corrected_score",
        "valid_format_rate",
        "accuracy_when_valid",
        "truncated_rate",
        "avg_response_time_s",
        "p95_response_time_s",
        "avg_completion_tokens",
        "correct_per_minute",
        "n_questions",
        "n_correct",
    ],
    column_config={
        "accuracy_rank": st.column_config.NumberColumn("Rang global", help="Rang parmi les 16 exécutions."),
        "model_name": "Modèle",
        "prompt_label": "Prompt",
        "temperature": st.column_config.NumberColumn("Température", format="%.1f"),
        "model_publisher": "Éditeur",
        "model_country": "Pays",
        "model_params_b": st.column_config.NumberColumn("Taille (Md)", format="%.1f"),
        "accuracy": pct_progress("Précision", HELP["accuracy"]),
        "accuracy_ci_low": pct_number("IC bas", HELP["ci"]),
        "accuracy_ci_high": pct_number("IC haut", HELP["ci"]),
        "random_baseline": pct_number("Hasard", HELP["random_baseline"]),
        "chance_corrected_score": st.column_config.NumberColumn(
            "Score corrigé", help=HELP["chance_corrected_score"], format="%.3f"
        ),
        "valid_format_rate": pct_progress("Format valide", HELP["valid_format_rate"]),
        "accuracy_when_valid": pct_number("Précision si format valide", HELP["accuracy_when_valid"]),
        "truncated_rate": pct_number("Réponses tronquées"),
        "avg_response_time_s": st.column_config.NumberColumn("Temps moyen (s)", format="%.3f"),
        "p95_response_time_s": st.column_config.NumberColumn("Temps p95 (s)", format="%.3f"),
        "avg_completion_tokens": st.column_config.NumberColumn("Tokens moyens", format="%.1f"),
        "correct_per_minute": st.column_config.NumberColumn(
            "Bonnes réponses / min", help=HELP["correct_per_minute"], format="%.1f"
        ),
        "n_questions": st.column_config.NumberColumn("Questions"),
        "n_correct": st.column_config.NumberColumn("Bonnes réponses"),
    },
)
