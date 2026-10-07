import argparse
import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from utils.ai_all import lancer_benchmark
from utils.clean_questions import nettoyer_questions
from utils.get_data import collecter_questions

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
STREAMLIT_APP = ROOT / "app" / "streamlit_app.py"


# 1. Paramètres du pipeline -------------------------------------------

N_QUESTIONS_API = None   # questions à récolter avec l'API : None = toutes les questions disponibles
RUN_ORDERS = None        # lignes de benchmark_config.csv à exécuter : None = toutes, ou une liste, ex. [1, 2, 3, 4]
N_QUESTIONS_IA = None    # questions posées par exécution : None = toutes les questions de silver
BATCH_SIZE = 500         # un fichier Parquet est écrit toutes les BATCH_SIZE questions
MAX_ERREURS = 5          # erreurs consécutives avant d'abandonner une exécution (serveur coupé...)


# 2. Fonctions utilitaires -------------------------------------------------------------------------------------

# Permet de lire les paramètres passés en ligne de commande (les valeurs ci-dessus servent par défaut)
def lire_parametres() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Lance tout le pipeline : collecte, nettoyage, IA, dbt.")
    parser.add_argument("--n-questions-api", type=int, default=N_QUESTIONS_API,
                        help="questions à récolter avec l'API (défaut : toutes)")
    parser.add_argument("--run-orders", type=int, nargs="+", default=RUN_ORDERS,
                        help="lignes de benchmark_config.csv à exécuter, ex. --run-orders 1 2 3 (défaut : toutes)")
    parser.add_argument("--n-questions-ia", type=int, default=N_QUESTIONS_IA,
                        help="questions posées par exécution (défaut : toutes)")
    parser.add_argument("--batch-size", type=int, default=BATCH_SIZE,
                        help=f"questions par fichier Parquet (défaut : {BATCH_SIZE})")
    parser.add_argument("--max-erreurs", type=int, default=MAX_ERREURS,
                        help=f"erreurs consécutives avant d'abandonner une exécution (défaut : {MAX_ERREURS})")
    return parser.parse_args()

# Permet d'afficher le titre d'une étape
def titre(numero: int, texte: str) -> None:
    print("\n" + "#" * 100)
    print(f"# ÉTAPE {numero}/4 : {texte}")
    print("#" * 100 + "\n")

# Permet de lancer dbt build sur tous les modèles (staging, intermediate, marts)
def lancer_dbt() -> None:
    from dbt.cli.main import dbtRunner

    # Les sources dbt lisent 'silver/...' en chemin relatif : on se place à la racine du projet
    os.chdir(ROOT)
    resultat = dbtRunner().invoke(["build", "--project-dir", str(ROOT), "--profiles-dir", str(ROOT)])
    if not resultat.success:
        raise RuntimeError("dbt build a échoué (voir les messages ci-dessus).")

# Permet de trouver un port libre pour Streamlit (8501 par défaut, le suivant s'il est déjà pris)
def port_libre(depart: int = 8501) -> int:
    for port in range(depart, depart + 20):
        with socket.socket() as s:
            if s.connect_ex(("localhost", port)) != 0:
                return port
    raise RuntimeError(f"Aucun port libre entre {depart} et {depart + 19} pour Streamlit.")

# Permet de lancer l'app Streamlit et d'afficher son lien (elle tourne jusqu'au Ctrl+C)
def lancer_streamlit() -> None:
    port = port_libre()
    lien = f"http://localhost:{port}"
    print("\n" + "=" * 100)
    print(f"Dashboard Streamlit : {lien}")
    print("Ctrl+C pour arrêter l'app.")
    print("=" * 100 + "\n")

    # Lancé depuis la racine du projet pour que .streamlit/config.toml (thème) soit pris en compte
    process = subprocess.Popen([sys.executable, "-m", "streamlit", "run", str(STREAMLIT_APP),
                                "--server.port", str(port)], cwd=ROOT)
    try:
        process.wait()
    except KeyboardInterrupt:
        process.terminate()
        process.wait()
        print("\nStreamlit arrêté.")


# 3. Pipeline --------------------------------------------------------------------------------------------------

def main() -> None:
    args = lire_parametres()
    debut = time.perf_counter()

    print("Paramètres :")
    for nom, valeur in vars(args).items():
        print(f"  {nom:<16} {'toutes' if valeur is None else valeur}")

    titre(1, "collecte des questions (API OpenTDB -> bronze)")
    collecter_questions(args.n_questions_api)

    titre(2, "nettoyage des questions (bronze -> silver)")
    nettoyer_questions()

    titre(3, "réponses des IA (LM Studio -> silver/ai_responses)")
    lancer_benchmark(run_orders=args.run_orders, n_questions=args.n_questions_ia,
                     batch_size=args.batch_size, max_erreurs=args.max_erreurs)

    titre(4, "dbt build (staging -> intermediate -> marts)")
    lancer_dbt()

    print(f"\nPipeline terminé en {(time.perf_counter() - debut) / 60:.1f} min.")

    lancer_streamlit()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit("\nPipeline interrompu (Ctrl+C) : les étapes suivantes ne sont pas lancées.")
