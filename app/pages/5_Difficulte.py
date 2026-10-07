"""Page 5 — Difficulté et type de question, par rapport au hasard (source : gold.mart_perf_by_difficulty)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import altair as alt
import streamlit as st

from lib import charts
from lib.data import load_perf_by_difficulty
from lib.style import (
    DIFFICULTY_ORDER,
    HELP,
    QUESTION_TYPE_ORDER,
    difficulty_label,
    fmt_pct,
    model_order,
    ordered,
    page_setup,
    pct_number,
    prompt_filter,
    prompt_label,
    section,
    stop_if_empty,
    type_label,
    with_labels,
)

ACCURACY = "Précision"
CORRECTED = "Score corrigé du hasard"

page_setup("Difficulté", "comment la performance évolue-t-elle avec la difficulté, et par rapport au hasard ?")

perf = load_perf_by_difficulty()
stop_if_empty(perf)

st.sidebar.header("Filtres")
prompt = prompt_filter(perf)
metric = st.sidebar.radio("Métrique", [ACCURACY, CORRECTED])

current = with_labels(perf[perf["prompt_version"] == prompt])
stop_if_empty(current)

difficulty_sort = [difficulty_label(d) for d in ordered(current["difficulty"], DIFFICULTY_ORDER)]
type_sort = [type_label(t) for t in ordered(current["question_type"], QUESTION_TYPE_ORDER)]
order = model_order(current)

# --- Synthèse ----------------------------------------------------------------
easy_hard = current[current["difficulty"].isin(["easy", "hard"])]
if easy_hard["difficulty"].nunique() == 2:
    acc = easy_hard.groupby(["model_name", "difficulty"]).apply(
        lambda g: g["n_correct"].sum() / g["n_questions"].sum(), include_groups=False
    ).unstack()
    drop = (acc["easy"] - acc["hard"]).sort_values(ascending=False)
    st.markdown(
        f"Avec le prompt « {prompt_label(prompt)} », tous types confondus, **{drop.index[0]}** perd le plus entre "
        f"les questions faciles et difficiles ({fmt_pct(acc.loc[drop.index[0], 'easy'])} → {fmt_pct(acc.loc[drop.index[0], 'hard'])})."
    )

# --- Courbes ------------------------------------------------------------------------
section(f"{metric} selon la difficulté — {prompt_label(prompt)}")
tooltip = [
    alt.Tooltip("model_name:N", title="Modèle"),
    alt.Tooltip("type_label:N", title="Type"),
    alt.Tooltip("difficulty_label:N", title="Difficulté"),
    alt.Tooltip("accuracy:Q", title="Précision", format=".1%"),
    alt.Tooltip("accuracy_ci_low:Q", title="IC 95 % bas", format=".1%"),
    alt.Tooltip("accuracy_ci_high:Q", title="IC 95 % haut", format=".1%"),
    alt.Tooltip("chance_corrected_score:Q", title="Score corrigé", format=".3f"),
    alt.Tooltip("random_baseline:Q", title="Hasard", format=".0%"),
    alt.Tooltip("sample_note:N", title="Effectif"),
]
if metric == ACCURACY:
    chart = charts.faceted_lines(
        current, x="difficulty_label", x_sort=difficulty_sort, x_title="Difficulté annoncée",
        y="accuracy", y_title="Précision", facet="type_label", facet_sort=type_sort,
        title="Précision par difficulté et par type de question", ci=("accuracy_ci_low", "accuracy_ci_high"),
        baseline="random_baseline", y_domain=[0, 1], tooltip=tooltip,
    )
else:
    chart = charts.faceted_lines(
        current.assign(zero=0.0), x="difficulty_label", x_sort=difficulty_sort, x_title="Difficulté annoncée",
        y="chance_corrected_score", y_title="Score corrigé du hasard", facet="type_label", facet_sort=type_sort,
        title="Score corrigé du hasard par difficulté et par type de question", ci=None,
        baseline="zero", tooltip=tooltip,
    )
charts.show(chart)
st.caption(
    "Une ligne par modèle, un panneau par type de question. La ligne pointillée est le niveau du hasard "
    + ("(25 % pour un QCM, 50 % pour un vrai/faux) ; la bande colorée est l'intervalle de confiance à 95 %. " if metric == ACCURACY else "(0 en score corrigé). ")
    + "Les points estompés portent sur moins de 30 questions."
)
st.info(
    "**Pourquoi un score corrigé du hasard ?** Répondre au hasard donne déjà 50 % sur un vrai/faux contre 25 % sur un QCM : "
    "une précision de 60 % est donc médiocre en vrai/faux mais bonne en QCM. "
    f"{HELP['chance_corrected_score']} Il place les deux types de questions sur la même échelle."
)

# --- Tableau croisé ---------------------------------------------------------------------
section("Tableau croisé")
pivot = current.assign(column=current["difficulty_label"] + " · " + current["type_label"])
columns = [f"{d} · {t}" for t in type_sort for d in difficulty_sort]
table = (
    pivot.pivot_table(index="model_name", columns="column", values="accuracy", aggfunc="first")
    .reindex(index=order, columns=[c for c in columns if c in set(pivot["column"])])
    .mul(100)
    .reset_index()
)
st.dataframe(
    table,
    hide_index=True,
    column_config={"model_name": "Modèle", **{c: pct_number(c, HELP["accuracy"]) for c in columns}},
)
st.caption("Précision de chaque modèle par difficulté annoncée et par type de question, pour le prompt choisi.")
