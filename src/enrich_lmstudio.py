"""
Enrichissement Silver : pose chaque question à un LLM local (LM Studio)
et écrit les réponses dans data/silver/ai_responses/part_XXXX.parquet.

1 ligne = 1 question x 1 modèle x 1 version de prompt.

Le script est reprenable : au démarrage, il relit les fichiers déjà écrits
et saute les couples (question_id, model, prompt_version) déjà traités.

Exemples :
    python src/enrich_lmstudio.py --limit 20
    python src/enrich_lmstudio.py --prompts v2_strict v3_optimized --limit 200
    python src/enrich_lmstudio.py --input silver/questions.parquet --limit 20
"""

import argparse
import json
import random
import re
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests

# --------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------
BASE_URL = "http://localhost:1234/v1"          # serveur local de LM Studio
DEFAULT_MODEL = "llama-3.2-3b-instruct"         # mlx-community/Llama-3.2-3B-Instruct-4bit
TEMPERATURE = 0                                 # réponses déterministes = benchmark reproductible
MAX_TOKENS = 50                                 # assez pour une lettre, coupe les longs bavardages
TIMEOUT = 120                                   # secondes max par appel
BATCH_SIZE = 100                                # 1 fichier parquet tous les 100 résultats

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "data" / "silver" / "questions_clean.parquet"
PROMPTS_FILE = ROOT / "dbt_trivial" / "seeds" / "prompts.csv"
OUTPUT_DIR = ROOT / "data" / "silver" / "ai_responses"

LETTERS = "ABCD"


# --------------------------------------------------------------------------
# Préparation des questions et des prompts
# --------------------------------------------------------------------------
def load_prompts(path: Path) -> dict:
    """Lit seeds/prompts.csv. Les retours à la ligne y sont écrits '\\n'."""
    df = pd.read_csv(path, keep_default_na=False, dtype=str)
    prompts = {}
    for row in df.to_dict("records"):
        prompts[row["prompt_version"]] = {
            "system": row["system_prompt"].replace("\\n", "\n"),
            "user": row["user_template"].replace("\\n", "\n"),
            "structured": row["structured_output"].strip().lower() == "true",
        }
    return prompts


def to_list(value) -> list:
    """incorrect_answers peut arriver en liste, en tableau numpy ou en texte JSON."""
    if isinstance(value, str):
        return json.loads(value)
    return list(value)


def build_choices(row) -> tuple[list, str]:
    """Mélange les choix et renvoie (choix dans l'ordre présenté, lettre correcte).

    Le mélange est 'aléatoire' mais graine = question_id : il est identique
    à chaque exécution, donc tous les prompts et tous les modèles voient
    exactement les mêmes choix dans le même ordre.
    """
    correct = row["correct_answer"]
    choices = [correct] + to_list(row["incorrect_answers"])
    if row["type"] == "boolean":
        choices = ["True", "False"]               # ordre naturel pour un vrai/faux
    else:
        random.Random(row["question_id"]).shuffle(choices)
    return choices, LETTERS[choices.index(correct)]


def format_choices(choices: list) -> str:
    return "\n".join(f"{LETTERS[i]}) {c}" for i, c in enumerate(choices))


def build_messages(prompt: dict, question: str, choices: list) -> list:
    user = prompt["user"].format(question=question, choices=format_choices(choices))
    messages = []
    if prompt["system"]:
        messages.append({"role": "system", "content": prompt["system"]})
    messages.append({"role": "user", "content": user})
    return messages


# --------------------------------------------------------------------------
# Appel au modèle et lecture de la réponse
# --------------------------------------------------------------------------
def call_model(model: str, messages: list, structured: bool, nb_choices: int) -> tuple[str, float]:
    payload = {
        "model": model,
        "messages": messages,
        "temperature": TEMPERATURE,
        "max_tokens": MAX_TOKENS,
    }
    if structured:
        # Sortie structurée : le serveur force le modèle à produire
        # exactement {"answer": "<une lettre valide>"}.
        payload["response_format"] = {
            "type": "json_schema",
            "json_schema": {
                "name": "quiz_answer",
                "strict": True,
                "schema": {
                    "type": "object",
                    "properties": {"answer": {"type": "string", "enum": list(LETTERS[:nb_choices])}},
                    "required": ["answer"],
                },
            },
        }
    start = time.perf_counter()
    resp = requests.post(f"{BASE_URL}/chat/completions", json=payload, timeout=TIMEOUT)
    elapsed = time.perf_counter() - start
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"], elapsed


def extract_letter(raw: str, nb_choices: int, structured: bool):
    """Renvoie la lettre choisie par le modèle, ou None si le format est invalide."""
    valid = LETTERS[:nb_choices]
    text = (raw or "").strip()

    if structured:
        try:
            letter = str(json.loads(text).get("answer", "")).strip().upper()
            return letter if letter in valid else None
        except (json.JSONDecodeError, AttributeError):
            pass

    # 1) La réponse commence par la lettre : "B", "B)", "B.", "(B)", "B: Mars"
    m = re.match(r"^\(?([A-D])\s*(?:[).:]|$)", text)
    if m and m.group(1) in valid:
        return m.group(1)

    # 2) La lettre est annoncée : "The answer is B", "Answer: (C)"
    m = re.search(r"answer\s*(?:is)?\s*:?\s*\(?([A-D])\b", text, flags=re.IGNORECASE)
    if m and m.group(1).upper() in valid:
        return m.group(1).upper()

    return None


# --------------------------------------------------------------------------
# Écriture par lots et reprise
# --------------------------------------------------------------------------
def already_done() -> set:
    done = set()
    for part in sorted(OUTPUT_DIR.glob("part_*.parquet")):
        df = pd.read_parquet(part, columns=["question_id", "model", "prompt_version"])
        done.update(map(tuple, df.itertuples(index=False, name=None)))
    return done


def next_part_number() -> int:
    numbers = [int(p.stem.split("_")[1]) for p in OUTPUT_DIR.glob("part_*.parquet")]
    return max(numbers, default=0) + 1


def write_batch(rows: list) -> None:
    if not rows:
        return
    path = OUTPUT_DIR / f"part_{next_part_number():04d}.parquet"
    df = pd.DataFrame(rows)
    df["created_at"] = pd.to_datetime(df["created_at"], utc=True)
    df.to_parquet(path, index=False)
    print(f"   -> {len(rows)} réponses écrites dans {path.relative_to(ROOT)}")
    rows.clear()


# --------------------------------------------------------------------------
# Programme principal
# --------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark LLM sur les questions OpenTDB")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--prompts", nargs="+", help="versions à lancer (défaut : toutes)")
    parser.add_argument("--limit", type=int, help="nombre de questions (pour tester)")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    prompts = load_prompts(PROMPTS_FILE)
    versions = args.prompts or list(prompts)
    unknown = set(versions) - set(prompts)
    if unknown:
        raise SystemExit(f"Prompts inconnus : {unknown}. Disponibles : {list(prompts)}")

    questions = pd.read_parquet(args.input)
    # Trier par question_id (un hash) mélange catégories et difficultés :
    # les N premières questions forment un échantillon varié et toujours le même.
    questions = questions.sort_values("question_id").reset_index(drop=True)
    if args.limit:
        questions = questions.head(args.limit)

    done = already_done()
    buffer = []
    print(f"Modèle : {args.model} | prompts : {versions} | questions : {len(questions)}")
    print(f"Déjà traités (toutes exécutions confondues) : {len(done)}")

    try:
        for version in versions:
            prompt = prompts[version]
            run_id = f"{datetime.now():%Y%m%d_%H%M%S}_{args.model}_{version}"
            todo = questions[[(qid, args.model, version) not in done for qid in questions["question_id"]]]
            print(f"\n=== {version} : {len(todo)} questions à traiter ===")
            start = time.perf_counter()

            for i, row in enumerate(todo.to_dict("records"), start=1):
                choices, correct_letter = build_choices(row)
                messages = build_messages(prompt, row["question"], choices)
                try:
                    raw, elapsed = call_model(args.model, messages, prompt["structured"], len(choices))
                except requests.RequestException as err:
                    # On n'écrit rien : la question sera retentée à la prochaine exécution.
                    print(f"   ! {row['question_id']} : {err}")
                    continue

                letter = extract_letter(raw, len(choices), prompt["structured"])
                ai_answer = choices[LETTERS.index(letter)] if letter else None
                buffer.append({
                    "question_id": row["question_id"],
                    "run_id": run_id,
                    "model": args.model,
                    "prompt_version": version,
                    "prompt_text": "\n\n".join(m["content"] for m in messages),
                    "choices": choices,
                    "correct_letter": correct_letter,
                    "raw_response": raw,
                    "ai_letter": letter,
                    "ai_answer": ai_answer,
                    "ai_correct": letter == correct_letter,
                    "is_valid_format": letter is not None,
                    "response_time": round(elapsed, 3),
                    "created_at": datetime.now(timezone.utc),
                })

                if i % 10 == 0 or i == len(todo):
                    speed = (time.perf_counter() - start) / i
                    remaining = (len(todo) - i) * speed / 60
                    print(f"   {i}/{len(todo)}  ({speed:.2f} s/question, reste ~{remaining:.0f} min)")
                if len(buffer) >= BATCH_SIZE:
                    write_batch(buffer)

            write_batch(buffer)
    except KeyboardInterrupt:
        print("\nInterruption : sauvegarde des réponses déjà obtenues...")
        write_batch(buffer)

    print("\nTerminé.")


if __name__ == "__main__":
    main()
