"""Graphiques Altair réutilisables, au thème sombre de la charte.

Règles communes : intervalle de confiance en trait d'erreur quand il existe,
niveau du hasard en pointillé, éléments à petit effectif (n < 30) estompés.
"""

from __future__ import annotations

import altair as alt
import pandas as pd
import streamlit as st

from lib.style import (
    ACCENT,
    BG,
    BORDER,
    DIVERGING_SCHEME,
    GAIN_COLOR,
    GRID,
    LOSS_COLOR,
    MUTED,
    SEQUENTIAL_SCHEME,
    SMALL_SAMPLE,
    STATUS_COLORS,
    TEXT,
    fmt_pct,
    model_order,
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
    text: str | None = None,
    row_step: int = 56,
) -> alt.LayerChart:
    """Carte de chaleur avec la valeur écrite dans chaque cellule.

    Palette séquentielle (bleus) pour une précision, divergente centrée sur 0 pour un écart.
    Les cellules avec `n_questions < 30` sont estompées si la colonne existe.
    `text` : colonne texte à écrire dans les cellules à la place de la valeur formatée.
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
    labels = base.mark_text(fontSize=14 if row_step >= 40 else 12, fontWeight=700).encode(
        text=alt.Text(f"{text}:N") if text else alt.Text(f"{value}:Q", format=value_format),
        color=alt.condition(dark_cell, alt.value("#FFFFFF"), alt.value("#0B1026")),
    )
    return (rects + labels).properties(title=title, height=alt.Step(row_step))


# ---------------------------------------------------------------------------
# Graphiques des pages d'analyse
# ---------------------------------------------------------------------------


def _model_color(df: pd.DataFrame, legend: bool = False) -> alt.Color:
    """Encodage couleur des modèles (couleur fixe par modèle)."""
    return alt.Color(
        "model_name:N",
        scale=model_scale(df),
        title="Modèle",
        legend=alt.Legend(title=None) if legend else None,
    )


def model_scatter(
    df: pd.DataFrame,
    x: str,
    x_title: str,
    title: str,
    x_log: bool = False,
    x_format: str | None = None,
    size: str | None = None,
    size_title: str | None = None,
    extra_tooltip: list[alt.Tooltip] | None = None,
) -> alt.LayerChart:
    """Nuage de points modèle par modèle : y = précision avec IC 95 %, étiquette du nom, ligne du hasard."""
    scale = alt.Scale(type="log", nice=False, padding=30) if x_log else alt.Scale(zero=False, padding=30)
    axis = alt.Axis(format=x_format) if x_format else alt.Axis()
    tooltip = [
        alt.Tooltip("model_name:N", title="Modèle"),
        alt.Tooltip("accuracy:Q", title="Précision", format=".1%"),
        alt.Tooltip("accuracy_ci_low:Q", title="IC 95 % bas", format=".1%"),
        alt.Tooltip("accuracy_ci_high:Q", title="IC 95 % haut", format=".1%"),
        *(extra_tooltip or []),
    ]
    base = alt.Chart(df).encode(
        x=alt.X(f"{x}:Q", title=x_title, scale=scale, axis=axis),
        y=alt.Y("accuracy:Q", title="Précision", scale=alt.Scale(domain=[0, 1]), axis=alt.Axis(format="%")),
        tooltip=tooltip,
    )
    errors = base.mark_rule(strokeWidth=2).encode(y="accuracy_ci_low:Q", y2="accuracy_ci_high:Q", color=_model_color(df))
    size_enc = (
        alt.Size(f"{size}:Q", title=size_title, scale=alt.Scale(range=[150, 900]), legend=None)
        if size
        else alt.value(260)
    )
    points = base.mark_circle(opacity=1, stroke=BG, strokeWidth=1.5).encode(color=_model_color(df), size=size_enc)
    labels = base.mark_text(align="left", dx=14, dy=-10, fontSize=13, fontWeight=700, color=TEXT).encode(
        text="model_name:N"
    )
    chart = errors + points + labels
    if "random_baseline" in df.columns:
        chart = chart + baseline_rule(df, axis="y")
    return chart.properties(title=title, height=380)


def grouped_bars(
    df: pd.DataFrame,
    x: str,
    y: str,
    group: str,
    group_scale: alt.Scale,
    title: str,
    x_title: str | None,
    y_title: str,
    x_sort: list[str] | None = None,
    group_sort: list[str] | None = None,
    group_title: str | None = None,
    y_format: str = "%",
    y_domain: list[float] | None = None,
    tooltip: list[alt.Tooltip] | None = None,
    ci: tuple[str, str] | None = None,
    baseline: bool = False,
) -> alt.LayerChart:
    """Barres verticales groupées (une barre par valeur de `group` dans chaque `x`).

    `ci` = (colonne basse, colonne haute) ajoute des traits d'intervalle de confiance,
    `baseline` ajoute la ligne pointillée du hasard (colonne `random_baseline`).
    """
    data = add_sample_note(df) if "n_questions" in df.columns else df.assign(low_n=False)
    scale = alt.Scale(domain=y_domain) if y_domain else alt.Scale()
    base = alt.Chart(data).encode(
        x=alt.X(f"{x}:N", sort=x_sort, title=x_title, axis=alt.Axis(labelAngle=0, labelColor=TEXT, labelLimit=180)),
        xOffset=alt.XOffset(f"{group}:N", sort=group_sort),
        tooltip=tooltip,
    )
    bars = base.mark_bar(cornerRadiusEnd=4).encode(
        y=alt.Y(f"{y}:Q", title=y_title, scale=scale, axis=alt.Axis(format=y_format)),
        color=alt.Color(f"{group}:N", scale=group_scale, sort=group_sort, title=group_title, legend=alt.Legend(title=None)),
        opacity=_low_n_opacity(),
    )
    chart = bars
    if ci:
        chart = chart + base.mark_rule(color=TEXT, strokeWidth=1.5).encode(y=f"{ci[0]}:Q", y2=f"{ci[1]}:Q")
    if baseline and "random_baseline" in df.columns:
        chart = chart + baseline_rule(df, axis="y")
    return chart.properties(title=title, height=360)


def slope_chart(df: pd.DataFrame, x: str, x_sort: list[str], title: str, x_title: str) -> alt.LayerChart:
    """Graphique en pente : une ligne par modèle à travers les modalités de `x` (précision en y)."""
    last = df[df[x] == next(v for v in reversed(x_sort) if v in set(df[x]))]
    base = alt.Chart(df).encode(
        x=alt.X(f"{x}:N", sort=x_sort, title=x_title, axis=alt.Axis(labelAngle=0, labelColor=TEXT), scale=alt.Scale(padding=0.3)),
        y=alt.Y("accuracy:Q", title="Précision", scale=alt.Scale(zero=False), axis=alt.Axis(format="%")),
        color=_model_color(df),
        tooltip=[
            alt.Tooltip("model_name:N", title="Modèle"),
            alt.Tooltip(f"{x}:N", title=x_title),
            alt.Tooltip("accuracy:Q", title="Précision", format=".1%"),
            alt.Tooltip("valid_format_rate:Q", title="Format valide", format=".1%"),
            alt.Tooltip("n_questions:Q", title="n"),
        ],
    )
    lines = base.mark_line(strokeWidth=3) + base.mark_point(filled=True, size=110, opacity=1)
    labels = (
        alt.Chart(last)
        .mark_text(align="left", dx=10, fontSize=12, fontWeight=700)
        .encode(x=alt.X(f"{x}:N", sort=x_sort), y="accuracy:Q", text="model_name:N", color=_model_color(df))
    )
    return (lines + labels).properties(title=title, height=380)


def dumbbell(df: pd.DataFrame, title: str) -> alt.LayerChart:
    """Haltère : précision à T=0 et à T=1 par modèle, reliées par un segment."""
    order = model_order(df)
    long = df.melt(
        id_vars=["model_name", "n_questions", "accuracy_delta"],
        value_vars=["accuracy_cold", "accuracy_hot"],
        var_name="run",
        value_name="accuracy",
    )
    long["run"] = long["run"].map({"accuracy_cold": "Température 0", "accuracy_hot": "Température 1"})
    run_scale = alt.Scale(domain=["Température 0", "Température 1"], range=[ACCENT, "#FF6B6B"])
    y = alt.Y("model_name:N", sort=order, title=None, axis=alt.Axis(labelColor=TEXT, labelFontSize=13, labelLimit=320))
    segment = (
        alt.Chart(df)
        .mark_rule(color=MUTED, strokeWidth=4, opacity=0.6)
        .encode(y=y, x=alt.X("accuracy_cold:Q"), x2="accuracy_hot:Q")
    )
    points = (
        alt.Chart(long)
        .mark_circle(size=260, opacity=1, stroke=BG, strokeWidth=1.5)
        .encode(
            y=y,
            x=alt.X("accuracy:Q", title="Précision", axis=alt.Axis(format="%"), scale=alt.Scale(zero=False, padding=20)),
            color=alt.Color("run:N", scale=run_scale, title=None, legend=alt.Legend(title=None)),
            tooltip=[
                alt.Tooltip("model_name:N", title="Modèle"),
                alt.Tooltip("run:N", title="Exécution"),
                alt.Tooltip("accuracy:Q", title="Précision", format=".1%"),
                alt.Tooltip("accuracy_delta:Q", title="Écart T=1 − T=0", format="+.1%"),
                alt.Tooltip("n_questions:Q", title="n"),
            ],
        )
    )
    chart = segment + points
    if "random_baseline" in df.columns:
        chart = chart + baseline_rule(df)
    return chart.properties(title=title, height=alt.Step(52))


def diverging_flow(df: pd.DataFrame, title: str) -> alt.LayerChart:
    """Barres divergentes : réponses perdues (juste → faux) à gauche, gagnées (faux → juste) à droite."""
    order = model_order(df)
    long = pd.concat(
        [
            df.assign(direction="Perdues (juste → faux)", share=-df["rate_correct_to_wrong"], rate=df["rate_correct_to_wrong"]),
            df.assign(direction="Gagnées (faux → juste)", share=df["rate_wrong_to_correct"], rate=df["rate_wrong_to_correct"]),
        ]
    )
    scale = alt.Scale(domain=["Perdues (juste → faux)", "Gagnées (faux → juste)"], range=[LOSS_COLOR, GAIN_COLOR])
    bars = (
        alt.Chart(long)
        .mark_bar(height={"band": 0.6}, cornerRadius=3)
        .encode(
            y=alt.Y("model_name:N", sort=order, title=None, axis=alt.Axis(labelColor=TEXT, labelFontSize=13, labelLimit=320)),
            x=alt.X("share:Q", title="Part des questions", axis=alt.Axis(format="%", labelExpr="replace(datum.label, '-', '')")),
            color=alt.Color("direction:N", scale=scale, title=None, legend=alt.Legend(title=None)),
            tooltip=[
                alt.Tooltip("model_name:N", title="Modèle"),
                alt.Tooltip("direction:N", title="Sens"),
                alt.Tooltip("rate:Q", title="Part des questions", format=".1%"),
                alt.Tooltip("n_questions:Q", title="n"),
            ],
        )
    )
    zero = alt.Chart(pd.DataFrame({"x": [0]})).mark_rule(color=TEXT, strokeWidth=1).encode(x="x:Q")
    return (bars + zero).properties(title=title, height=alt.Step(52))


def signed_bars(df: pd.DataFrame, y: str, value: str, title: str, x_title: str, tooltip: list[alt.Tooltip]) -> alt.LayerChart:
    """Barres horizontales d'un écart signé, triées, vertes si positives et rouges si négatives.

    Les lignes où `highlight` est faux (si la colonne existe) sont estompées.
    """
    data = df.assign(sign=lambda d: d[value].map(lambda v: "Au-dessus" if v >= 0 else "En dessous"))
    if "highlight" not in data.columns:
        data["highlight"] = True
    order = data.sort_values(value, ascending=False)[y].tolist()
    scale = alt.Scale(domain=["Au-dessus", "En dessous"], range=[GAIN_COLOR, LOSS_COLOR])
    bars = (
        alt.Chart(data)
        .mark_bar(height={"band": 0.7}, cornerRadius=3)
        .encode(
            y=alt.Y(f"{y}:N", sort=order, title=None, axis=alt.Axis(labelColor=TEXT, labelLimit=240)),
            x=alt.X(f"{value}:Q", title=x_title, axis=alt.Axis(format="+%")),
            color=alt.Color("sign:N", scale=scale, legend=None),
            opacity=alt.condition("datum.highlight", alt.value(1.0), alt.value(0.35)),
            tooltip=tooltip,
        )
    )
    zero = alt.Chart(pd.DataFrame({"x": [0]})).mark_rule(color=TEXT, strokeWidth=1).encode(x="x:Q")
    return (bars + zero).properties(title=title, height=alt.Step(24))


def faceted_lines(
    df: pd.DataFrame,
    x: str,
    x_sort: list[str],
    x_title: str,
    y: str,
    y_title: str,
    facet: str,
    facet_sort: list[str],
    title: str,
    ci: tuple[str, str] | None,
    baseline: str,
    y_domain: list[float] | None = None,
    tooltip: list[alt.Tooltip] | None = None,
) -> alt.FacetChart:
    """Courbes par modèle, une facette par valeur de `facet`, avec bande d'IC et ligne du hasard par facette."""
    data = add_sample_note(df)
    order = model_order(df)
    color = alt.Color("model_name:N", scale=model_scale(df), sort=order, title=None, legend=alt.Legend(title=None))
    x_enc = alt.X(f"{x}:N", sort=x_sort, title=x_title, axis=alt.Axis(labelAngle=0, labelColor=TEXT))
    y_scale = alt.Scale(domain=y_domain) if y_domain else alt.Scale(zero=False)
    layers = []
    if ci:
        layers.append(
            alt.Chart().mark_area(opacity=0.15).encode(x=x_enc, y=alt.Y(f"{ci[0]}:Q", scale=y_scale), y2=f"{ci[1]}:Q", color=color)
        )
    layers.append(
        alt.Chart()
        .mark_line(strokeWidth=3, point=alt.OverlayMarkDef(filled=True, size=90))
        .encode(
            x=x_enc,
            y=alt.Y(f"{y}:Q", title=y_title, scale=y_scale, axis=alt.Axis(format="%" if ci else ".2f")),
            color=color,
            opacity=_low_n_opacity(),
            tooltip=tooltip,
        )
    )
    layers.append(
        alt.Chart().mark_rule(strokeDash=[6, 4], color=MUTED, strokeWidth=1.5).encode(
            y=f"mean({baseline}):Q", tooltip=[alt.Tooltip(f"mean({baseline}):Q", title="Hasard", format=".2f")]
        )
    )
    return (
        alt.layer(*layers, data=data)
        .properties(width=420, height=320)
        .facet(column=alt.Column(f"{facet}:N", sort=facet_sort, title=None, header=alt.Header(labelFontSize=15, labelFontWeight=700)))
        .properties(title=title)
    )


def faceted_position_bars(df: pd.DataFrame, title: str, x_sort: list[str]) -> alt.FacetChart:
    """Par modèle (facettes) : part des réponses données vs part des bonnes réponses, position par position."""
    long = df.melt(
        id_vars=["model_name", "position_label", "position", "n_chosen", "n_correct_here", "position_bias"],
        value_vars=["share_chosen", "share_expected"],
        var_name="measure",
        value_name="share",
    )
    long["measure"] = long["measure"].map(
        {"share_chosen": "Réponses du modèle", "share_expected": "Bonnes réponses réelles"}
    )
    measures = ["Réponses du modèle", "Bonnes réponses réelles"]
    scale = alt.Scale(domain=measures, range=[ACCENT, MUTED])
    bars = (
        alt.Chart()
        .mark_bar(cornerRadiusEnd=3)
        .encode(
            x=alt.X("position_label:N", sort=x_sort, title="Option", axis=alt.Axis(labelAngle=0, labelColor=TEXT)),
            xOffset=alt.XOffset("measure:N", sort=measures),
            y=alt.Y("share:Q", title="Part", axis=alt.Axis(format="%")),
            color=alt.Color("measure:N", scale=scale, sort=measures, title=None, legend=alt.Legend(title=None)),
            tooltip=[
                alt.Tooltip("model_name:N", title="Modèle"),
                alt.Tooltip("position_label:N", title="Option"),
                alt.Tooltip("measure:N", title="Mesure"),
                alt.Tooltip("share:Q", title="Part", format=".1%"),
                alt.Tooltip("position_bias:Q", title="Biais", format="+.1%"),
                alt.Tooltip("n_chosen:Q", title="Fois choisie"),
                alt.Tooltip("n_correct_here:Q", title="Fois bonne réponse"),
            ],
        )
    )
    order = model_order(df)
    return (
        alt.layer(bars, data=long)
        .properties(width=220, height=260)
        .facet(facet=alt.Facet("model_name:N", sort=order, title=None, header=alt.Header(labelFontSize=14, labelFontWeight=700)), columns=4)
        .properties(title=title)
    )


def histogram(
    df: pd.DataFrame, x: str, x_sort: list[str], color: str, color_scale: alt.Scale, color_sort: list[str], title: str, x_title: str
) -> alt.Chart:
    """Histogramme empilé d'une variable discrète (déjà regroupée : colonnes `x`, `color`, `n`, `color_rank`)."""
    return (
        alt.Chart(df)
        .mark_bar(cornerRadiusEnd=0)
        .encode(
            x=alt.X(f"{x}:O", sort=x_sort, title=x_title, axis=alt.Axis(labelAngle=0, labelColor=TEXT)),
            y=alt.Y("n:Q", title="Nombre de questions", stack=True),
            color=alt.Color(f"{color}:N", scale=color_scale, sort=color_sort, title=None, legend=alt.Legend(title=None)),
            order=alt.Order("color_rank:Q"),
            tooltip=[
                alt.Tooltip(f"{x}:O", title=x_title),
                alt.Tooltip(f"{color}:N", title="Difficulté annoncée"),
                alt.Tooltip("n:Q", title="Questions"),
            ],
        )
        .properties(title=title, height=340)
    )
