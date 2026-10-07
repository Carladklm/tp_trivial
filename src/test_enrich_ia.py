import random
import re
import sys
import time
from datetime import datetime
from pathlib import Path
import lmstudio as lms
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")

# --- À MODIFIER -----------------------------------------------------------------------------------

RUN_ORDER = 1          # numéro de la ligne à utiliser (colonne run_order du CSV)
N_QUESTIONS = 20       # nombre de questions tirées au hasard (20 pour tester, 1000 pour le benchmark)

# --- Chemins et connexion -------------------------------------------------------------------------

ROOT = Path(__file__).resolve().parents[1]
CONFIG_FILE = ROOT / "prompt" / "benchmark_config.csv"
QUESTIONS_FILE = ROOT / "silver" / "questions_clean.parquet"
OUTPUT_DIR = ROOT / "silver" / "ai_responses"

LMSTUDIO_HOST = "localhost:1234"          # adresse du serveur LM Studio (onglet Developer)
lms.configure_default_client(LMSTUDIO_HOST)

LABELS = {"letters": ["A", "B", "C", "D"], "numbers": ["1", "2", "3", "4"]}


# --- Construction du prompt -----------------------------------------------------------------------

def build_choices(question_id: str, qtype: str, correct_answer: str, incorrect_answers) -> list:
    """Options dans l'ordre où elles sont présentées : choices[0] = A (ou 1), choices[1] = B (ou 2)...

    - Vrai/Faux : ordre fixe ["True", "False"] -> A = True, B = False.
    - QCM : bonne réponse + 3 mauvaises réponses MÉLANGÉES, sinon la bonne réponse serait toujours A.
      Le mélange a pour graine question_id : l'ordre change d'une question à l'autre, mais une même
      question a toujours le même ordre, pour tous les modèles et tous les prompts.
    """
    if qtype == "boolean":
        return ["True", "False"]
    options = [correct_answer] + list(incorrect_answers)
    random.Random(question_id).shuffle(options)
    return options


def format_options(choices: list, label_style: str) -> str:
    """Options affichées au modèle : 'A. Canada' / '1. Canada' / '- Canada'."""
    if label_style == "text":
        return "\n".join(f"- {c}" for c in choices)
    return "\n".join(f"{label}. {c}" for label, c in zip(LABELS[label_style], choices))


def label_of(index: int, choices: list, label_style: str) -> str:
    """Étiquette d'une option : 'C', '3' ou le texte de l'option."""
    return choices[index] if label_style == "text" else LABELS[label_style][index]


# --- Lecture de la réponse : UNIQUEMENT pour le suivi dans le terminal (non enregistrée) -----------

def normalize(text: str) -> str:
    """Minuscules, sans guillemets, ponctuation finale ni espaces en trop (pour comparer des textes)."""
    text = text.strip().strip("\"'`*").strip().rstrip(".!").strip()
    return " ".join(text.lower().split())


def parse_answer(raw: str, choices: list, label_style: str):
    """Renvoie l'index de l'option choisie (0, 1, 2, 3) ou None si la réponse est inexploitable."""
    text = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL)        # bloc de réflexion éventuel
    text = re.sub(r"^\s*(answer|réponse)\s*[:\-]\s*", "", text.strip(), flags=re.IGNORECASE)
    text = text.strip()
    if not text:
        return None

    if label_style in LABELS:
        allowed = LABELS[label_style][:len(choices)]          # A-B ou 1-2 pour un Vrai/Faux
        tokens = text.split()
        # Le premier mot doit être une étiquette seule : "C", "C.", "(C)", "C)". "1789" n'est pas "1".
        match = re.fullmatch(r"\(?([A-Da-d1-4])[).:]?", tokens[0])
        if not match or match.group(1).upper() not in allowed:
            return None
        index = allowed.index(match.group(1).upper())
        rest = " ".join(tokens[1:])
        # "C" seul est accepté ; "C. Canada" aussi, si le texte qui suit est bien celui de l'option C
        return index if not rest or normalize(rest) == normalize(choices[index]) else None

    # label_style == "text" : la réponse doit correspondre exactement à une option
    normalized = [normalize(c) for c in choices]
    answer = normalize(text.splitlines()[0])
    return normalized.index(answer) if answer in normalized else None


# --- 1. Choix de l'exécution ----------------------------------------------------------------------

config = pd.read_csv(CONFIG_FILE, keep_default_na=False)
run = config[config["run_order"] == RUN_ORDER]
if run.empty:
    raise ValueError(f"Aucune ligne avec run_order = {RUN_ORDER} dans {CONFIG_FILE.name}")
run = run.iloc[0]
disable_thinking = str(run["disable_thinking"]).lower() == "true"

print(f"Exécution : {run['run_id']}  (modèle {run['lmstudio_id']}, prompt {run['prompt_version']}, "
      f"température {run['temperature']})")

# Récupère le modèle dans LM Studio (et le charge en mémoire s'il ne l'est pas encore)
try:
    model = lms.llm(run["lmstudio_id"])
except Exception as exc:
    raise SystemExit(
        f"\nImpossible d'obtenir le modèle '{run['lmstudio_id']}' : {type(exc).__name__}: {exc}\n"
        f"Vérifie que LM Studio est ouvert, que le serveur est démarré ({LMSTUDIO_HOST}) et que le modèle "
        "est téléchargé. Le nom exact des modèles est affiché par la commande `lms ls` ou dans l'onglet "
        "Developer ; corrige la colonne lmstudio_id du CSV si besoin.")
print(f"Modèle prêt : {run['lmstudio_id']}")


# --- 2. Tirage aléatoire des questions ------------------------------------------------------------

questions = pd.read_parquet(QUESTIONS_FILE)
sample = questions.sample(n=N_QUESTIONS, random_state=int(run["sample_seed"])).reset_index(drop=True)
print(f"{len(sample)} questions tirées au hasard (graine {run['sample_seed']}) sur {len(questions)}\n")


# --- 3. Interrogation du modèle -------------------------------------------------------------------

system_prompt = run["system_prompt"] + (" /no_think" if disable_thinking else "")
rows = []
suivi = []          # (bonne réponse ?, format valide ?) : pour l'affichage uniquement, jamais enregistré
started_at = datetime.now()

try:
    for i, q in enumerate(sample.itertuples(), start=1):
        choices = build_choices(q.question_id, q.type, q.correct_answer, q.incorrect_answers)
        user_prompt = run["user_template"].format(question=q.question,
                                                  options=format_options(choices, run["label_style"]))
        chat = lms.Chat(system_prompt) if system_prompt.strip() else lms.Chat()
        chat.add_user_message(user_prompt)

        raw, error, prompt_tokens, completion_tokens, stop_reason, first_token = "", None, None, None, None, None
        start = time.perf_counter()
        try:
            result = model.respond(chat, config={
                "temperature": float(run["temperature"]),
                "maxTokens": int(run["max_tokens"]),
            })
            raw = result.content or ""
            prompt_tokens = result.stats.prompt_tokens_count
            completion_tokens = result.stats.predicted_tokens_count
            stop_reason = str(result.stats.stop_reason)
            first_token = result.stats.time_to_first_token_sec
        except Exception as exc:                       # serveur arrêté, modèle déchargé...
            error = f"{type(exc).__name__}: {exc}"
        response_time = time.perf_counter() - start

        correct_index = choices.index(q.correct_answer)
        ai_index = parse_answer(raw, choices, run["label_style"]) if error is None else None
        suivi.append((ai_index == correct_index, ai_index is not None))

        rows.append({
            # exécution
            "run_id": run["run_id"], "run_order": int(run["run_order"]),
            "model_key": run["model_key"], "lmstudio_id": run["lmstudio_id"], "model_name": run["model_name"],
            "publisher": run["publisher"], "country": run["country"], "params_b": float(run["params_b"]),
            "prompt_version": run["prompt_version"], "label_style": run["label_style"],
            "temperature": float(run["temperature"]), "max_tokens": int(run["max_tokens"]),
            "sample_seed": int(run["sample_seed"]), "n_questions": N_QUESTIONS,
            # question
            "question_id": q.question_id, "type": q.type, "difficulty": q.difficulty,
            "category_group": q.category_group, "category_name": q.category_name,
            "question": q.question, "choices": choices, "correct_answer": q.correct_answer,
            "correct_label": label_of(correct_index, choices, run["label_style"]),
            # prompt envoyé
            "system_prompt": system_prompt, "user_prompt": user_prompt,
            # réponse du modèle
            "raw_response": raw,
            "response_time": round(response_time, 4),
            "prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens,
            "time_to_first_token": first_token, "stop_reason": stop_reason,
            "error": error,
            "created_at": datetime.now().isoformat(timespec="seconds"),
        })

        if i % 10 == 0 or i == len(sample):
            print(f"{i:>5}/{len(sample)}  bonnes réponses (provisoire) : {sum(c for c, _ in suivi) / i:6.1%}  "
                  f"format valide : {sum(v for _, v in suivi) / i:6.1%}  "
                  f"temps moyen : {sum(r['response_time'] for r in rows) / i:.2f} s")
        if error and i == 1:
            print(f"\n!! Le premier appel a échoué : {error}")
            print("   Vérifie que LM Studio est toujours ouvert et que le serveur est démarré.\n")
            break

except KeyboardInterrupt:
    print("\nInterruption : on enregistre les réponses déjà obtenues.")


# --- 4. Écriture en Silver ------------------------------------------------------------------------

if rows and not all(r["error"] for r in rows):
    result = pd.DataFrame(rows)
    # Types fixés explicitement : une colonne entièrement vide (ex. aucune erreur) garde le même type
    # dans tous les fichiers, sinon DuckDB la lit en "null" et les fichiers ne se combinent plus.
    result = result.astype({"raw_response": "string", "error": "string", "stop_reason": "string",
                            "prompt_tokens": "Int64", "completion_tokens": "Int64",
                            "time_to_first_token": "Float64"})
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_file = OUTPUT_DIR / f"{run['run_id']}__n{N_QUESTIONS}__{started_at:%Y%m%d_%H%M%S}.parquet"
    result.to_parquet(output_file, index=False)

    print(f"\n{len(result)} réponses enregistrées dans {output_file.relative_to(ROOT)}")
    print(f"Bonnes réponses (provisoire) : {sum(c for c, _ in suivi) / len(suivi):.1%}   "
          f"Format valide : {sum(v for _, v in suivi) / len(suivi):.1%}   "
          f"Temps moyen : {result['response_time'].mean():.2f} s   "
          f"Erreurs : {result['error'].notna().sum()}")
    invalides = [r["raw_response"] for r, (_, v) in zip(rows, suivi) if not v and r["error"] is None]
    if invalides:
        print("\nExemples de réponses au mauvais format :")
        for texte in invalides[:5]:
            print("  ", repr(texte))
else:
    print("Aucune réponse obtenue du modèle : aucun fichier écrit.")