"""Page 6 — Biais de position : préférence pour certaines options (source : gold.mart_position_bias)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import altair as alt
import streamlit as st

from lib import charts
from lib.data import load_position_bias
from lib.style import (
    HELP,
    QUESTION_TYPE_ORDER,
    fmt_pct,
    fmt_pts,
    model_order,
    ordered,
    page_setup,
    prompt_filter,
    prompt_label,
    section,
    stop_if_empty,
    type_label,
)

page_setup(
    "Biais de position",
    "les modèles ont-ils une préférence pour certaines options (A, ou True), indépendamment de la bonne réponse ?",
)

bias = load_position_bias()
stop_if_empty(bias)

st.sidebar.header("Filtres")
prompt = prompt_filter(bias)
types = ordered(bias["question_type"], QUESTION_TYPE_ORDER)
qtype = st.sidebar.radio("Type de question", types, format_func=type_label)

for_prompt = bias[bias["prompt_version"] == prompt]
current = for_prompt[for_prompt["question_type"] == qtype]
stop_if_empty(current)

order = model_order(current)
position_sort = current.drop_duplicates("position").sort_values("position")["position_label"].tolist()

if (current["label_style"] == "text").any():
    st.info("Avec le prompt texte, « position » désigne le rang de l'option dans la liste présentée au modèle.")

# --- Synthèse ----------------------------------------------------------------
strongest = current.loc[current["position_bias"].abs().idxmax()]
st.markdown(
    f"Biais le plus fort ({type_label(qtype)}, prompt « {prompt_label(prompt)} ») : **{strongest['model_name']}** "
    f"choisit l'option **{strongest['position_label']}** dans {fmt_pct(strongest['share_chosen'])} des cas, alors qu'elle n'est "
    f"la bonne réponse que dans {fmt_pct(strongest['share_expected'])} des cas, soit **{fmt_pts(strongest['position_bias'])}**."
)

# --- Réponses données vs bonnes réponses ------------------------------------------------
section(f"Réponses données et bonnes réponses — {type_label(qtype)}")
charts.show(charts.faceted_position_bars(current, "Part des réponses par option", x_sort=position_sort))
st.caption(
    "Pour chaque option, la barre claire est la part des réponses du modèle, la barre grise la part des questions dont "
    "c'est réellement la bonne réponse. Deux barres égales = aucun biais ; une barre claire plus haute = option sur-choisie."
)

# --- Carte de chaleur et Vrai/Faux ----------------------------------------------------------
left, right = st.columns([3, 2], gap="large")
with left:
    section("Carte du biais")
    charts.show(
        charts.heatmap(
            current,
            x="position_label",
            y="model_name",
            value="position_bias",
            title="Biais de position (points)",
            x_title="Option",
            y_title=None,
            x_sort=position_sort,
            y_sort=order,
            diverging=True,
            value_format="+.1%",
            tooltip=[
                alt.Tooltip("model_name:N", title="Modèle"),
                alt.Tooltip("position_label:N", title="Option"),
                alt.Tooltip("share_chosen:Q", title="Part choisie", format=".1%"),
                alt.Tooltip("share_expected:Q", title="Part attendue", format=".1%"),
                alt.Tooltip("position_bias:Q", title="Biais", format="+.1%"),
                alt.Tooltip("n_chosen:Q", title="Fois choisie"),
                alt.Tooltip("accuracy_when_correct_here:Q", title="Précision quand la bonne réponse est ici", format=".1%"),
            ],
        )
    )
    st.caption(f"{HELP['position_bias']} En bleu l'option est sur-choisie, en rouge sous-choisie.")
with right:
    section("Vrai/Faux : part de « True »")
    true_rows = for_prompt[(for_prompt["question_type"] == "boolean") & (for_prompt["position"] == 1)]
    if true_rows.empty:
        st.info("Aucune question vrai/faux pour ce prompt.")
    else:
        expected = true_rows["share_expected"].iloc[0]
        st.caption(f"Parmi les bonnes réponses, « True » représente **{fmt_pct(expected)}** des vrai/faux.")
        for row in true_rows.set_index("model_name").loc[[m for m in order if m in set(true_rows["model_name"])]].itertuples():
            st.metric(
                row.Index,
                f"{fmt_pct(row.share_chosen)} de « True »",
                delta=f"{fmt_pts(row.position_bias)} vs la part réelle",
                delta_color="off",
                help=HELP["position_bias"],
            )
