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

RUN_ORDERS = None      # lignes du CSV à exécuter : None = toutes, ou une liste, ex. [1, 2, 3, 4] ou range(1, 9)
N_QUESTIONS = None     # questions par exécution : 1000 pour le benchmark, None = toutes les questions
BATCH_SIZE = 500       # un fichier Parquet est écrit toutes les BATCH_SIZE questions
MAX_ERREURS = 5        # erreurs consécutives avant d'abandonner une exécution (serveur coupé...)

# --- Chemins et connexion -------------------------------------------------------------------------

ROOT = Path(__file__).resolve().parents[1]
CONFIG_FILE = ROOT / "prompt" / "benchmark_config.csv"
QUESTIONS_FILE = ROOT / "silver" / "questions_clean.parquet"
OUTPUT_DIR = ROOT / "silver" / "ai_responses"

LMSTUDIO_HOST = "localhost:1234"          # adresse du serveur LM Studio (onglet Developer)
lms.configure_default_client(LMSTUDIO_HOST)

LABELS = {"letters": ["A", "B", "C", "D"], "numbers": ["1", "2", "3", "4"]}

# Types fixés pour que tous les fichiers aient le même schéma, même quand une colonne est vide
DTYPES = {"raw_response": "string", "stop_reason": "string", "prompt_tokens": "Int64",
          "completion_tokens": "Int64", "time_to_first_token": "Float64"}


# --- Construction du prompt -----------------------------------------------------------------------

def build_choices(question_id: str, qtype: str, correct_answer: str, incorrect_answers) -> list:
    """Options dans l'ordre présenté : choices[0] = A (ou 1), choices[1] = B (ou 2)...

    - Vrai/Faux : ordre fixe ["True", "False"] -> A = True, B = False.
    - QCM : bonne réponse + 3 mauvaises réponses mélangées (sinon la bonne réponse serait toujours A),
      avec question_id comme graine : une même question a toujours le même ordre, pour tous les
      modèles et tous les prompts.
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
    text = text.strip().strip("\"'`*").strip().rstrip(".!").strip()
    return " ".join(text.lower().split())


def parse_answer(raw: str, choices: list, label_style: str):
    """Index de l'option choisie (0, 1, 2, 3) ou None si la réponse est inexploitable."""
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


# --- Écriture et reprise --------------------------------------------------------------------------

def already_done(run_id: str) -> set:
    """Questions déjà traitées pour cette exécution (lues dans tous les fichiers du dossier)."""
    parts = sorted(OUTPUT_DIR.glob("part_*.parquet"))
    if not parts:
        return set()
    existing = pd.concat([pd.read_parquet(p, columns=["run_id", "question_id"]) for p in parts])
    return set(existing.loc[existing["run_id"] == run_id, "question_id"])


def write_part(rows: list) -> Path:
    """Écrit un lot dans le prochain fichier libre : part_0001, part_0002, ... (numérotation commune)."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    numbers = [int(p.stem.split("_")[1]) for p in OUTPUT_DIR.glob("part_*.parquet")]
    path = OUTPUT_DIR / f"part_{max(numbers, default=0) + 1:04d}.parquet"
    pd.DataFrame(rows).astype(DTYPES).to_parquet(path, index=False)
    return path


# --- 1. Chargement ---------------------------------------------------------------------------------

config = pd.read_csv(CONFIG_FILE, keep_default_na=False).sort_values("run_order")
if RUN_ORDERS is not None:
    config = config[config["run_order"].isin(list(RUN_ORDERS))]
if config.empty:
    raise SystemExit(f"Aucune ligne à exécuter : vérifie RUN_ORDERS ({RUN_ORDERS}).")

questions = pd.read_parquet(QUESTIONS_FILE)
n_total = len(questions) if N_QUESTIONS is None else min(N_QUESTIONS, len(questions))

print(f"{len(config)} exécution(s) à lancer, {n_total} questions chacune, "
      f"un fichier toutes les {BATCH_SIZE} questions.\n")


# --- 2. Boucle sur les exécutions -----------------------------------------------------------------

bilan = []
model, model_id = None, None

try:
    for run in config.itertuples():
        print("=" * 100)
        print(f"[{run.run_order}] {run.run_id}  —  modèle {run.lmstudio_id}, prompt {run.prompt_version}, "
              f"température {run.temperature}")

        # Questions de cette exécution : même tirage pour tous (graine du CSV), moins celles déjà faites
        ordre = questions.sample(frac=1, random_state=int(run.sample_seed)).reset_index(drop=True)
        ordre["sample_rank"] = range(1, len(ordre) + 1)          # position dans le tirage
        sample = ordre.head(n_total)
        done = already_done(run.run_id)
        todo = sample[~sample["question_id"].isin(done)]
        if todo.empty:
            print(f"Déjà terminée ({len(done)} questions enregistrées) : on passe à la suivante.\n")
            bilan.append({"run_id": run.run_id, "statut": "déjà terminée", "nouvelles": 0})
            continue
        print(f"{len(sample) - len(todo)} questions déjà faites, {len(todo)} à faire.")

        # Changement de modèle : on décharge l'ancien pour libérer la mémoire, puis on charge le nouveau
        if run.lmstudio_id != model_id:
            if model is not None:
                try:
                    model.unload()
                except Exception:
                    pass
            try:
                model = lms.llm(run.lmstudio_id)
                model_id = run.lmstudio_id
                print(f"Modèle prêt : {model_id}")
            except Exception as exc:
                model, model_id = None, None
                print(f"!! Modèle '{run.lmstudio_id}' indisponible ({type(exc).__name__}: {exc}).\n"
                      "   Vérifie qu'il est téléchargé et que lmstudio_id correspond au nom affiché par "
                      "`lms ls`. On passe à l'exécution suivante.\n")
                bilan.append({"run_id": run.run_id, "statut": "modèle introuvable", "nouvelles": 0})
                continue

        system_prompt = run.system_prompt + (" /no_think" if str(run.disable_thinking).lower() == "true" else "")
        rows, suivi = [], []
        erreurs_consecutives, nouvelles = 0, 0
        debut_run = time.perf_counter()

        try:
            for i, q in enumerate(todo.itertuples(), start=1):
                choices = build_choices(q.question_id, q.type, q.correct_answer, q.incorrect_answers)
                user_prompt = run.user_template.format(question=q.question,
                                                       options=format_options(choices, run.label_style))
                chat = lms.Chat(system_prompt) if system_prompt.strip() else lms.Chat()
                chat.add_user_message(user_prompt)

                start = time.perf_counter()
                try:
                    result = model.respond(chat, config={"temperature": float(run.temperature),
                                                         "maxTokens": int(run.max_tokens)})
                except Exception as exc:
                    # La question n'est pas enregistrée : elle sera reposée au prochain lancement
                    erreurs_consecutives += 1
                    print(f"   erreur sur {q.question_id} ({type(exc).__name__}: {exc})")
                    if erreurs_consecutives >= MAX_ERREURS:
                        print(f"!! {MAX_ERREURS} erreurs d'affilée : exécution interrompue "
                              "(LM Studio est-il toujours ouvert ?).")
                        break
                    continue
                response_time = time.perf_counter() - start
                erreurs_consecutives = 0

                raw = result.content or ""
                correct_index = choices.index(q.correct_answer)
                ai_index = parse_answer(raw, choices, run.label_style)
                suivi.append((ai_index == correct_index, ai_index is not None, response_time))

                rows.append({
                    # exécution
                    "run_id": run.run_id, "run_order": int(run.run_order),
                    "model_key": run.model_key, "lmstudio_id": run.lmstudio_id, "model_name": run.model_name,
                    "publisher": run.publisher, "country": run.country, "params_b": float(run.params_b),
                    "prompt_version": run.prompt_version, "label_style": run.label_style,
                    "temperature": float(run.temperature), "max_tokens": int(run.max_tokens),
                    "sample_seed": int(run.sample_seed), "sample_rank": int(q.sample_rank),
                    # question
                    "question_id": q.question_id, "type": q.type, "difficulty": q.difficulty,
                    "category_group": q.category_group, "category_name": q.category_name,
                    "question": q.question, "choices": choices, "correct_answer": q.correct_answer,
                    "correct_label": label_of(correct_index, choices, run.label_style),
                    # prompt envoyé
                    "system_prompt": system_prompt, "user_prompt": user_prompt,
                    # réponse brute et mesures
                    "raw_response": raw,
                    "response_time": round(response_time, 4),
                    "prompt_tokens": result.stats.prompt_tokens_count,
                    "completion_tokens": result.stats.predicted_tokens_count,
                    "time_to_first_token": result.stats.time_to_first_token_sec,
                    "stop_reason": str(result.stats.stop_reason),
                    "created_at": datetime.now().isoformat(timespec="seconds"),
                })

                # Écriture d'un fichier toutes les BATCH_SIZE questions
                if len(rows) == BATCH_SIZE:
                    path = write_part(rows)
                    nouvelles += len(rows)
                    print(f"   -> {path.relative_to(ROOT)} ({len(rows)} réponses)")
                    rows = []

                if i % 50 == 0 or i == len(todo):
                    n = len(suivi)
                    reste = (len(todo) - i) * sum(t for *_, t in suivi) / n
                    print(f"{i:>6}/{len(todo)}  bonnes réponses (provisoire) : {sum(c for c, _, _ in suivi) / n:6.1%}"
                          f"  format valide : {sum(v for _, v, _ in suivi) / n:6.1%}"
                          f"  {sum(t for *_, t in suivi) / n:.2f} s/question  reste ~{reste / 60:.0f} min")
        finally:
            # Le dernier lot incomplet est écrit même en cas d'erreur ou d'interruption (Ctrl+C)
            if rows:
                path = write_part(rows)
                nouvelles += len(rows)
                print(f"   -> {path.relative_to(ROOT)} ({len(rows)} réponses)")

        n = len(suivi)
        bilan.append({
            "run_id": run.run_id,
            "statut": "terminée" if nouvelles == len(todo) else "incomplète",
            "nouvelles": nouvelles,
            "bonnes réponses (provisoire)": f"{sum(c for c, _, _ in suivi) / n:.1%}" if n else "-",
            "format valide": f"{sum(v for _, v, _ in suivi) / n:.1%}" if n else "-",
            "durée": f"{(time.perf_counter() - debut_run) / 60:.1f} min",
        })
        print()

except KeyboardInterrupt:
    print("\nInterruption (Ctrl+C) : les réponses obtenues sont enregistrées. "
          "Relance le script pour reprendre là où il s'est arrêté.")


# --- 3. Bilan --------------------------------------------------------------------------------------

print("=" * 100)
print("BILAN")
if bilan:
    print(pd.DataFrame(bilan).fillna("-").to_string(index=False))
print(f"\nRéponses dans : {OUTPUT_DIR.relative_to(ROOT)}/part_*.parquet")