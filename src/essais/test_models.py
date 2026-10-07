import random
import re
import sys
import time
from pathlib import Path

import lmstudio as lms
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")

# --- À MODIFIER -----------------------------------------------------------------------------------

N_QUESTIONS = 5               # questions posées à chaque modèle pour le test
PROMPT_VERSION = "v2_numbers" # prompt utilisé pour le test (None = la première ligne de chaque modèle)
N_BENCHMARK = 1000            # questions par exécution dans le vrai benchmark (pour l'estimation de durée)

# --- Chemins et connexion -------------------------------------------------------------------------

ROOT = Path(__file__).resolve().parents[2]
CONFIG_FILE = ROOT / "prompt" / "benchmark_config.csv"
QUESTIONS_FILE = ROOT / "silver" / "questions_clean.parquet"

LMSTUDIO_HOST = "localhost:1234"
lms.configure_default_client(LMSTUDIO_HOST)

LABELS = {"letters": ["A", "B", "C", "D"], "numbers": ["1", "2", "3", "4"]}


# --- Mêmes fonctions que run_benchmark.py ---------------------------------------------------------

def build_choices(question_id, qtype, correct_answer, incorrect_answers):
    if qtype == "boolean":
        return ["True", "False"]
    options = [correct_answer] + list(incorrect_answers)
    random.Random(question_id).shuffle(options)
    return options


def format_options(choices, label_style):
    if label_style == "text":
        return "\n".join(f"- {c}" for c in choices)
    return "\n".join(f"{label}. {c}" for label, c in zip(LABELS[label_style], choices))


def normalize(text):
    text = text.strip().strip("\"'`*").strip().rstrip(".!").strip()
    return " ".join(text.lower().split())


def parse_answer(raw, choices, label_style):
    text = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL)
    text = re.sub(r"^\s*(answer|réponse)\s*[:\-]\s*", "", text.strip(), flags=re.IGNORECASE).strip()
    if not text:
        return None
    if label_style in LABELS:
        allowed = LABELS[label_style][:len(choices)]
        tokens = text.split()
        match = re.fullmatch(r"\(?([A-Da-d1-4])[).:]?", tokens[0])
        if not match or match.group(1).upper() not in allowed:
            return None
        index = allowed.index(match.group(1).upper())
        rest = " ".join(tokens[1:])
        return index if not rest or normalize(rest) == normalize(choices[index]) else None
    normalized = [normalize(c) for c in choices]
    answer = normalize(text.splitlines()[0])
    return normalized.index(answer) if answer in normalized else None


# --- 1. Modèles disponibles dans LM Studio --------------------------------------------------------

config = pd.read_csv(CONFIG_FILE, keep_default_na=False).sort_values("run_order")
runs_per_model = config.groupby("lmstudio_id").size()          # nb d'exécutions prévues par modèle

if PROMPT_VERSION is not None:
    tests = config[config["prompt_version"] == PROMPT_VERSION]
else:
    tests = config.drop_duplicates("lmstudio_id", keep="first")
tests = tests.drop_duplicates("lmstudio_id", keep="first")
if tests.empty:
    raise SystemExit(f"Aucune ligne avec prompt_version = {PROMPT_VERSION} dans le CSV.")

try:
    downloaded = sorted(m.model_key for m in lms.list_downloaded_models("llm"))
except Exception as exc:
    raise SystemExit(f"Impossible de joindre LM Studio ({type(exc).__name__}: {exc}).\n"
                     f"Vérifie que LM Studio est ouvert et que le serveur est démarré ({LMSTUDIO_HOST}).")

print("Modèles téléchargés dans LM Studio :")
for key in downloaded:
    print(f"   - {key}")
print()

questions = pd.read_parquet(QUESTIONS_FILE)
# Mêmes questions que le benchmark : début du tirage avec la graine du CSV
sample = questions.sample(frac=1, random_state=int(tests.iloc[0]["sample_seed"])).head(N_QUESTIONS)


# --- 2. Test de chaque modèle ---------------------------------------------------------------------

bilan = []
for run in tests.itertuples():
    print("=" * 100)
    print(f"{run.model_name}  ({run.lmstudio_id})  —  prompt {run.prompt_version}")

    if run.lmstudio_id not in downloaded:
        proches = [k for k in downloaded if run.lmstudio_id.split("/")[-1].split("-")[0] in k]
        print(f"!! '{run.lmstudio_id}' n'est pas dans les modèles téléchargés."
              + (f" Nom proche trouvé : {proches} -> corrige lmstudio_id dans le CSV." if proches
                 else " Télécharge-le dans LM Studio, ou corrige lmstudio_id dans le CSV."))
        bilan.append({"modèle": run.model_name, "lmstudio_id": run.lmstudio_id, "statut": "non téléchargé"})
        print()
        continue

    try:
        t0 = time.perf_counter()
        model = lms.llm(run.lmstudio_id)
        load_time = time.perf_counter() - t0
        print(f"Chargé en {load_time:.1f} s")
    except Exception as exc:
        print(f"!! Chargement impossible : {type(exc).__name__}: {exc}")
        bilan.append({"modèle": run.model_name, "lmstudio_id": run.lmstudio_id, "statut": "échec du chargement"})
        print()
        continue

    system_prompt = run.system_prompt + (" /no_think" if str(run.disable_thinking).lower() == "true" else "")
    temps, valides, justes, erreurs = [], 0, 0, 0
    for q in sample.itertuples():
        choices = build_choices(q.question_id, q.type, q.correct_answer, q.incorrect_answers)
        chat = lms.Chat(system_prompt) if system_prompt.strip() else lms.Chat()
        chat.add_user_message(run.user_template.format(question=q.question,
                                                       options=format_options(choices, run.label_style)))
        start = time.perf_counter()
        try:
            result = model.respond(chat, config={"temperature": float(run.temperature),
                                                 "maxTokens": int(run.max_tokens)})
        except Exception as exc:
            erreurs += 1
            print(f"   erreur : {type(exc).__name__}: {exc}")
            continue
        temps.append(time.perf_counter() - start)
        raw = result.content or ""
        ai_index = parse_answer(raw, choices, run.label_style)
        correct_index = choices.index(q.correct_answer)
        valides += ai_index is not None
        justes += ai_index == correct_index
        statut = "juste" if ai_index == correct_index else ("faux" if ai_index is not None else "FORMAT INVALIDE")
        print(f"   {temps[-1]:5.2f} s  réponse brute : {raw!r:<30}  -> {statut}")

    try:
        model.unload()                     # libère la mémoire avant le modèle suivant
    except Exception:
        pass

    n = len(temps)
    moyenne = sum(temps) / n if n else None
    duree_benchmark = moyenne * N_BENCHMARK * runs_per_model[run.lmstudio_id] / 60 if n else None
    bilan.append({
        "modèle": run.model_name, "lmstudio_id": run.lmstudio_id,
        "statut": "OK" if n and erreurs == 0 else ("erreurs" if n else "aucune réponse"),
        "chargement (s)": round(load_time, 1),
        "s/question": round(moyenne, 2) if n else None,
        "format valide": f"{valides}/{n}" if n else "-",
        "justes": f"{justes}/{n}" if n else "-",
        f"durée estimée benchmark ({runs_per_model[run.lmstudio_id]} exéc. x {N_BENCHMARK} q.)":
            f"~{duree_benchmark:.0f} min" if n else "-",
    })
    print()


# --- 3. Bilan --------------------------------------------------------------------------------------

print("=" * 100)
print("BILAN DU TEST")
print(pd.DataFrame(bilan).fillna("-").to_string(index=False))
print("\nUn modèle avec beaucoup de FORMAT INVALIDE répond par des phrases : regarde ses réponses brutes "
      "ci-dessus avant de lancer le benchmark.")