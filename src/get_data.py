import json
import csv
import time
from pathlib import Path
import requests

URL_API = "https://opentdb.com/api.php"
TOKEN_URL = "https://opentdb.com/api_token.php"
OUTPUT = Path("bronze/questions_raw.csv")
PAUSE = 5.5 # On peut faire un appel que toutes les 5 secondes


# 1. On récupere le TOKEN --------------------------------------------------------------------------------------------------------------------------------

reponse_token = requests.get(TOKEN_URL, params={"command": "request"}) 
donnees_token = reponse_token.json()
token = donnees_token["token"]   


# 2. On récupere les questionss --------------------------------------------------------------------------------------------------------------------------

questions = []
amount = 50

while True:
    time.sleep(PAUSE)
    data = requests.get(URL_API, params={"amount": amount, "token": token}).json()
    code = data["response_code"]

    if code == 0:
        questions.extend(data["results"])
        print(f"{len(questions)} questions récupérées (lot de {amount})")
    elif code in (1, 4):
        if amount == 1:
            break                     
        amount = max(1, amount // 2) 
        print(f"Plus assez de questions, on passe à des lots de {amount}")
    elif code == 5:
        time.sleep(PAUSE)
    else:
        raise RuntimeError(f"Erreur de l api : {code}")


# 3. On sauvegarde les données dans bronze, un seul fichier ----------------------------------------------------------------------------------------------

OUTPUT.parent.mkdir(parents=True, exist_ok=True)
with open(OUTPUT, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=questions[0].keys())
    writer.writeheader()
    for q in questions:
        q["incorrect_answers"] = json.dumps(q["incorrect_answers"])
        writer.writerow(q)

print(f"{len(questions)} questions enregistrées dans {OUTPUT}\n")