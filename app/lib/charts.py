"""Graphiques Altair réutilisables, au thème sombre de la charte.

Règles communes : intervalle de confiance en trait d'erreur quand il existe,
niveau du hasard en pointillé, éléments à petit effectif (n < 30) estompés.
"""

from __future__ import annotations

import altair as alt
import pandas as pd
import streamlit as st

from lib.style import (
    BORDER,
    DIVERGING_SCHEME,
    GRID,
    MUTED,
    SEQUENTIAL_SCHEME,
    SMALL_SAMPLE,
    STATUS_COLORS,
    TEXT,
    fmt_pct,
    model_scale,
)

FONT = "\"Source Sans\", sans-serif"
LOW_N_OPACITY = 0.35


@alt.theme.register("trivia_dark", enable=True)
def _trivia_dark() -> alt.theme.ThemeConfig:
    """Thème Altair aligné sur la charte (fond transparent, texte clair)."""
    axis = {
        "labelColor": MUTED,
        "titleColor": TEXT,
        "gridColor": GRID,
        "domainColor": BORDER,
        "tickColor": BORDER,
        "labelFont": FONT,
        "titleFont": FONT,
        "labelFontSize": 12,
        "titleFontSize": 13,
        "titleFontWeight": 600,
    }
    return {
        "config": {
            "background": "transparent",
            "autosize": {"type": "fit", "contains": "padding"},
            "font": FONT,
            "view": {"stroke": None},
            "axis": axis,
            "legend": {
                "labelColor": MUTED,
                "titleColor": TEXT,
                "labelFont": FONT,
                "titleFont": FONT,
                "labelFontSize": 12,
                "orient": "bottom",
            },
            "header": {"labelColor": TEXT, "titleColor": TEXT, "labelFontSize": 13, "labelFont": FONT},
            "title": {"color": TEXT, "font": FONT, "fontSize": 16, "fontWeight": 700, "anchor": "start", "offset": 12},
            "text": {"color": TEXT, "font": FONT},
            "bar": {"cornerRadiusEnd": 4},
        }
    }


def show(chart: alt.TopLevelMixin) -> None:
    """Affiche un graphique sur toute la largeur."""
    st.altair_chart(chart, width="stretch", theme=None)


def _row_step(df: pd.DataFrame, label: str) -> alt.Step:
    """Hauteur de ligne : large pour quelques barres, resserrée quand il y en a beaucoup."""
    return alt.Step(52 if df[label].nunique() <= 6 else 30)


def add_sample_note(df: pd.DataFrame) -> pd.DataFrame:
    """Ajoute `sample_note` (texte d'infobulle) et `low_n` (booléen) selon `n_questions`."""
    out = df.copy()
    out["low_n"] = out["n_questions"] < SMALL_SAMPLE
    out["sample_note"] = out["n_questions"].map(
        lambda n: f"Échantillon faible : n = {n}" if n < SMALL_SAMPLE else f"n = {n}"
    )
    return out


def _low_n_opacity() -> alt.OpacityValue:
    return alt.condition("datum.low_n", alt.value(LOW_N_OPACITY), alt.value(1.0))


def baseline_rule(df: pd.DataFrame, field: str = "random_baseline", axis: str = "x") -> alt.LayerChart:
    """Ligne pointillée du niveau du hasard, une par valeur distincte de `field`.

    `axis="x"` trace une ligne verticale (précision en abscisse), `axis="y"` une horizontale.
    """
    base = alt.Chart(df[[field]].drop_duplicates().assign(label="Hasard"))
    position = {axis: alt.X(f"{field}:Q") if axis == "x" else alt.Y(f"{field}:Q")}
    other = "y" if axis == "x" else "x"
    rule = base.mark_rule(strokeDash=[6, 4], color=MUTED, strokeWidth=1.5).encode(
        **position, tooltip=[alt.Tooltip(f"{field}:Q", title="Hasard", format=".1%")]
    )
    label = base.mark_text(color=MUTED, fontSize=11, align="left", dx=4, dy=-6).encode(
        **position, **{other: alt.value(0)}, text="label:N"
    )
    return rule + label


def accuracy_bars(df: pd.DataFrame, title: str, label: str = "model_name") -> alt.LayerChart:
    """Barres horizontales de précision, triées, avec IC à 95 % et ligne du hasard.

    `label` est la colonne affichée sur l'axe (le modèle, ou « modèle · prompt »).
    La couleur reste toujours celle du modèle.
    """
    data = add_sample_note(df).assign(accuracy_txt=lambda d: d["accuracy"].map(fmt_pct))
    order = data.sort_values("accuracy", ascending=False)[label].tolist()
    y = alt.Y(f"{label}:N", sort=order, title=None, axis=alt.Axis(labelFontSize=13, labelColor=TEXT, labelLimit=320))
    x_scale = alt.Scale(domain=[0, 1])
    tooltip = [
        alt.Tooltip(f"{label}:N", title="Exécution" if label != "model_name" else "Modèle"),
        alt.Tooltip("accuracy:Q", title="Précision", format=".1%"),
        alt.Tooltip("accuracy_ci_low:Q", title="IC 95 % bas", format=".1%"),
        alt.Tooltip("accuracy_ci_high:Q", title="IC 95 % haut", format=".1%"),
        alt.Tooltip("valid_format_rate:Q", title="Format valide", format=".1%"),
        alt.Tooltip("sample_note:N", title="Effectif"),
    ]
    base = alt.Chart(data).encode(y=y, tooltip=tooltip)
    bars = base.mark_bar(height={"band": 0.62}).encode(
        x=alt.X("accuracy:Q", title="Précision (part de bonnes réponses)", scale=x_scale, axis=alt.Axis(format="%")),
        color=alt.Color("model_name:N", scale=model_scale(df), legend=None),
        opacity=_low_n_opacity(),
    )
    errors = base.mark_rule(color=TEXT, strokeWidth=2).encode(x="accuracy_ci_low:Q", x2="accuracy_ci_high:Q")
    caps = base.mark_tick(color=TEXT, thickness=2, size=12).encode(x="accuracy_ci_low:Q") + base.mark_tick(
        color=TEXT, thickness=2, size=12
    ).encode(x="accuracy_ci_high:Q")
    labels = base.mark_text(align="left", dx=8, fontWeight=700, fontSize=13, color=TEXT).encode(
        x="accuracy_ci_high:Q", text="accuracy_txt:N"
    )
    return (bars + errors + caps + labels + baseline_rule(data)).properties(title=title, height=_row_step(data, label))


def status_stack(
    df: pd.DataFrame, title: str, order: list[str] | None = None, label: str = "model_name"
) -> alt.Chart:
    """Barre empilée à 100 % par modèle : juste / faux / format invalide.

    Les trois parts sont dérivées à l'affichage : juste = accuracy,
    faux = valid_format_rate − accuracy, invalide = 1 − valid_format_rate.
    """
    parts = df.assign(
        **{
            "Juste": df["accuracy"],
            "Faux": df["valid_format_rate"] - df["accuracy"],
            "Format invalide": 1 - df["valid_format_rate"],
        }
    )
    long = parts.melt(
        id_vars=[label, "n_questions"],
        value_vars=list(STATUS_COLORS),
        var_name="status",
        value_name="share",
    )
    long["status_rank"] = long["status"].map({s: i for i, s in enumerate(STATUS_COLORS)})
    status_scale = alt.Scale(domain=list(STATUS_COLORS), range=list(STATUS_COLORS.values()))
    return (
        alt.Chart(long)
        .mark_bar(height={"band": 0.62}, cornerRadiusEnd=0)
        .encode(
            y=alt.Y(f"{label}:N", sort=order, title=None, axis=alt.Axis(labelFontSize=13, labelColor=TEXT, labelLimit=320)),
            x=alt.X("share:Q", stack="normalize", title="Part des réponses", axis=alt.Axis(format="%")),
            color=alt.Color("status:N", scale=status_scale, title=None, sort=list(STATUS_COLORS)),
            order=alt.Order("status_rank:Q"),
            tooltip=[
                alt.Tooltip(f"{label}:N", title="Exécution" if label != "model_name" else "Modèle"),
                alt.Tooltip("status:N", title="Statut"),
                alt.Tooltip("share:Q", title="Part", format=".1%"),
                alt.Tooltip("n_questions:Q", title="n"),
            ],
        )
        .properties(title=title, height=_row_step(df, label))
    )


def heatmap(
    df: pd.DataFrame,
    x: str,
    y: str,
    value: str,
    title: str,
    x_title: str,
    y_title: str,
    x_sort: list[str] | None = None,
    y_sort: list[str] | None = None,
    diverging: bool = False,
    tooltip: list[alt.Tooltip] | None = None,
    value_format: str = ".1%",
) -> alt.LayerChart:
    """Carte de chaleur avec la valeur écrite dans chaque cellule.

    Palette séquentielle (bleus) pour une précision, divergente centrée sur 0 pour un écart.
    Les cellules avec `n_questions < 30` sont estompées si la colonne existe.
    """
    data = add_sample_note(df) if "n_questions" in df.columns else df.assign(low_n=False)
    scale = alt.Scale(scheme=DIVERGING_SCHEME, domainMid=0) if diverging else alt.Scale(scheme=SEQUENTIAL_SCHEME)
    tooltip = tooltip or [
        alt.Tooltip(f"{y}:N", title=y_title),
        alt.Tooltip(f"{x}:N", title=x_title),
        alt.Tooltip(f"{value}:Q", format=value_format),
    ]
    base = alt.Chart(data).encode(
        x=alt.X(f"{x}:N", sort=x_sort, title=x_title, axis=alt.Axis(labelAngle=0, orient="top", labelColor=TEXT, labelLimit=180)),
        y=alt.Y(f"{y}:N", sort=y_sort, title=y_title, axis=alt.Axis(labelColor=TEXT, labelLimit=220)),
        tooltip=tooltip,
    )
    rects = base.mark_rect(cornerRadius=6, stroke="#0B1026", strokeWidth=3).encode(
        color=alt.Color(f"{value}:Q", scale=scale, legend=alt.Legend(format=value_format, title=None)),
        opacity=_low_n_opacity(),
    )
    # Texte clair sur les cellules foncées (extrémités de la palette), sombre ailleurs.
    if diverging:
        dark_cell = f"abs(datum.{value}) > {data[value].abs().max() * 0.55}"
    else:
        dark_cell = f"datum.{value} > {(data[value].min() + data[value].max()) / 2}"
    text = base.mark_text(fontSize=14, fontWeight=700).encode(
        text=alt.Text(f"{value}:Q", format=value_format),
        color=alt.condition(dark_cell, alt.value("#FFFFFF"), alt.value("#0B1026")),
    )
    return (rects + text).properties(title=title, height=alt.Step(56))
