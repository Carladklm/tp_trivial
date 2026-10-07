"""Charte graphique, libellés, formats et éléments d'interface communs à toutes les pages.

La charte reprend l'univers Trivial Pursuit : fond bleu nuit, et les six couleurs
des camemberts (bleu, rose, jaune, orange, violet, vert) pour les accents.
"""

from __future__ import annotations

import altair as alt
import pandas as pd
import streamlit as st

from lib.data import ensure_db, reload_button

# ---------------------------------------------------------------------------
# Couleurs
# ---------------------------------------------------------------------------

BG = "#0B1026"
SURFACE = "#151D3F"
SURFACE_2 = "#1C2650"
BORDER = "#2A3566"
GRID = "#232D5A"
TEXT = "#EEF1FB"
MUTED = "#9AA6CF"
ACCENT = "#7DD3FC"

# Les six couleurs des camemberts Trivial Pursuit.
TRIVIAL = {
    "blue": "#1EA0E6",
    "pink": "#E6198A",
    "yellow": "#FFD21F",
    "orange": "#F7941D",
    "purple": "#A44CC9",
    "green": "#4CBB47",
}

# Une couleur fixe par modèle. Les teintes suivent l'ordre d'Okabe-Ito
# (bleu, orange, vert, violet rosé) pour rester lisibles par les daltoniens.
MODEL_COLORS = {
    "gemma3_1b": TRIVIAL["blue"],
    "lfm2_1_2b": TRIVIAL["orange"],
    "qwen2_5_3b": TRIVIAL["green"],
    "ministral3_8b": TRIVIAL["pink"],
}
FALLBACK_COLOR = "#999999"

# Ordre de repli (taille croissante) pour les tables sans `model_params_b`.
MODEL_ORDER = ["gemma3_1b", "lfm2_1_2b", "qwen2_5_3b", "ministral3_8b"]

STATUS_COLORS = {
    "Juste": TRIVIAL["green"],
    "Faux": TRIVIAL["pink"],
    "Format invalide": "#8A93B5",
}

# Palette des formats de prompt, distincte de celle des modèles.
PROMPT_COLORS = {
    "v1_letters": TRIVIAL["yellow"],
    "v2_numbers": TRIVIAL["purple"],
    "v3_text": ACCENT,
    "v4_letters_hot": "#FF6B6B",
}

SEQUENTIAL_SCHEME = "blues"
DIVERGING_SCHEME = "redblue"

# ---------------------------------------------------------------------------
# Libellés
# ---------------------------------------------------------------------------

PROMPT_LABELS = {
    "v1_letters": "Lettres (A–D)",
    "v2_numbers": "Chiffres (1–4)",
    "v3_text": "Texte de la réponse",
    "v4_letters_hot": "Lettres, température 1",
}
PROMPT_ORDER = list(PROMPT_LABELS)
DEFAULT_PROMPT = "v1_letters"
ALL_PROMPTS = "all"

DIFFICULTY_LABELS = {"easy": "Facile", "medium": "Moyen", "hard": "Difficile", "all": "Toutes"}
DIFFICULTY_ORDER = ["easy", "medium", "hard"]
QUESTION_TYPE_LABELS = {"multiple": "QCM", "boolean": "Vrai/Faux"}
QUESTION_TYPE_ORDER = ["multiple", "boolean"]

# Formats de réponse (label_style), dans l'ordre de lecture Lettres → Chiffres → Texte.
FORMAT_LABELS = {"letters": "Lettres", "numbers": "Chiffres", "text": "Texte"}
FORMAT_ORDER = list(FORMAT_LABELS)
FORMAT_COLORS = {"letters": TRIVIAL["yellow"], "numbers": TRIVIAL["purple"], "text": ACCENT}

DIFFICULTY_COLORS = {"easy": TRIVIAL["green"], "medium": TRIVIAL["yellow"], "hard": TRIVIAL["pink"]}

GAIN_COLOR = TRIVIAL["green"]
LOSS_COLOR = "#D55E00"

SMALL_SAMPLE = 30

CONFOUNDING_NOTE = (
    "Avec 4 modèles, on **observe** sans pouvoir **généraliser** : chaque pays n'a qu'un modèle "
    "(sauf les États-Unis, qui en ont deux), et le pays, l'éditeur et la taille ne peuvent pas "
    "être séparés du modèle lui-même."
)

# Infobulles reprises des définitions de la page Méthodologie.
HELP = {
    "accuracy": "Part des questions répondues correctement. Une réponse au format invalide compte comme fausse.",
    "ci": "Intervalle de confiance à 95 % de la précision (méthode de Wilson).",
    "valid_format_rate": "Part des réponses qui respectent le format demandé (« C » et non « The answer is C »).",
    "accuracy_when_valid": "Précision parmi les seules réponses bien formatées : mesure la connaissance, sans la discipline de format.",
    "random_baseline": "Score d'un modèle qui répondrait au hasard : 0,25 pour un QCM, 0,5 pour un vrai/faux.",
    "chance_corrected_score": "(précision − hasard) / (1 − hasard). 0 = hasard, 1 = parfait, négatif = pire que le hasard.",
    "correct_per_minute": "Bonnes réponses produites par minute de calcul : efficacité.",
    "prompt_spread": "Écart de précision entre le meilleur et le pire prompt d'un modèle : plus il est faible, plus le modèle est robuste au format.",
    "answer_stability": "Part des questions où le modèle donne la même réponse à T=0 et à T=1.",
    "position_bias": "Part des réponses données sur une position, moins la part des bonnes réponses réellement sur cette position. > 0 : le modèle sur-choisit cette option.",
    "ai_difficulty": "Difficulté « vécue » par les modèles : facile si au moins 2/3 des 12 réponses sont justes, difficile si moins d'1/3, sinon moyenne.",
    "is_common_trap": "Aucun modèle n'a juste et au moins la moitié des réponses désignent la même mauvaise option (idée reçue, ou possible erreur du dataset).",
    "is_majority_correct": "La réponse la plus donnée par l'ensemble des modèles est la bonne (vote à la majorité).",
}

# Tableau des définitions (page Méthodologie) : (indicateur, colonne, clé de HELP).
DEFINITIONS = [
    ("Précision", "accuracy", "accuracy"),
    ("Intervalle de confiance", "accuracy_ci_low / accuracy_ci_high", "ci"),
    ("Format valide", "valid_format_rate", "valid_format_rate"),
    ("Précision si format valide", "accuracy_when_valid", "accuracy_when_valid"),
    ("Hasard", "random_baseline", "random_baseline"),
    ("Score corrigé du hasard", "chance_corrected_score", "chance_corrected_score"),
    ("Bonnes réponses par minute", "correct_per_minute", "correct_per_minute"),
    ("Robustesse au prompt", "prompt_spread", "prompt_spread"),
    ("Stabilité des réponses", "answer_stability", "answer_stability"),
    ("Biais de position", "position_bias", "position_bias"),
    ("Difficulté vécue", "ai_difficulty", "ai_difficulty"),
    ("Piège commun", "is_common_trap", "is_common_trap"),
    ("Vote à la majorité", "is_majority_correct", "is_majority_correct"),
]

# ---------------------------------------------------------------------------
# Formats
# ---------------------------------------------------------------------------


def fmt_pct(x: float | None) -> str:
    """Fraction → « 71.1 % »."""
    return "—" if pd.isna(x) else f"{x * 100:.1f} %"


def fmt_pts(x: float | None) -> str:
    """Écart de fractions → « +3.2 pts »."""
    return "—" if pd.isna(x) else f"{x * 100:+.1f} pts"


def fmt_seconds(x: float | None) -> str:
    """Durée → « 0.421 s »."""
    return "—" if pd.isna(x) else f"{x:.3f} s"


def fmt_score(x: float | None) -> str:
    """Score corrigé du hasard → « 0.562 »."""
    return "—" if pd.isna(x) else f"{x:.3f}"


def prompt_label(prompt_version: str) -> str:
    """Libellé français d'un prompt, ou sa clé brute s'il est inconnu."""
    if prompt_version == ALL_PROMPTS:
        return "Tous les prompts"
    return PROMPT_LABELS.get(prompt_version, prompt_version)


def difficulty_label(difficulty: str) -> str:
    """Libellé français d'une difficulté (Facile, Moyen, Difficile)."""
    return DIFFICULTY_LABELS.get(difficulty, difficulty)


def type_label(question_type: str) -> str:
    """Libellé français d'un type de question (QCM, Vrai/Faux)."""
    return QUESTION_TYPE_LABELS.get(question_type, question_type)


def format_label(label_style: str) -> str:
    """Libellé français d'un format de réponse (Lettres, Chiffres, Texte)."""
    return FORMAT_LABELS.get(label_style, label_style)


def ordered(values, order: list[str]) -> list[str]:
    """Valeurs présentes, dans l'ordre de référence `order`, les inconnues en dernier."""
    present = list(dict.fromkeys(values))
    return [v for v in order if v in present] + sorted(v for v in present if v not in order)


# ---------------------------------------------------------------------------
# Modèles : ordre et couleurs
# ---------------------------------------------------------------------------


def model_order(df: pd.DataFrame) -> list[str]:
    """Noms des modèles par taille croissante (repli sur MODEL_ORDER, inconnus en dernier)."""
    models = df[["model_key", "model_name"]].drop_duplicates("model_key")
    if "model_params_b" in df.columns:
        sizes = df.groupby("model_key")["model_params_b"].first()
        models = models.assign(_rank=models["model_key"].map(sizes))
    else:
        rank = {key: i for i, key in enumerate(MODEL_ORDER)}
        models = models.assign(_rank=models["model_key"].map(rank).fillna(len(rank)))
    return models.sort_values(["_rank", "model_name"])["model_name"].tolist()


def model_color(model_key: str) -> str:
    """Couleur fixe d'un modèle, grise s'il est inconnu."""
    return MODEL_COLORS.get(model_key, FALLBACK_COLOR)


def model_scale(df: pd.DataFrame) -> alt.Scale:
    """Échelle Altair qui associe chaque nom de modèle à sa couleur fixe."""
    names = model_order(df)
    key_by_name = df.drop_duplicates("model_name").set_index("model_name")["model_key"]
    return alt.Scale(domain=names, range=[model_color(key_by_name[n]) for n in names])


# ---------------------------------------------------------------------------
# Mise en page
# ---------------------------------------------------------------------------

_CSS = f"""
<style>
.stApp {{
  background:
    radial-gradient(1200px 600px at 100% -10%, rgba(164,76,201,.28), transparent 60%),
    radial-gradient(900px 500px at -10% 110%, rgba(30,160,230,.18), transparent 60%),
    {BG};
}}
[data-testid="stSidebar"] {{ background: #0E1533; border-right: 1px solid {BORDER}; }}
[data-testid="stHeader"] {{ background: transparent; }}
.block-container {{ padding-top: 2.2rem; }}

.tp-header {{ display: flex; align-items: center; gap: 1.1rem; margin-bottom: .4rem; }}
.tp-wheel {{
  width: 58px; height: 58px; border-radius: 50%; flex: none;
  background: conic-gradient({TRIVIAL['blue']} 0 60deg, {TRIVIAL['purple']} 60deg 120deg,
    {TRIVIAL['green']} 120deg 180deg, {TRIVIAL['yellow']} 180deg 240deg,
    {TRIVIAL['orange']} 240deg 300deg, {TRIVIAL['pink']} 300deg 360deg);
  border: 3px solid #F4F6FF; box-shadow: 0 0 0 3px {BORDER}, 0 6px 20px rgba(0,0,0,.35);
  position: relative;
}}
.tp-wheel::after {{
  content: ""; position: absolute; inset: 40%; border-radius: 50%; background: #F4F6FF;
}}
.tp-eyebrow {{
  display: inline-block; font-size: .72rem; font-weight: 700; letter-spacing: .12em;
  text-transform: uppercase; color: {ACCENT}; background: rgba(125,211,252,.12);
  border: 1px solid rgba(125,211,252,.35); border-radius: 999px; padding: .1rem .6rem;
}}
.tp-title {{ font-size: 2.1rem; font-weight: 800; line-height: 1.15; margin: .25rem 0 0; color: {TEXT}; }}
.tp-question {{ color: {MUTED}; font-size: 1.05rem; margin: .2rem 0 1.2rem; }}
.tp-question b {{ color: {TEXT}; }}

.tp-section {{
  font-size: .78rem; font-weight: 700; letter-spacing: .12em; text-transform: uppercase;
  color: {MUTED}; border-bottom: 1px solid {BORDER}; padding-bottom: .35rem; margin: 1.4rem 0 .6rem;
}}

/* Tuiles KPI façon écran de profil Trivial Pursuit */
div[class*="st-key-kpi_"] {{
  border-radius: 14px; padding: .9rem 1.1rem; min-height: 118px;
  box-shadow: inset 0 -4px 0 rgba(0,0,0,.18), 0 8px 22px rgba(0,0,0,.28);
}}
div[class*="st-key-kpi_"] [data-testid="stMetricLabel"] p {{
  font-size: .74rem; font-weight: 700; letter-spacing: .1em; text-transform: uppercase; opacity: .92;
}}
div[class*="st-key-kpi_"] [data-testid="stMetricValue"] {{ font-weight: 800; font-size: 2rem; }}
div[class*="st-key-kpi_"] * {{ color: #FFFFFF !important; }}
div[class*="st-key-kpi_"] [data-testid="stMetricDelta"] svg {{ display: none; }}
div[class*="st-key-kpi_yellow"] * {{ color: #2A2100 !important; }}
div[class*="st-key-kpi_"][class*="-long"] [data-testid="stMetricValue"] {{ font-size: 1.35rem; line-height: 1.25; }}
div[class*="st-key-kpi_"][class*="-long"] [data-testid="stMetricValue"] div {{ white-space: normal; }}
""" + "".join(
    f'div[class*="st-key-kpi_{name}"] {{ background: linear-gradient(160deg, {color}, {color}D0); }}\n'
    for name, color in TRIVIAL.items()
) + "</style>"


def page_setup(title: str, question: str, eyebrow: str = "Benchmark Trivial Pursuit · LLM locaux") -> None:
    """Configure la page, applique la charte, affiche l'en-tête et le bouton de rechargement."""
    st.set_page_config(page_title=title, layout="wide")
    st.html(_CSS)
    st.html(
        f"""<div class="tp-header"><div class="tp-wheel"></div><div>
        <span class="tp-eyebrow">{eyebrow}</span>
        <h1 class="tp-title">{title}</h1></div></div>
        <p class="tp-question"><b>Question :</b> {question}</p>"""
    )
    reload_button()
    ensure_db()


def section(title: str) -> None:
    """Petit intertitre en capitales, comme les rubriques de l'écran de profil."""
    st.html(f'<div class="tp-section">{title}</div>')


def kpi(label: str, value: str, color: str, delta: str | None = None, help: str | None = None) -> None:
    """Indicateur `st.metric` sur une tuile colorée (color = clé de TRIVIAL)."""
    slug = "".join(c for c in label.lower() if c.isalnum())
    size = "-long" if len(value) > 12 else ""
    with st.container(key=f"kpi_{color}_{slug}{size}"):
        st.metric(label, value, delta=delta, delta_color="off", help=help)


def stop_if_empty(df: pd.DataFrame) -> None:
    """Message neutre et arrêt de la page si la sélection ne renvoie rien."""
    if df.empty:
        st.info("Aucune donnée pour cette sélection.")
        st.stop()


# ---------------------------------------------------------------------------
# Filtres de barre latérale
# ---------------------------------------------------------------------------


def prompt_filter(
    df: pd.DataFrame, key: str = "prompt", include_hot: bool = True, allow_all: bool = False
) -> str | None:
    """Sélecteur de prompt (défaut : lettres à T=0), limité aux prompts présents dans `df`.

    Avec `allow_all`, ajoute l'option ALL_PROMPTS (« Tous les prompts »).
    """
    present = set(df["prompt_version"])
    options = [p for p in PROMPT_ORDER if p in present] + sorted(present - set(PROMPT_ORDER))
    if not include_hot:
        options = [p for p in options if p != "v4_letters_hot"]
    if not options:
        return None
    if allow_all:
        options.append(ALL_PROMPTS)
    index = options.index(DEFAULT_PROMPT) if DEFAULT_PROMPT in options else 0
    return st.sidebar.selectbox("Prompt", options, index=index, format_func=prompt_label, key=key)


def model_filter(df: pd.DataFrame, key: str = "models") -> list[str]:
    """Sélection multiple de modèles (tous par défaut), renvoie des `model_key`."""
    names = model_order(df)
    key_by_name = df.drop_duplicates("model_name").set_index("model_name")["model_key"]
    chosen = st.sidebar.multiselect("Modèles", names, default=names, key=key)
    return [key_by_name[n] for n in chosen]


def multi_filter(label: str, values, order: list[str] | None = None, format_func=str, key: str | None = None) -> list:
    """Sélection multiple de barre latérale (tout coché par défaut) sur les valeurs présentes."""
    options = ordered(values, order or [])
    return st.sidebar.multiselect(label, options, default=options, format_func=format_func, key=key or label)


def with_labels(df: pd.DataFrame) -> pd.DataFrame:
    """Ajoute les colonnes de libellés français pour les dimensions présentes dans `df`."""
    out = df.copy()
    if "prompt_version" in out.columns:
        out["prompt_label"] = out["prompt_version"].map(prompt_label)
    if "difficulty" in out.columns:
        out["difficulty_label"] = out["difficulty"].map(difficulty_label)
    if "question_type" in out.columns:
        out["type_label"] = out["question_type"].map(type_label)
    if "label_style" in out.columns:
        out["format_label"] = out["label_style"].map(format_label)
    return out


# ---------------------------------------------------------------------------
# Tableaux
# ---------------------------------------------------------------------------


def as_percent(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    """Copie de `df` où les fractions de `columns` sont exprimées en pourcentage (0–100)."""
    out = df.copy()
    for col in columns:
        if col in out.columns:
            out[col] = out[col] * 100
    return out


def pct_progress(label: str, help: str | None = None) -> st.column_config.ProgressColumn:
    """Colonne barre de progression pour une valeur déjà convertie en pourcentage."""
    return st.column_config.ProgressColumn(label, help=help, min_value=0, max_value=100, format="%.1f %%")


def pct_number(label: str, help: str | None = None) -> st.column_config.NumberColumn:
    """Colonne numérique en pourcentage (valeur déjà multipliée par 100)."""
    return st.column_config.NumberColumn(label, help=help, format="%.1f %%")
