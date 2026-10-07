"""Page 2 — Formats de prompt : lettres, chiffres ou texte (source : gold.mart_prompt_format)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import altair as alt
import streamlit as st

from lib import charts
from lib.data import load_leaderboard, load_prompt_format
from lib.style import (
    FORMAT_COLORS,
    FORMAT_ORDER,
    GAIN_COLOR,
    HELP,
    LOSS_COLOR,
    as_percent,
    fmt_pct,
    fmt_pts,
    format_label,
    model_filter,
    model_order,
    ordered,
    page_setup,
    pct_number,
    pct_progress,
    section,
    stop_if_empty,
    with_labels,
)

page_setup("Formats de prompt", "demander la réponse en lettre, en chiffre ou en texte change-t-il le résultat ?")

formats = load_prompt_format()
stop_if_empty(formats)

st.sidebar.header("Filtres")
models = model_filter(formats)
formats = with_labels(formats[formats["model_key"].isin(models)])
stop_if_empty(formats)

# Intervalle de confiance et hasard lus dans le classement (mêmes exécutions modèle × prompt).
leaderboard = load_leaderboard()[["model_key", "prompt_version", "accuracy_ci_low", "accuracy_ci_high", "random_baseline"]]
formats = formats.merge(leaderboard, on=["model_key", "prompt_version"], how="left")

order = model_order(formats)
present_styles = ordered(formats["label_style"], FORMAT_ORDER)
format_sort = [format_label(s) for s in present_styles]
format_scale = alt.Scale(domain=format_sort, range=[FORMAT_COLORS.get(s, "#999999") for s in present_styles])

# --- Synthèse ----------------------------------------------------------------
by_format = formats.groupby("format_label")["accuracy"].mean().sort_values(ascending=False)
deltas = formats[formats["label_style"] != "letters"].assign(abs_delta=lambda d: d["accuracy_delta_vs_letters"].abs())
summary = f"En moyenne sur les modèles affichés, le format le plus favorable est **{by_format.index[0]}** ({fmt_pct(by_format.iloc[0])})."
if not deltas.empty:
    sensitive = deltas.sort_values("abs_delta", ascending=False).iloc[0]
    summary += (
        f" Le modèle le plus sensible au format est **{sensitive['model_name']}** : "
        f"{fmt_pts(sensitive['accuracy_delta_vs_letters'])} en format {sensitive['format_label'].lower()} par rapport aux lettres."
    )
st.markdown(summary)

tooltip = [
    alt.Tooltip("model_name:N", title="Modèle"),
    alt.Tooltip("format_label:N", title="Format"),
    alt.Tooltip("accuracy:Q", title="Précision", format=".1%"),
    alt.Tooltip("accuracy_ci_low:Q", title="IC 95 % bas", format=".1%"),
    alt.Tooltip("accuracy_ci_high:Q", title="IC 95 % haut", format=".1%"),
    alt.Tooltip("valid_format_rate:Q", title="Format valide", format=".1%"),
    alt.Tooltip("sample_note:N", title="Effectif"),
]

# --- Précision et format valide -----------------------------------------------------
section("Précision et respect du format")
left, right = st.columns(2, gap="large")
with left:
    charts.show(
        charts.grouped_bars(
            formats, x="model_name", y="accuracy", group="format_label", group_scale=format_scale,
            group_sort=format_sort, x_sort=order, title="Précision par format", x_title=None,
            y_title="Précision", y_domain=[0, 1], tooltip=tooltip,
            ci=("accuracy_ci_low", "accuracy_ci_high"), baseline=True,
        )
    )
    st.caption(
        "Pour chaque modèle, une barre par format de réponse. Les traits verticaux sont les intervalles de confiance "
        "à 95 % : deux barres dont les traits se chevauchent ne sont pas significativement différentes."
    )
with right:
    charts.show(
        charts.grouped_bars(
            formats, x="model_name", y="valid_format_rate", group="format_label", group_scale=format_scale,
            group_sort=format_sort, x_sort=order, title="Format valide par format", x_title=None,
            y_title="Part des réponses au bon format", y_domain=[0, 1], tooltip=tooltip,
        )
    )
    st.caption(
        "Part des réponses lisibles selon le format demandé. Une barre basse signifie que le modèle répond "
        "souvent hors format (phrase, explication…), ce qui compte comme une erreur."
    )

# --- Graphique en pente ------------------------------------------------------------
section("Tous les modèles réagissent-ils de la même façon ?")
charts.show(charts.slope_chart(formats, x="format_label", x_sort=format_sort, title="Précision selon le format", x_title="Format de réponse"))
st.caption(
    "Une ligne par modèle. Des lignes parallèles signifient que le format a le même effet sur tous les modèles ; "
    "des lignes qui se croisent, que l'effet dépend du modèle."
)

# --- Tableau des écarts ------------------------------------------------------------
section("Écarts par rapport au format lettres")
table = as_percent(
    formats.sort_values(["model_params_b", "label_style"]),
    ["accuracy", "valid_format_rate", "accuracy_when_valid", "accuracy_delta_vs_letters", "valid_format_delta_vs_letters", "truncated_rate"],
)


def _sign_color(value: float) -> str:
    """Rouge si l'écart est négatif, vert s'il est positif."""
    if value > 0:
        return f"color: {GAIN_COLOR}; font-weight: 700"
    if value < 0:
        return f"color: {LOSS_COLOR}; font-weight: 700"
    return ""


styled = table[
    ["model_name", "format_label", "accuracy", "accuracy_delta_vs_letters", "valid_format_rate",
     "valid_format_delta_vs_letters", "accuracy_when_valid", "truncated_rate", "avg_completion_tokens", "rank_within_model"]
].style.map(_sign_color, subset=["accuracy_delta_vs_letters", "valid_format_delta_vs_letters"])
st.dataframe(
    styled,
    hide_index=True,
    column_config={
        "model_name": "Modèle",
        "format_label": "Format",
        "accuracy": pct_progress("Précision", HELP["accuracy"]),
        "accuracy_delta_vs_letters": st.column_config.NumberColumn("Écart précision vs lettres", format="%+.1f pts"),
        "valid_format_rate": pct_progress("Format valide", HELP["valid_format_rate"]),
        "valid_format_delta_vs_letters": st.column_config.NumberColumn("Écart format vs lettres", format="%+.1f pts"),
        "accuracy_when_valid": pct_number("Précision si format valide", HELP["accuracy_when_valid"]),
        "truncated_rate": pct_number("Réponses tronquées"),
        "avg_completion_tokens": st.column_config.NumberColumn("Tokens moyens", format="%.1f"),
        "rank_within_model": st.column_config.NumberColumn("Rang du format pour ce modèle"),
    },
)
st.caption("Écarts en points de pourcentage : en vert le format fait mieux que les lettres, en rouge moins bien.")
