"""Page 1 — Modèles : taille, éditeur, pays et efficacité (source : gold.mart_model_profile)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import altair as alt
import streamlit as st

from lib import charts
from lib.data import load_leaderboard, load_model_profile
from lib.style import (
    CONFOUNDING_NOTE,
    HELP,
    MUTED,
    TRIVIAL,
    as_percent,
    fmt_pct,
    fmt_seconds,
    model_filter,
    model_order,
    page_setup,
    pct_number,
    pct_progress,
    prompt_label,
    section,
    stop_if_empty,
)

page_setup("Modèles", "un modèle plus gros, ou d'un autre pays, fait-il mieux ? À quel coût en temps ?")

profile = load_model_profile()
stop_if_empty(profile)

st.sidebar.header("Filtres")
models = model_filter(profile)
profile = profile[profile["model_key"].isin(models)]
stop_if_empty(profile)

# Niveau du hasard lu dans le classement (prompts à T=0, mêmes questions pour tous les modèles).
leaderboard = load_leaderboard()
baseline = leaderboard.loc[leaderboard["temperature"] == 0, ["model_key", "random_baseline"]].drop_duplicates("model_key")
profile = profile.merge(baseline, on="model_key", how="left")
order = model_order(profile)

st.info(CONFOUNDING_NOTE)

# --- Synthèse ----------------------------------------------------------------
ranked = profile.sort_values("accuracy", ascending=False)
best, fastest = ranked.iloc[0], profile.sort_values("avg_response_time_s").iloc[0]
largest = profile.sort_values("model_params_b").iloc[-1]
size_follows = ranked["model_params_b"].is_monotonic_decreasing
st.markdown(
    f"Le modèle le plus précis est **{best['model_name']}** ({fmt_pct(best['accuracy'])} sur les prompts à température 0). "
    + (
        "Le classement suit exactement la taille des modèles. "
        if size_follows and len(profile) > 1
        else f"Le plus gros modèle ({largest['model_name']}) n'est pas forcément le premier : le classement ne suit pas exactement la taille. "
    )
    + f"Le plus rapide est **{fastest['model_name']}** ({fmt_seconds(fastest['avg_response_time_s'])} par question)."
)

# --- Taille et vitesse ------------------------------------------------------------
section("Taille et vitesse")
left, right = st.columns(2, gap="large")
with left:
    charts.show(
        charts.model_scatter(
            profile,
            x="model_params_b",
            x_title="Taille du modèle, en milliards de paramètres",
            title="Taille contre précision",
            x_log=True,
            extra_tooltip=[alt.Tooltip("model_params_b:Q", title="Taille (Md)", format=".1f")],
        )
    )
    st.caption(
        "Chaque point est un modèle (moyenne des 3 prompts à température 0), le trait vertical est l'intervalle "
        "de confiance à 95 % et la ligne pointillée le niveau du hasard. L'axe horizontal est logarithmique."
    )
with right:
    charts.show(
        charts.model_scatter(
            profile,
            x="avg_response_time_s",
            x_title="Temps moyen par question (s)",
            title="Compromis précision / vitesse",
            x_format=".3f",
            size="model_params_b",
            size_title="Taille (Md)",
            extra_tooltip=[
                alt.Tooltip("avg_response_time_s:Q", title="Temps moyen (s)", format=".3f"),
                alt.Tooltip("correct_per_minute:Q", title="Bonnes réponses / min", format=".1f"),
                alt.Tooltip("model_params_b:Q", title="Taille (Md)", format=".1f"),
            ],
        )
    )
    st.caption(
        "En haut à gauche = rapide et précis. La taille du point est proportionnelle au nombre de paramètres. "
        "Les temps dépendent de la machine : ils ne se comparent qu'entre modèles exécutés au même endroit."
    )

# --- Connaissance, format et robustesse ---------------------------------------------
section("Connaissance, format et robustesse")
left, right = st.columns(2, gap="large")
with left:
    knowledge = profile.melt(
        id_vars=["model_name", "model_key", "model_params_b", "n_responses", "valid_format_rate"],
        value_vars=["accuracy", "accuracy_when_valid"],
        var_name="measure",
        value_name="value",
    ).assign(measure=lambda d: d["measure"].map({"accuracy": "Précision", "accuracy_when_valid": "Précision si format valide"}))
    measures = ["Précision", "Précision si format valide"]
    charts.show(
        charts.grouped_bars(
            knowledge,
            x="model_name",
            y="value",
            group="measure",
            group_scale=alt.Scale(domain=measures, range=[TRIVIAL["blue"], MUTED]),
            group_sort=measures,
            x_sort=order,
            title="Connaissance contre respect du format",
            x_title=None,
            y_title="Précision",
            y_domain=[0, 1],
            tooltip=[
                alt.Tooltip("model_name:N", title="Modèle"),
                alt.Tooltip("measure:N", title="Mesure"),
                alt.Tooltip("value:Q", title="Valeur", format=".1%"),
                alt.Tooltip("valid_format_rate:Q", title="Format valide", format=".1%"),
                alt.Tooltip("n_responses:Q", title="n"),
            ],
        )
    )
    st.caption(
        "L'écart entre les deux barres d'un modèle correspond aux points perdus parce que la réponse ne respectait "
        "pas le format demandé, et non par manque de connaissance."
    )
with right:
    spread = profile.assign(
        best_label=lambda d: d["best_prompt"].map(prompt_label),
        worst_label=lambda d: d["worst_prompt"].map(prompt_label),
    )
    charts.show(
        alt.Chart(spread)
        .mark_bar(cornerRadiusEnd=4, height={"band": 0.6})
        .encode(
            y=alt.Y("model_name:N", sort=order, title=None, axis=alt.Axis(labelLimit=320)),
            x=alt.X("prompt_spread:Q", title="Écart meilleur − pire prompt (points)", axis=alt.Axis(format="%")),
            color=alt.Color("model_name:N", scale=charts.model_scale(spread), legend=None),
            tooltip=[
                alt.Tooltip("model_name:N", title="Modèle"),
                alt.Tooltip("prompt_spread:Q", title="Écart", format=".1%"),
                alt.Tooltip("best_label:N", title="Meilleur prompt"),
                alt.Tooltip("best_prompt_accuracy:Q", title="Précision (meilleur)", format=".1%"),
                alt.Tooltip("worst_label:N", title="Pire prompt"),
                alt.Tooltip("worst_prompt_accuracy:Q", title="Précision (pire)", format=".1%"),
            ],
        )
        .properties(title="Robustesse au prompt", height=alt.Step(52))
    )
    st.caption(f"{HELP['prompt_spread']} Seuls les 3 prompts à température 0 sont comparés.")

# --- Tableau ---------------------------------------------------------------------
section("Profil des modèles")
table = as_percent(
    ranked.assign(best_label=ranked["best_prompt"].map(prompt_label), worst_label=ranked["worst_prompt"].map(prompt_label)),
    ["accuracy", "accuracy_ci_low", "accuracy_ci_high", "valid_format_rate", "best_prompt_accuracy", "worst_prompt_accuracy"],
)
st.dataframe(
    table,
    hide_index=True,
    column_order=[
        "accuracy_rank", "model_name", "model_publisher", "model_country", "model_params_b", "size_class",
        "accuracy", "accuracy_ci_low", "accuracy_ci_high", "chance_corrected_score", "valid_format_rate",
        "best_label", "best_prompt_accuracy", "worst_label", "worst_prompt_accuracy",
        "avg_response_time_s", "correct_per_minute",
    ],
    column_config={
        "accuracy_rank": st.column_config.NumberColumn("Rang"),
        "model_name": "Modèle",
        "model_publisher": "Éditeur",
        "model_country": "Pays",
        "model_params_b": st.column_config.NumberColumn("Taille (Md)", format="%.1f"),
        "size_class": "Classe de taille",
        "accuracy": pct_progress("Précision", HELP["accuracy"]),
        "accuracy_ci_low": pct_number("IC bas", HELP["ci"]),
        "accuracy_ci_high": pct_number("IC haut", HELP["ci"]),
        "chance_corrected_score": st.column_config.NumberColumn("Score corrigé", help=HELP["chance_corrected_score"], format="%.3f"),
        "valid_format_rate": pct_progress("Format valide", HELP["valid_format_rate"]),
        "best_label": "Meilleur prompt",
        "best_prompt_accuracy": pct_number("Précision (meilleur)"),
        "worst_label": "Pire prompt",
        "worst_prompt_accuracy": pct_number("Précision (pire)"),
        "avg_response_time_s": st.column_config.NumberColumn("Temps moyen (s)", format="%.3f"),
        "correct_per_minute": st.column_config.NumberColumn("Bonnes réponses / min", help=HELP["correct_per_minute"], format="%.1f"),
    },
)
