import hashlib
import html
import json
from pathlib import Path
import pandas as pd


ROOT = Path(__file__).resolve().parents[1] 
BRONZE_FILE = ROOT / "bronze" / "questions_raw.csv"
SILVER_DIR = ROOT / "silver"
OUTPUT_FILE = SILVER_DIR / "questions_clean.parquet"
EXPECTED_COLUMNS = ["type", "difficulty", "category", "question", "correct_answer", "incorrect_answers"]
DIFFICULTY_LEVEL = {"easy": 1, "medium": 2, "hard": 3}
HTML_ENTITY = r"&[a-zA-Z#0-9]+;"


# 1. Fonctions utilitaires ---------------------------------------------------------------------------------------

# Permet de vérifier indiviuellement chaque contrôle et avoir le résultat
def verifier(controles: dict, etape: str) -> None:
    print(f"\n--- Contrôles : {etape}")
    for nom, ok in controles.items():
        print(("OK  " if ok else "KO  ") + nom)
    echecs = [nom for nom, ok in controles.items() if not ok]
    if echecs:
        raise ValueError(f"{len(echecs)} contrôle(s) en échec ({etape}) : {echecs}")

# Permet de nettoyer le texte des questions HTML > clean
def clean_text(value: str) -> str:
    value = html.unescape(value)
    value = value.replace("­", "")   
    value = value.replace(" ", " ")   
    return " ".join(value.split())         

# Permet de créer un id pour chaque question, se base sur question + bonne réponse
def make_id(question: str, correct_answer: str) -> str:
    key = f"{question.lower()}||{correct_answer.lower()}"
    return hashlib.md5(key.encode("utf-8")).hexdigest()[:12]


# --- 1. Chargement --------------------------------------------------------------------------------
raw = pd.read_csv(BRONZE_FILE, dtype=str, keep_default_na=False)
print(f"Bronze chargé : {len(raw)} lignes, {raw.shape[1]} colonnes")


# --- 2. Contrat Bronze ----------------------------------------------------------------------------

incorrect_lists = raw["incorrect_answers"].apply(json.loads)
is_multiple = raw["type"] == "multiple"
is_boolean = raw["type"] == "boolean"

verifier({
    "Colonnes attendues": list(raw.columns) == EXPECTED_COLUMNS,
    "Aucune valeur vide": (raw != "").all().all(),
    "type dans {multiple, boolean}": raw["type"].isin(["multiple", "boolean"]).all(),
    "difficulty dans {easy, medium, hard}": raw["difficulty"].isin(DIFFICULTY_LEVEL).all(),
    "incorrect_answers est une liste JSON": incorrect_lists.apply(lambda x: isinstance(x, list)).all(),
    "QCM : 3 mauvaises réponses": (incorrect_lists[is_multiple].str.len() == 3).all(),
    "Vrai/Faux : 1 mauvaise réponse": (incorrect_lists[is_boolean].str.len() == 1).all(),
    "Vrai/Faux : réponse True ou False": raw.loc[is_boolean, "correct_answer"].isin(["True", "False"]).all(),
}, "contrat Bronze")


# --- 3. Nettoyage des textes ----------------------------------------------------------------------

df = raw.copy()
for col in ["category", "question", "correct_answer"]:
    df[col] = df[col].apply(clean_text)
df["incorrect_answers"] = incorrect_lists.apply(lambda answers: [clean_text(a) for a in answers])


# --- 4. Normalisation et enrichissement -----------------------------------------------------------

# "Entertainment: Film" -> groupe "Entertainment", nom "Film" ; "History" -> "History" / "History"
df["category_group"] = df["category"].str.split(":").str[0].str.strip()
df["category_group"] = df["category_group"].replace({"Science & Nature": "Science"})
df["category_name"] = df["category"].str.split(":").str[-1].str.strip()
df["category_name"] = df["category_name"].replace({"Science & Nature": "Nature"})

df["difficulty_level"] = df["difficulty"].map(DIFFICULTY_LEVEL)
df["nb_options"] = df["incorrect_answers"].str.len() + 1


# --- 5. Identifiant stable et doublons ------------------------------------------------------------

df["question_id"] = [make_id(q, a) for q, a in zip(df["question"], df["correct_answer"])]

doublons = df[df["question_id"].duplicated(keep=False)].sort_values("question_id")
print(f"\nDoublons détectés ({doublons['question_id'].nunique()} questions) :")
print(doublons[["question_id", "category", "question", "correct_answer"]].to_string(index=False))

avant = len(df)
df = df.drop_duplicates(subset="question_id", keep="first").reset_index(drop=True)
print(f"\nDoublons supprimés : {avant - len(df)}  ->  {len(df)} questions")

df = df[["question_id", "type", "difficulty", "difficulty_level", "category", "category_group",
         "category_name", "question", "correct_answer", "incorrect_answers", "nb_options"]]


# --- 6. Contrôles après nettoyage -----------------------------------------------------------------

all_incorrect = df["incorrect_answers"].explode()
text_cols = ["category", "question", "correct_answer"]

verifier({
    "question_id unique": df["question_id"].is_unique,
    "Plus aucune entité HTML": not any(df[c].str.contains(HTML_ENTITY).any() for c in text_cols)
                               and not all_incorrect.str.contains(HTML_ENTITY).any(),
    "Plus d'espaces en trop": all((df[c] == df[c].str.strip()).all() for c in text_cols)
                              and (all_incorrect == all_incorrect.str.strip()).all(),
    "Aucun texte vide": all((df[c] != "").all() for c in text_cols) and (all_incorrect != "").all(),
    "Bonne réponse absente des mauvaises réponses":
        not any(a in inc for a, inc in zip(df["correct_answer"], df["incorrect_answers"])),
    "Aucune option en double dans une question":
        all(len({x.lower() for x in inc + [a]}) == len(inc) + 1
            for a, inc in zip(df["correct_answer"], df["incorrect_answers"])),
    "nb_options = 4 (QCM) ou 2 (Vrai/Faux)":
        (df["nb_options"] == df["type"].map({"multiple": 4, "boolean": 2})).all(),
}, "après nettoyage")


# --- 7. Écriture en Silver : un seul fichier ------------------------------------------------------

SILVER_DIR.mkdir(parents=True, exist_ok=True)
df.to_parquet(OUTPUT_FILE, index=False)

# Relecture : on vérifie ce qui est réellement sur le disque
check = pd.read_parquet(OUTPUT_FILE)
verifier({
    f"Fichier relu : {len(check)} lignes": len(check) == len(df),
    "Colonnes conservées": list(check.columns) == list(df.columns),
    "incorrect_answers relu comme une liste": all(len(x) == n - 1 for x, n in
                                                 zip(check["incorrect_answers"], check["nb_options"])),
}, "écriture Silver")

print(f"\nSilver écrit : {OUTPUT_FILE.relative_to(ROOT)} ({len(df)} questions, {df.shape[1]} colonnes)")