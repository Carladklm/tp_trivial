"""Page 3 — Température : effet de T=1 sur la précision et la régularité (source : gold.mart_temperature_effect)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import altair as alt
import streamlit as st

from lib import charts
from lib.data import load_leaderboard, load_temperature_effect
from lib.style import (
    DIFFICULTY_ORDER,
    HELP,
    difficulty_label,
    fmt_pct,
    fmt_pts,
    model_filter,
    model_order,
    model_scale,
    ordered,
    page_setup,
    section,
    stop_if_empty,
    with_labels,
)

page_setup("Température", "ajouter de l'aléatoire (T=1) fait-il perdre en précision et en régularité ?")

effect = load_temperature_effect()
stop_if_empty(effect)

st.sidebar.header("Filtres")
models = model_filter(effect)
effect = with_labels(effect[effect["model_key"].isin(models)])
stop_if_empty(effect)

st.warning(
    "À température 1, les réponses sont tirées au hasard parmi les plus probables : relancer l'exécution "
    "donnerait des chiffres légèrement différents."
)

overall = effect[effect["difficulty"] == "all"]
by_difficulty = effect[effect["difficulty"] != "all"]
leaderboard = load_leaderboard()
baseline = leaderboard.loc[leaderboard["prompt_version"] == "v1_letters", ["model_key", "random_baseline"]]
overall = overall.merge(baseline, on="model_key", how="left")
order = model_order(effect)

# --- Synthèse ----------------------------------------------------------------
if not overall.empty:
    worst = overall.sort_values("accuracy_delta").iloc[0]
    steady = overall.sort_values("answer_stability", ascending=False).iloc[0]
    st.markdown(
        f"La plus forte variation de précision est celle de **{worst['model_name']}** "
        f"({fmt_pts(worst['accuracy_delta'])} en passant de T=0 à T=1). "
        f"Le modèle le plus régulier est **{steady['model_name']}**, qui garde la même réponse sur "
        f"{fmt_pct(steady['answer_stability'])} des questions."
    )

# --- Précision et stabilité ------------------------------------------------------------
section("Précision et stabilité")
left, right = st.columns(2, gap="large")
with left:
    if overall.empty:
        st.info("Aucune donnée pour cette sélection.")
    else:
        charts.show(charts.dumbbell(overall, "Précision à T=0 et à T=1"))
        st.caption(
            "Pour chaque modèle, le point bleu est la précision à température 0 et le point rouge à température 1, "
            "sur les mêmes questions avec le prompt lettres. Plus le segment est long, plus l'aléatoire change le score."
        )
with right:
    if not overall.empty:
        charts.show(
            alt.Chart(overall)
            .mark_bar(cornerRadiusEnd=4, height={"band": 0.6})
            .encode(
                y=alt.Y("model_name:N", sort=order, title=None, axis=alt.Axis(labelLimit=320)),
                x=alt.X("answer_stability:Q", title="Réponses identiques à T=0 et T=1", scale=alt.Scale(domain=[0, 1]), axis=alt.Axis(format="%")),
                color=alt.Color("model_name:N", scale=model_scale(overall), legend=None),
                tooltip=[
                    alt.Tooltip("model_name:N", title="Modèle"),
                    alt.Tooltip("answer_stability:Q", title="Stabilité", format=".1%"),
                    alt.Tooltip("n_questions:Q", title="n"),
                ],
            )
            .properties(title="Stabilité des réponses", height=alt.Step(52))
        )
        st.caption(f"{HELP['answer_stability']} 100 % = le modèle répond exactement pareil malgré l'aléatoire.")

# --- Par difficulté et flux -------------------------------------------------------------
section("Où l'aléatoire coûte-t-il des points ?")
left, right = st.columns(2, gap="large")
with left:
    if by_difficulty.empty:
        st.info("Aucune donnée pour cette sélection.")
    else:
        difficulty_sort = [difficulty_label(d) for d in ordered(by_difficulty["difficulty"], DIFFICULTY_ORDER)]
        charts.show(
            charts.grouped_bars(
                by_difficulty, x="difficulty_label", y="accuracy_delta", group="model_name",
                group_scale=model_scale(by_difficulty), group_sort=order, x_sort=difficulty_sort,
                title="Écart de précision T=1 − T=0 par difficulté", x_title="Difficulté annoncée",
                y_title="Écart de précision (points)", y_format="+%",
                tooltip=[
                    alt.Tooltip("model_name:N", title="Modèle"),
                    alt.Tooltip("difficulty_label:N", title="Difficulté"),
                    alt.Tooltip("accuracy_cold:Q", title="Précision T=0", format=".1%"),
                    alt.Tooltip("accuracy_hot:Q", title="Précision T=1", format=".1%"),
                    alt.Tooltip("accuracy_delta:Q", title="Écart", format="+.1%"),
                    alt.Tooltip("sample_note:N", title="Effectif"),
                ],
            )
        )
        st.caption(
            "Une barre sous zéro = le modèle perd des points à T=1. Hypothèse à vérifier : l'effet est plus fort sur "
            "les questions difficiles, où le modèle hésite davantage entre plusieurs options."
        )
with right:
    if not overall.empty:
        charts.show(charts.diverging_flow(overall, "Réponses perdues et gagnées à T=1"))
        st.caption(
            "À gauche, la part des questions justes à T=0 devenues fausses à T=1 ; à droite, celles fausses à T=0 "
            "devenues justes par chance. L'écart entre les deux donne la variation de précision."
        )
