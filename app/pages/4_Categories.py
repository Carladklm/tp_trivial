"""Page 4 — Catégories : thèmes forts et faibles de chaque modèle (source : gold.mart_perf_by_category)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import altair as alt
import pandas as pd
import streamlit as st

from lib import charts
from lib.data import load_perf_by_category
from lib.style import (
    CONFOUNDING_NOTE,
    fmt_pct,
    fmt_pts,
    model_order,
    model_scale,
    page_setup,
    prompt_filter,
    prompt_label,
    section,
    stop_if_empty,
)

FAMILIES = "Familles (category_group)"
CATEGORIES = "Catégories (category_name)"
ACCURACY = "Précision"
DELTA = "Écart à la moyenne du modèle"
POP_CULTURE = ["Film", "Music", "Television"]

page_setup("Catégories", "chaque modèle a-t-il des thèmes forts et faibles ?")

perf = load_perf_by_category()
stop_if_empty(perf)

st.sidebar.header("Filtres")
prompt = prompt_filter(perf)
level = st.sidebar.radio("Niveau de détail", [FAMILIES, CATEGORIES])
mode = st.sidebar.radio("Affichage", [ACCURACY, DELTA])

current = perf[perf["prompt_version"] == prompt]
stop_if_empty(current)
order = model_order(current)


def by_family(df: pd.DataFrame) -> pd.DataFrame:
    """Regroupe les catégories par famille : précision = somme des bonnes réponses / somme des questions."""
    grouped = (
        df.groupby(["model_key", "model_name", "category_group"], as_index=False)
        .agg(n_correct=("n_correct", "sum"), n_questions=("n_questions", "sum"), model_accuracy=("model_accuracy", "first"))
        .assign(accuracy=lambda d: d["n_correct"] / d["n_questions"])
    )
    grouped["delta_vs_model_average"] = grouped["accuracy"] - grouped["model_accuracy"]
    totals = grouped.groupby("category_group")[["n_correct", "n_questions"]].transform("sum")
    grouped["category_accuracy_all_models"] = totals["n_correct"] / totals["n_questions"]
    grouped["rank_in_category"] = grouped.groupby("category_group")["accuracy"].rank(ascending=False, method="min").astype(int)
    return grouped.rename(columns={"category_group": "category"})


if level == FAMILIES:
    view = by_family(current)
    ci_tooltip = []
else:
    view = current.rename(columns={"category_name": "category"})
    ci_tooltip = [
        alt.Tooltip("accuracy_ci_low:Q", title="IC 95 % bas", format=".1%"),
        alt.Tooltip("accuracy_ci_high:Q", title="IC 95 % haut", format=".1%"),
    ]

category_sort = (
    view.drop_duplicates("category").sort_values("category_accuracy_all_models", ascending=False)["category"].tolist()
)
value = "accuracy" if mode == ACCURACY else "delta_vs_model_average"

# --- Carte de chaleur --------------------------------------------------------------
section(f"Précision par thème — {prompt_label(prompt)}")
charts.show(
    charts.heatmap(
        view,
        x="model_name",
        y="category",
        value=value,
        title=f"{mode} par {'famille' if level == FAMILIES else 'catégorie'} et par modèle",
        x_title="Modèle",
        y_title=None,
        x_sort=order,
        y_sort=category_sort,
        diverging=mode == DELTA,
        value_format=".0%" if mode == ACCURACY else "+.0%",
        row_step=34,
        tooltip=[
            alt.Tooltip("category:N", title="Thème"),
            alt.Tooltip("model_name:N", title="Modèle"),
            alt.Tooltip("accuracy:Q", title="Précision", format=".1%"),
            *ci_tooltip,
            alt.Tooltip("delta_vs_model_average:Q", title="Écart à la moyenne du modèle", format="+.1%"),
            alt.Tooltip("rank_in_category:Q", title="Rang du modèle sur ce thème"),
            alt.Tooltip("sample_note:N", title="Effectif"),
        ],
    )
)
st.caption(
    "Les thèmes sont triés du plus réussi au moins réussi, tous modèles confondus. "
    + (
        "En mode écart, une case bleue indique un thème où le modèle fait mieux que sa propre moyenne, une case rouge moins bien. "
        if mode == DELTA
        else "Plus la case est foncée, plus la précision est élevée. "
    )
    + "Les cases estompées portent sur moins de 30 questions : leur valeur est peu fiable."
)

# --- Meilleur modèle et zoom ----------------------------------------------------------
left, right = st.columns([2, 3], gap="large")
with left:
    section("Premier sur le plus de catégories")
    wins = (
        current[current["is_best_in_category"]]
        .groupby(["model_key", "model_name"], as_index=False)
        .agg(n_wins=("category_name", "nunique"))
    )
    wins = (
        current.drop_duplicates("model_key")[["model_key", "model_name"]]
        .merge(wins, on=["model_key", "model_name"], how="left")
        .fillna({"n_wins": 0})
    )
    charts.show(
        alt.Chart(wins)
        .mark_bar(cornerRadiusEnd=4, height={"band": 0.6})
        .encode(
            y=alt.Y("model_name:N", sort=order, title=None, axis=alt.Axis(labelLimit=320)),
            x=alt.X("n_wins:Q", title="Nombre de catégories où le modèle est premier", axis=alt.Axis(tickMinStep=1)),
            color=alt.Color("model_name:N", scale=model_scale(wins), legend=None),
            tooltip=[alt.Tooltip("model_name:N", title="Modèle"), alt.Tooltip("n_wins:Q", title="Catégories gagnées")],
        )
        .properties(title=f"Catégories gagnées (sur {current['category_name'].nunique()})", height=alt.Step(52))
    )
    st.caption("Compté au niveau des catégories détaillées, pour le prompt choisi.")
with right:
    section("Zoom sur un modèle")
    chosen = st.selectbox("Modèle", order, key="zoom_model")
    zoom = view[view["model_name"] == chosen].sort_values("delta_vs_model_average", ascending=False).reset_index(drop=True)
    highlight = set(zoom.head(3)["category"]) | set(zoom.tail(3)["category"])
    zoom = zoom.assign(highlight=zoom["category"].isin(highlight))
    charts.show(
        charts.signed_bars(
            zoom,
            y="category",
            value="delta_vs_model_average",
            title=f"{chosen} : écart à sa moyenne par thème",
            x_title="Écart à la moyenne du modèle (points)",
            tooltip=[
                alt.Tooltip("category:N", title="Thème"),
                alt.Tooltip("accuracy:Q", title="Précision", format=".1%"),
                alt.Tooltip("delta_vs_model_average:Q", title="Écart", format="+.1%"),
                alt.Tooltip("n_questions:Q", title="n"),
            ],
        )
    )
    strong = ", ".join(zoom.head(3)["category"])
    weak = ", ".join(zoom.tail(3)["category"][::-1])
    st.caption(f"Les 3 points forts ({strong}) et les 3 points faibles ({weak}) sont mis en évidence ; les autres thèmes sont estompés.")

# --- Hypothèse --------------------------------------------------------------------
section("Hypothèse : Qwen (modèle chinois) est-il plus faible sur la pop culture occidentale ?")
pop = current[current["category_name"].isin(POP_CULTURE)]
qwen_keys = set(current.loc[current["model_name"].str.contains("Qwen", case=False), "model_key"])
if pop.empty or not qwen_keys:
    st.info("Qwen ou les catégories Film, Music et Television sont absents de la sélection : l'hypothèse ne peut pas être vérifiée.")
else:
    pop_by_model = (
        pop.groupby(["model_key", "model_name"], as_index=False)
        .agg(n_correct=("n_correct", "sum"), n_questions=("n_questions", "sum"), model_accuracy=("model_accuracy", "first"))
        .assign(pop_accuracy=lambda d: d["n_correct"] / d["n_questions"])
        .assign(delta=lambda d: d["pop_accuracy"] - d["model_accuracy"])
    )
    qwen = pop_by_model[pop_by_model["model_key"].isin(qwen_keys)].iloc[0]
    others = pop_by_model[~pop_by_model["model_key"].isin(qwen_keys)]
    others_txt = ", ".join(f"{r.model_name} {fmt_pts(r.delta)}" for r in others.itertuples())
    weaker = not others.empty and qwen["delta"] < others["delta"].min()
    verdict = (
        "Qwen recule plus que tous les autres modèles sur ces thèmes : l'hypothèse est **compatible** avec les données."
        if weaker
        else "Qwen ne recule pas plus que les autres modèles sur ces thèmes : les données ne **soutiennent pas** l'hypothèse."
    )
    st.info(
        f"Sur Film, Music et Television ({int(qwen['n_questions'])} questions), {qwen['model_name']} obtient "
        f"{fmt_pct(qwen['pop_accuracy'])}, soit **{fmt_pts(qwen['delta'])}** par rapport à sa propre moyenne. "
        f"Écart des autres modèles sur les mêmes thèmes : {others_txt or '—'}.\n\n{verdict}\n\n{CONFOUNDING_NOTE}"
    )
