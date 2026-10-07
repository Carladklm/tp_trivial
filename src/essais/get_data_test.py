import json
from pathlib import Path
import pandas as pd
import requests

OUTPUT = Path("data_test/questions_test.csv")

data = requests.get("https://opentdb.com/api.php", params={"amount": 50}).json()
print("response_code :", data["response_code"]) 

df = pd.DataFrame(data["results"])
df["incorrect_answers"] = df["incorrect_answers"].apply(json.dumps)  # liste -> texte

OUTPUT.parent.mkdir(parents=True, exist_ok=True)
df.to_csv(OUTPUT, index=False)
print(f"{len(df)} questions enregistrées dans {OUTPUT}\n")

# Aperçu de la donnée
print(df.head())
