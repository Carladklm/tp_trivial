"""Page 7 — Questions pièges et difficulté réelle (source : gold.mart_question_insights)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import altair as alt
import pandas as pd
import streamlit as st

from lib import charts
from lib.data import load_model_profile, load_question_insights
from lib.style import (
    DIFFICULTY_COLORS,
    DIFFICULTY_ORDER,
    HELP,
    QUESTION_TYPE_ORDER,
    as_percent,
    difficulty_label,
    fmt_pct,
    fmt_pts,
    kpi,
    multi_filter,
    ordered,
    page_setup,
    pct_progress,
    section,
    stop_if_empty,
    type_label,
    with_labels,
)

page_setup(
    "Questions pièges",
    "quelles questions font tomber tous les modèles, et la difficulté annoncée par OpenTDB est-elle réaliste ?",
)

insights = with_labels(load_question_insights())
stop_if_empty(insights)
insights["ai_difficulty_label"] = insights["ai_difficulty"].map(difficulty_label)

st.sidebar.header("Filtres")
groups = multi_filter("Famille de catégorie", insights["category_group"], key="groups")
difficulties = multi_filter("Difficulté annoncée", insights["difficulty"], DIFFICULTY_ORDER, difficulty_label, key="difficulties")
types = multi_filter("Type de question", insights["question_type"], QUESTION_TYPE_ORDER, type_label, key="types")
search = st.sidebar.text_input("Rechercher dans les questions")

selection = insights[
    insights["category_group"].isin(groups)
    & insights["difficulty"].isin(difficulties)
    & insights["question_type"].isin(types)
]
if search:
    selection = selection[selection["question_text"].str.contains(search, case=False, regex=False)]
stop_if_empty(selection)

st.caption(f"{len(selection):,} questions sélectionnées sur {len(insights):,}.".replace(",", " "))

# --- Indicateurs -----------------------------------------------------------------
cols = st.columns(4)
with cols[0]:
    kpi("Ratées par tous", fmt_pct(selection["is_all_wrong"].mean()), "pink",
        delta=f"{int(selection['is_all_wrong'].sum())} questions", help="Aucune des réponses à température 0 n'est juste.")
with cols[1]:
    kpi("Pièges communs", f"{int(selection['is_common_trap'].sum())}", "orange",
        delta="même mauvaise réponse", help=HELP["is_common_trap"])
with cols[2]:
    kpi("Réussies par tous", fmt_pct(selection["is_all_correct"].mean()), "green",
        delta=f"{int(selection['is_all_correct'].sum())} questions", help="Toutes les réponses à température 0 sont justes.")
with cols[3]:
    # Comparaison sur l'ensemble des questions : la précision du meilleur modèle n'existe pas par filtre.
    profile = load_model_profile()
    majority = insights["is_majority_correct"].mean()
    best = profile.sort_values("accuracy", ascending=False).iloc[0] if not profile.empty else None
    kpi("Vote à la majorité", fmt_pct(majority), "blue",
        delta=None if best is None else f"{fmt_pts(majority - best['accuracy'])} vs {best['model_name']} seul",
        help=HELP["is_majority_correct"])

if best is not None:
    better = majority > best["accuracy"]
    n_total = f"{len(insights):,}".replace(",", " ")
    st.markdown(
        "**Plusieurs petits modèles ensemble font-ils mieux que le meilleur seul ?** "
        f"Sur l'ensemble des {n_total} questions, le vote à la majorité des modèles obtient {fmt_pct(majority)}, "
        f"contre {fmt_pct(best['accuracy'])} pour {best['model_name']} seul : "
        + ("**oui**, le collectif fait mieux." if better else "**non**, le meilleur modèle seul reste devant.")
    )
    st.caption("Cette comparaison porte toujours sur toutes les questions, quels que soient les filtres.")

# --- Difficulté annoncée contre vécue ------------------------------------------------------
left, right = st.columns(2, gap="large")
with left:
    section("Difficulté annoncée contre difficulté vécue")
    announced_sort = [difficulty_label(d) for d in ordered(selection["difficulty"], DIFFICULTY_ORDER)]
    lived_sort = [difficulty_label(d) for d in DIFFICULTY_ORDER]
    cross = pd.crosstab(selection["difficulty"], selection["ai_difficulty"]).reindex(
        index=ordered(selection["difficulty"], DIFFICULTY_ORDER), columns=DIFFICULTY_ORDER, fill_value=0
    )
    row_share = cross.div(cross.sum(axis=1), axis=0)
    matrix = (
        cross.stack().rename("n").to_frame()
        .join(row_share.stack().rename("row_share"))
        .reset_index()
        .rename(columns={"difficulty": "announced", "ai_difficulty": "lived"})
    )
    matrix["announced_label"] = matrix["announced"].map(difficulty_label)
    matrix["lived_label"] = matrix["lived"].map(difficulty_label)
    matrix["cell"] = matrix["n"].astype(str) + " (" + matrix["row_share"].map(lambda x: f"{x * 100:.0f} %") + ")"
    charts.show(
        charts.heatmap(
            matrix,
            x="lived_label",
            y="announced_label",
            value="row_share",
            title="Nombre de questions (part de la ligne)",
            x_title="Difficulté vécue par les modèles",
            y_title="Difficulté annoncée (OpenTDB)",
            x_sort=lived_sort,
            y_sort=announced_sort,
            text="cell",
            tooltip=[
                alt.Tooltip("announced_label:N", title="Annoncée"),
                alt.Tooltip("lived_label:N", title="Vécue"),
                alt.Tooltip("n:Q", title="Questions"),
                alt.Tooltip("row_share:Q", title="Part de la ligne", format=".1%"),
            ],
        )
    )
    diagonal = sum(cross.at[d, d] for d in cross.index if d in cross.columns) / max(int(cross.values.sum()), 1)
    st.caption(
        f"La diagonale correspond aux questions où OpenTDB et les modèles sont d'accord : **{fmt_pct(diagonal)}** des questions. "
        f"{HELP['ai_difficulty']}"
    )
with right:
    section("Distribution du taux de réussite")
    hist = (
        selection.assign(score=(selection["success_rate"] * selection["n_answers"]).round().astype(int))
        .assign(bucket=lambda d: d["score"].astype(str) + "/" + d["n_answers"].astype(str))
        .groupby(["score", "bucket", "difficulty", "difficulty_label"], as_index=False)
        .size()
        .rename(columns={"size": "n"})
        .sort_values("score")
    )
    hist["color_rank"] = hist["difficulty"].map({d: i for i, d in enumerate(DIFFICULTY_ORDER)})
    present = ordered(hist["difficulty"], DIFFICULTY_ORDER)
    scale = alt.Scale(
        domain=[difficulty_label(d) for d in present], range=[DIFFICULTY_COLORS.get(d, "#999999") for d in present]
    )
    charts.show(
        charts.histogram(
            hist,
            x="bucket",
            x_sort=hist["bucket"].unique().tolist(),
            color="difficulty_label",
            color_scale=scale,
            color_sort=[difficulty_label(d) for d in present],
            title="Questions selon le nombre de réponses justes",
            x_title="Réponses justes sur le total (tous modèles, prompts à T=0)",
        )
    )
    st.caption(
        "À gauche, les questions que personne ne réussit ; à droite, celles que tous les modèles réussissent. "
        "La couleur indique la difficulté annoncée par OpenTDB."
    )

# --- Pièges communs ---------------------------------------------------------------------
section("Pièges communs : tous les modèles se trompent de la même façon")
traps = selection[selection["is_common_trap"]].sort_values("top_wrong_votes", ascending=False)
if traps.empty:
    st.info("Aucun piège commun dans cette sélection.")
else:
    st.dataframe(
        traps,
        hide_index=True,
        column_order=["question_text", "category_name", "difficulty_label", "correct_answer", "top_wrong_answer", "top_wrong_votes", "n_answers"],
        column_config={
            "question_text": st.column_config.TextColumn("Question", width="large"),
            "category_name": "Catégorie",
            "difficulty_label": "Difficulté",
            "correct_answer": "Bonne réponse",
            "top_wrong_answer": "Mauvaise réponse la plus donnée",
            "top_wrong_votes": st.column_config.NumberColumn("Votes pour cette réponse"),
            "n_answers": st.column_config.NumberColumn("Réponses au total"),
        },
    )
    st.caption(f"{HELP['is_common_trap']} Triés par nombre de votes pour la mauvaise réponse.")

# --- Explorateur ------------------------------------------------------------------------
section("Explorateur des questions")
st.dataframe(
    as_percent(selection.sort_values("success_rate"), ["success_rate"]),
    hide_index=True,
    column_order=[
        "question_text", "category_group", "category_name", "type_label", "difficulty_label", "ai_difficulty_label",
        "correct_answer", "success_rate", "n_correct", "n_answers", "majority_answer", "is_majority_correct", "is_common_trap",
    ],
    column_config={
        "question_text": st.column_config.TextColumn("Question", width="large"),
        "category_group": "Famille",
        "category_name": "Catégorie",
        "type_label": "Type",
        "difficulty_label": "Difficulté annoncée",
        "ai_difficulty_label": st.column_config.TextColumn("Difficulté vécue", help=HELP["ai_difficulty"]),
        "correct_answer": "Bonne réponse",
        "success_rate": pct_progress("Taux de réussite"),
        "n_correct": st.column_config.NumberColumn("Réponses justes"),
        "n_answers": st.column_config.NumberColumn("Réponses"),
        "majority_answer": "Réponse majoritaire",
        "is_majority_correct": st.column_config.CheckboxColumn("Majorité juste", help=HELP["is_majority_correct"]),
        "is_common_trap": st.column_config.CheckboxColumn("Piège commun", help=HELP["is_common_trap"]),
    },
)
