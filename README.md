# tp_trivial : benchmark de petits LLM sur des questions de Trivial Pursuit

Ce projet mesure à quel point de petits modèles de langage, exécutés en local avec LM Studio, répondent juste à des questions de culture générale. Les questions viennent de l'API [Open Trivia DB](https://opentdb.com/). Elles traversent un data lake en architecture médaillon (bronze → silver → gold), et les réponses des modèles sont notées et agrégées avec dbt sur DuckDB. Un dashboard Streamlit affiche le résultat.

**En chiffres** : 5 296 questions × 4 modèles × 4 prompts = **84 736 réponses**.

![Architecture médaillon du projet : sources, bronze, silver, gold et restitution](docs/architecture.png)

---

## Sommaire

1. [Résultats clés](#1-résultats-clés)
2. [Méthodologie](#2-méthodologie)
3. [Organisation du projet](#3-organisation-du-projet)
4. [Utilisation du projet](#4-utilisation-du-projet)
5. [Modèles dbt](#5-modèles-dbt)
6. [Macros dbt](#6-macros-dbt)
7. [Dashboard Streamlit](#7-dashboard-streamlit)
8. [Limites](#8-limites)

---

## 1. Résultats clés

Score moyen sur les 4 prompts, avec l'intervalle de confiance de Wilson à 95 % :

| Rang | Modèle | Taille | Accuracy | IC 95 % | Meilleur prompt |
|---|---|---|---|---|---|
| 1 | Ministral 3 8B Instruct (Mistral AI) | 8 B | **68,1 %** | 67,4 – 68,9 % | v3_text (69,7 %) |
| 2 | Qwen2.5 3B Instruct (Alibaba) | 3 B | **61,3 %** | 60,5 – 62,0 % | v3_text (62,1 %) |
| 3 | LFM2 1.2B (Liquid AI) | 1,2 B | **46,5 %** | 45,7 – 47,3 % | v2_numbers (47,9 %) |
| 4 | Gemma 3 1B (Google) | 1 B | **41,1 %** | 40,4 – 41,9 % | v3_text (42,6 %) |

Le hasard donne 28,7 % de bonnes réponses : 25 % sur un QCM, 50 % sur un Vrai/Faux, pondérés par la part de chaque type.

- **La taille compte** : le classement suit exactement le nombre de paramètres.
- **Le format du prompt a moins d'effet que le modèle** : l'écart entre le meilleur et le pire prompt va de 1,6 point (Qwen) à 3,8 points (Ministral).
- **La température 1.0 déstabilise les réponses** sans toujours changer le score. Ministral perd 4,3 points, alors que Qwen garde la même réponse sur 97 % des questions.
- **Gemma 3 1B a un biais de position** : il répond « A » sur environ 47 % des QCM, alors que « A » n'est la bonne réponse que dans environ 26 % des cas.

Ces chiffres viennent des tables `gold.mart_leaderboard`, `gold.mart_model_profile` et `gold.mart_temperature_effect`. Le dashboard les présente en détail.

---

## 2. Méthodologie

### 2.1 Architecture médaillon

| Couche | Contenu | Produit par |
|---|---|---|
| **Bronze** | `bronze/questions_raw.csv` : questions brutes de l'API, sans aucune transformation | `src/utils/get_data.py` |
| **Silver** | `silver/questions_clean.parquet` : questions nettoyées et contrôlées<br>`silver/ai_responses/part_*.parquet` : réponses brutes des modèles<br>schéma DuckDB `silver` : vues `stg_*` et tables `int_*` | `src/utils/clean_questions.py`<br>`src/utils/ai_all.py`<br>dbt |
| **Gold** | schéma DuckDB `gold` : 8 tables `mart_*`, une par question d'analyse | dbt |

Chaque couche ne lit que la couche précédente. Le dashboard ne lit que `gold`.

### 2.2 Collecte (bronze)

- L'API impose **une requête toutes les 5 secondes**. Le script attend 5,5 s entre deux appels.
- Un **token de session** OpenTDB garantit que l'API ne renvoie jamais deux fois la même question.
- Les questions sont demandées par lots de 50, le maximum de l'API. Quand la base s'épuise (codes 1 et 4), la taille du lot est divisée par deux jusqu'à 1, ce qui permet de récupérer les dernières questions.
- Résultat : **5 299 questions**, écrites telles quelles dans un CSV. Chaque collecte écrase ce fichier.

### 2.3 Nettoyage et contrat de données (bronze → silver)

Le script `clean_questions.py` applique des **contrôles bloquants** à trois moments. Si un seul échoue, le script s'arrête et n'écrit rien de faux en silver.

1. **Contrat bronze** : colonnes attendues, aucune valeur vide, `type` dans {multiple, boolean}, `difficulty` dans {easy, medium, hard}, 3 mauvaises réponses pour un QCM et 1 pour un Vrai/Faux, Vrai/Faux répondu par True ou False.
2. **Nettoyage** :
   - décodage des entités HTML (`&quot;` → `"`), suppression des tirets conditionnels et des espaces insécables ;
   - séparation de la catégorie en `category_group` / `category_name` ;
   - ajout de `difficulty_level` (1 à 3) et de `nb_options` ;
   - création d'un identifiant stable `question_id`, qui correspond aux 12 premiers caractères du MD5 de « question + bonne réponse ». Il permet de supprimer les doublons : 3 questions, d'où **5 296 questions** en silver.
3. **Après nettoyage** : identifiant unique, plus aucune entité HTML ni espace en trop, bonne réponse absente des mauvaises réponses, aucune option en double. Le fichier Parquet est ensuite relu pour vérifier son contenu.

### 2.4 Benchmark des modèles (silver)

Les 16 exécutions sont décrites dans **`prompt/benchmark_config.csv`**, une ligne par couple modèle × prompt :

| Modèle | `lmstudio_id` | Éditeur | Pays | Paramètres |
|---|---|---|---|---|
| Gemma 3 1B | `google/gemma-3-1b` | Google | États-Unis | 1 B |
| LFM2 1.2B | `liquid/lfm2-1.2b` | Liquid AI | États-Unis | 1,2 B |
| Qwen2.5 3B Instruct | `qwen2.5-3b-instruct` | Alibaba | Chine | 3 B |
| Ministral 3 8B Instruct | `ministral-3-8b-instruct-2512` | Mistral AI | France | 8 B |

| Prompt | Options affichées | Réponse attendue | Température | `max_tokens` |
|---|---|---|---|---|
| `v1_letters` | A. / B. / C. / D. | une lettre (référence) | 0 | 5 |
| `v2_numbers` | 1. / 2. / 3. / 4. | un chiffre | 0 | 5 |
| `v3_text` | `- option` | le texte exact de l'option | 0 | 40 |
| `v4_letters_hot` | A. / B. / C. / D. | une lettre | **1.0** | 5 |

`v4_letters_hot` ne diffère de `v1_letters` que par la température. On peut ainsi mesurer l'effet de l'aléatoire seul.

**Choix qui rendent les résultats comparables :**

- **Mêmes questions pour tous** : le tirage utilise la graine `sample_seed = 42` du CSV.
- **Même ordre des options pour tous** : pour un QCM, la bonne réponse est mélangée aux 3 mauvaises avec `question_id` comme graine. Une question a donc le même ordre d'options pour les 4 modèles et les 4 prompts. Sans ce mélange, la bonne réponse serait toujours « A ». Pour un Vrai/Faux, l'ordre est toujours A = True, B = False.
- **Réponse brute conservée** : le script Python enregistre la réponse telle quelle (`raw_response`) avec le prompt envoyé, le nombre de tokens, le temps de réponse et `stop_reason`. **La notation se fait dans dbt**, pas en Python. On peut donc changer la règle de notation sans reposer les 84 736 questions. Le score affiché dans le terminal pendant l'exécution n'est qu'un suivi provisoire.

**Robustesse de l'exécution :**

- un fichier `part_XXXX.parquet` est écrit tous les `batch_size` questions, ce qui limite la perte en cas de plantage ;
- **reprise automatique** : les questions déjà présentes pour un `run_id` sont sautées au lancement suivant ;
- après `max_erreurs` erreurs consécutives (serveur LM Studio coupé, par exemple), l'exécution s'arrête proprement ;
- un Ctrl+C enregistre le lot en cours avant de s'arrêter.

### 2.5 Notation et agrégation (dbt, silver → gold)

La règle de notation se trouve dans `int_ai_responses_scored` :

1. **Nettoyage** de la réponse brute : suppression des balises `<think>…</think>`, du préfixe « Answer: » et des espaces.
2. **Lecture** de l'option choisie :
   - prompts lettres et chiffres : le premier mot doit être une étiquette autorisée (`A`, `(B)`, `C.`…). Si du texte suit, il doit correspondre à l'option, comme dans « B. False » ;
   - prompt texte : la première ligne, normalisée (minuscules, ponctuation retirée), doit être égale à une option.
3. **Statut** de la réponse : `correct`, `incorrect` ou `invalid_format`. Une réponse illisible ne compte pas comme une erreur de connaissance, mais comme une erreur de format.

Les marts calculent ensuite trois indicateurs :

- **accuracy**, avec son **intervalle de confiance de Wilson** à 95 %, pour savoir si un écart est réel ou dû au hasard ;
- **random_baseline** : le score qu'obtiendrait le hasard, soit 0,25 pour un QCM et 0,5 pour un Vrai/Faux ;
- **chance_corrected_score** = (accuracy − baseline) / (1 − baseline). Il vaut 0 au niveau du hasard et 1 pour un sans-faute.

---

## 3. Organisation du projet

```
.
├── src/
│   ├── main.py                  ← lance tout le pipeline (point d'entrée)
│   ├── utils/
│   │   ├── get_data.py          ← collecte API → bronze      collecter_questions()
│   │   ├── clean_questions.py   ← bronze → silver            nettoyer_questions()
│   │   └── ai_all.py            ← questions → LM Studio      lancer_benchmark()
│   ├── models/                  ← modèles dbt
│   │   ├── sources.yml
│   │   ├── staging/             ← stg_*  (vues, schéma silver)
│   │   ├── intermediate/        ← int_*  (tables, schéma silver)
│   │   └── marts/               ← mart_* (tables, schéma gold)
│   ├── macros/                  ← macros dbt
│   └── essais/                  ← scripts de test et d'exploration (hors pipeline)
├── prompt/
│   └── benchmark_config.csv     ← les 16 exécutions (modèle, prompt, température…)
├── bronze/                      ← questions brutes (CSV)
├── silver/                      ← questions nettoyées + réponses des IA (Parquet)
├── warehouse/                   ← base DuckDB construite par dbt (non versionnée)
├── app/                         ← dashboard Streamlit
│   ├── streamlit_app.py         ← page d'accueil (classement général)
│   ├── pages/                   ← 8 pages d'analyse
│   └── lib/                     ← accès aux données, graphiques, style
├── .streamlit/config.toml       ← thème du dashboard
├── docs/STREAMLIT_SPEC.md       ← cahier des charges du dashboard
├── dbt_project.yml
├── profiles.yml                 ← connexion dbt → warehouse/trivial_questions.duckdb
└── requirements.txt
```

**Ce qui est versionné** : le code, la config, et les données `bronze/` et `silver/`. Le benchmark complet est donc reproductible sans rappeler l'API ni les modèles. **Ce qui ne l'est pas** : `.venv/`, `warehouse/`, `target/` et `logs/`. Tout cela se régénère avec `dbt build`.

---

## 4. Utilisation du projet

Cette partie suit l'ordre réel d'utilisation : on installe le projet, on lance le pipeline, puis on ouvre le dashboard.

```
Étape 1  Installer          venv + requirements.txt
Étape 2  Préparer           LM Studio (serveur + 4 modèles), vérifier dbt
Étape 3  Lancer             python src/main.py
           ├─ 1/4 Collecte      API OpenTDB      → bronze/questions_raw.csv
           ├─ 2/4 Nettoyage     bronze           → silver/questions_clean.parquet
           ├─ 3/4 Réponses IA   LM Studio        → silver/ai_responses/part_*.parquet
           └─ 4/4 dbt build     silver           → warehouse/ (schémas silver et gold)
Étape 4  Explorer           Streamlit s'ouvre sur http://localhost:8501
```

Tu peux aussi **sauter les étapes 2 et 3** : les données `bronze/` et `silver/` sont versionnées, donc `dbt build` puis Streamlit suffisent pour explorer les résultats (§ 4.6).

### 4.1 Prérequis

- **Python 3.14** (version fixée dans `.python-version`).
- **[LM Studio](https://lmstudio.ai/)**, uniquement pour l'étape « réponses des IA ».
- Git.

### 4.2 Étape 1 : installer

```powershell
git clone https://github.com/Carladklm/tp_trivial.git
cd tp_trivial

python -m venv .venv
.venv\Scripts\Activate.ps1          # Windows PowerShell
# source .venv/bin/activate         # macOS / Linux

pip install -r requirements.txt
```

`requirements.txt` installe pandas, pyarrow, requests, dbt-duckdb (qui inclut DuckDB), streamlit et lmstudio. Toutes les commandes qui suivent se lancent **depuis la racine du projet, avec le venv activé**.

### 4.3 Étape 2 : préparer LM Studio et dbt

1. Dans LM Studio, télécharge les 4 modèles du tableau du § 2.4.
2. Dans l'onglet **Developer**, démarre le serveur sur `localhost:1234`.
3. Vérifie les noms avec `lms ls` : ils doivent être **exactement** ceux de la colonne `lmstudio_id` de `prompt/benchmark_config.csv`. Le script charge et décharge lui-même les modèles, un à la fois.
4. Vérifie que dbt trouve sa configuration :

```powershell
dbt debug
```

dbt lit `profiles.yml` à la racine, et ses sources lisent `silver/...` en chemin relatif : c'est pour ça qu'il faut être à la racine.

### 4.4 Étape 3 : lancer le pipeline

```powershell
python src/main.py
```

`main.py` affiche d'abord les paramètres utilisés, puis enchaîne 4 étapes. **Si l'une échoue, les suivantes ne sont pas lancées.**

| Étape | Ce qu'elle fait | Ce que tu vois dans le terminal | Durée indicative |
|---|---|---|---|
| 1. Collecte | Interroge l'API OpenTDB et **écrase** `bronze/questions_raw.csv` | `50 questions récupérées (lot de 50)`… puis `N questions enregistrées` | ~10 min pour toutes les questions |
| 2. Nettoyage | Contrôle, nettoie et déduplique, puis écrit `silver/questions_clean.parquet` | Les contrôles, un par ligne, en `OK` (un seul `KO` arrête tout) | quelques secondes |
| 3. Réponses des IA | Pose chaque question à chaque modèle et écrit `silver/ai_responses/part_*.parquet` | `Modèle prêt`, l'avancement toutes les 50 questions, puis un tableau `BILAN` | ~45 min pour les 16 exécutions (sur GPU) |
| 4. dbt build | Construit les 13 modèles : staging → intermediate → marts | `13 of 13 OK`, puis `Completed successfully` | quelques secondes |

Exemple de fin de l'étape 3, puis de l'étape 4, sur un test avec 20 questions :

```
BILAN
               run_id   statut  nouvelles bonnes réponses (provisoire) format valide   durée
gemma3_1b__v1_letters terminée         20                        10.0%        100.0% 0.2 min
...
Done. PASS=13 WARN=0 ERROR=0 SKIP=0 NO-OP=0 REUSED=0 TOTAL=13

Pipeline terminé en 1.3 min.
```

L'étape 3 est **reprenable** : si elle est interrompue (Ctrl+C, LM Studio coupé), relance simplement `main.py`. Les questions déjà traitées sont sautées.

### 4.5 Paramètres du lancement

Les paramètres se règlent en haut de `src/main.py`, ou en ligne de commande, qui est prioritaire.

| Option | Variable dans `main.py` | Défaut | Rôle |
|---|---|---|---|
| `--n-questions-api` | `N_QUESTIONS_API` | toutes | nombre de questions à récolter |
| `--run-orders` | `RUN_ORDERS` | toutes | lignes de `benchmark_config.csv` à exécuter, ex. `1 2 3` |
| `--n-questions-ia` | `N_QUESTIONS_IA` | toutes | questions posées par exécution |
| `--batch-size` | `BATCH_SIZE` | 500 | questions par fichier Parquet |
| `--max-erreurs` | `MAX_ERREURS` | 5 | erreurs consécutives avant d'abandonner une exécution |

Dans le fichier, `RUN_ORDERS` doit être une **liste**, par exemple `[1]` et non `1`.

Exemple de test rapide, environ 1 minute (1 modèle, 20 questions) :

```powershell
python src/main.py --n-questions-api 200 --run-orders 1 --n-questions-ia 20 --batch-size 20
```

⚠️ Ce test écrase `bronze/` et `silver/questions_clean.parquet`. Lance-le plutôt dans une copie du projet, et vide `silver/ai_responses/` dans cette copie, sinon les questions déjà traitées sont sautées.

### 4.6 Étape 4 : explorer les résultats dans Streamlit

**Après `main.py`**, le dashboard se lance tout seul. Le terminal affiche :

```
====================================================================================================
Dashboard Streamlit : http://localhost:8501
Ctrl+C pour arrêter l'app.
====================================================================================================
```

Le navigateur s'ouvre en général tout seul ; sinon, ouvre le lien affiché. Si le port 8501 est déjà pris, le suivant libre est utilisé (8502, 8503…), et c'est ce lien qui est affiché.

**Sans relancer le pipeline**, par exemple juste après un clone :

```powershell
dbt build                                  # construit warehouse/ à partir des Parquet versionnés
streamlit run app/streamlit_app.py         # ouvre le dashboard
```

**Dans le dashboard :**

1. La **page d'accueil** affiche le classement général. Une phrase de synthèse résume le résultat : meilleur modèle, et si son écart avec le 2e est significatif.
2. La **barre latérale** donne accès aux 8 pages d'analyse (Modèles, Formats de prompt, Température, Catégories, Difficulté, Biais de position, Questions pièges, Méthodologie) et aux filtres de la page : prompt, modèles, etc.
3. **Survole un graphique** pour lire les valeurs exactes, l'intervalle de confiance et l'effectif `n`. Sous chaque graphique, une phrase explique comment le lire.
4. Après un nouveau `dbt build`, clique sur **« Recharger les données »** dans la barre latérale pour voir les nouveaux résultats sans redémarrer l'app.

Pour arrêter le dashboard : **Ctrl+C** dans le terminal.

---

## 5. Modèles dbt

Configuration (`dbt_project.yml`) : les modèles sont dans `src/models`. Le staging est matérialisé en **vues**, l'intermédiaire et les marts en **tables**. Les schémas `silver` et `gold` vivent dans `warehouse/trivial_questions.duckdb`.

```
sources (Parquet)           staging (vues)        intermediate (tables)             marts (tables, gold)
questions_clean ──────────► stg_questions ──┬───► int_answer_options
                                            │
                                            └─────────────┐
ai_responses ─────────────► stg_ai_responses ───► int_ai_responses_scored ──► int_responses_enriched ──► 8 mart_*
```

| Couche | Modèle | Schéma / matérialisation | Lit | Grain (1 ligne =) | Ce qu'il fait | Pourquoi |
|---|---|---|---|---|---|---|
| Source | `questions_clean` | fichier Parquet | `silver/questions_clean.parquet` | 1 question (5 296) | Déclare le fichier produit par `clean_questions.py` | Le chemin est écrit à un seul endroit, et la source apparaît dans le graphe dbt |
| Source | `ai_responses` | fichiers Parquet | `silver/ai_responses/*.parquet` | 1 réponse (84 736) | Déclare tous les fichiers `part_*` produits par `ai_all.py` | Même raison |
| Staging | `stg_questions` | silver / view | source `questions_clean` | 1 question (5 296) | Renomme (`type` → `question_type`, `question` → `question_text`) et convertit les types (TINYINT) | Les noms sont fixés une seule fois. Aucune logique : une ligne entre, une ligne sort |
| Staging | `stg_ai_responses` | silver / view | source `ai_responses` | 1 réponse (84 736) | Renomme avec préfixe et unité (`model_publisher`, `response_time_s`…), convertit les types et transforme `created_at` en timestamp | Noms explicites. Les attributs de la question ne sont pas repris : ils viennent de `stg_questions`, seule source de vérité |
| Intermediate | `int_ai_responses_scored` | silver / table | `stg_ai_responses` | 1 réponse (84 736) | Note la réponse : nettoie la réponse brute (`<think>`, « Answer: », espaces), trouve l'option choisie et la bonne option, puis calcule `ai_answer`, `is_valid_format`, `ai_correct`, `answer_status` et `is_truncated` | Cœur du projet. La notation est en SQL et versionnée. On peut changer la règle sans reposer les questions aux modèles, et il y a 0 écart avec la version Python |
| Intermediate | `int_responses_enriched` | silver / table | `int_ai_responses_scored` + `stg_questions` | 1 réponse (84 736) | Jointure sur `question_id` : ajoute catégorie, difficulté et `nb_options`, et calcule `random_baseline` (0,5 ou 0,25) | La jointure est faite une seule fois pour les 8 marts. `random_baseline` permet de comparer au hasard |
| Intermediate | `int_answer_options` | silver / table | `stg_questions` | 1 option de réponse (19 606) | Assemble la bonne réponse et chaque mauvaise réponse (UNNEST) avec `is_correct` | Table de référence des options, au format long |
| Mart | `mart_leaderboard` | gold / table | `int_responses_enriched` | 1 modèle × 1 prompt (16) | Classement général : accuracy et intervalle de confiance, rang, `chance_corrected_score`, format valide, temps, `correct_per_minute` | Qui gagne, et avec quel prompt ? |
| Mart | `mart_model_profile` | gold / table | idem, T = 0 | 1 modèle (4) | Profil global : accuracy, `size_class`, meilleur et pire prompt, `prompt_spread` | La taille compte-t-elle ? Quelle sensibilité au prompt ? |
| Mart | `mart_prompt_format` | gold / table | idem, T = 0 | 1 modèle × 1 format (12) | Score et format valide par style, écarts par rapport au format lettres | Lettres, chiffres ou texte : le format change-t-il le score ? |
| Mart | `mart_temperature_effect` | gold / table | idem, prompts `v1_letters` et `v4_letters_hot` | 1 modèle × 1 difficulté, plus une ligne « all » (16) | Compare chaque question à T = 0 et à T = 1 : `accuracy_delta`, `answer_stability`, bascules juste → faux et faux → juste | La température dégrade-t-elle les réponses ? |
| Mart | `mart_perf_by_category` | gold / table | `int_responses_enriched` | 1 modèle × 1 prompt × 1 catégorie (384) | Accuracy et intervalle, écart à la moyenne du modèle, rang et meilleur modèle par catégorie | Quels modèles sont forts dans quels domaines ? |
| Mart | `mart_perf_by_difficulty` | gold / table | idem | 1 modèle × 1 prompt × 1 difficulté × 1 type (96) | Accuracy et intervalle, `random_baseline`, format valide | Le score baisse-t-il avec la difficulté ? |
| Mart | `mart_position_bias` | gold / table | idem | 1 modèle × 1 prompt × 1 type × 1 position (96) | Part des réponses choisies à chaque position, comparée à la part attendue (`position_bias`) | Le modèle répond-il « A » ou « True » plus souvent qu'il ne devrait ? |
| Mart | `mart_question_insights` | gold / table | idem, T = 0 | 1 question (5 296) | Taux de réussite tous modèles confondus, difficulté ressentie par les IA (`ai_difficulty`), réponse majoritaire, mauvaise réponse la plus choisie, `is_all_wrong` / `is_all_correct` / `is_common_trap` | Quelles questions piègent tous les modèles ? La difficulté OpenTDB correspond-elle à celle ressentie par les IA ? |

Le jeu contient 24 catégories, regroupées en 12 groupes. Il compte 4 507 QCM et 789 Vrai/Faux. Par difficulté : 1 767 easy, 2 424 medium et 1 105 hard.

---

## 6. Macros dbt

| Macro | Utilisée dans | Ce qu'elle fait | Pourquoi |
|---|---|---|---|
| `generate_schema_name` | tous les modèles | Écrit dans `silver` ou `gold` au lieu de `main_silver` | Remplace la règle par défaut de dbt, qui colle le schéma cible devant le nom |
| `strip_whitespace` | `int_ai_responses_scored` | Retire espaces et retours à la ligne en début et en fin (expression régulière) | Le `TRIM` de DuckDB ne retire que les espaces, ce qui causait 30 écarts avec Python |
| `normalize_answer` | `int_ai_responses_scored` | Retire guillemets, `*` et ponctuation finale, met en minuscules et réduit les espaces multiples | Comparer une réponse en texte libre (prompt v3) aux options sans être piégé par la mise en forme |
| `wilson_low` / `wilson_high` | marts | Bornes basse et haute de l'intervalle de confiance de Wilson à 95 % | Savoir si un écart de score est réel ou dû au hasard, surtout sur les petits groupes |

---

## 7. Dashboard Streamlit

Lancement : `streamlit run app/streamlit_app.py`. Le dashboard s'ouvre aussi automatiquement à la fin de `src/main.py`.

| Page | Question posée | Table gold |
|---|---|---|
| Accueil | Quel modèle, avec quel prompt, répond le mieux ? | `mart_leaderboard` |
| Modèles | Un modèle plus gros, ou d'un autre pays, fait-il mieux ? À quel coût en temps ? | `mart_model_profile` |
| Formats de prompt | Lettre, chiffre ou texte : le format change-t-il le résultat ? | `mart_prompt_format` |
| Température | L'aléatoire (T=1) fait-il perdre en précision et en régularité ? | `mart_temperature_effect` |
| Catégories | Chaque modèle a-t-il des thèmes forts et faibles ? | `mart_perf_by_category` |
| Difficulté | Comment la performance évolue-t-elle avec la difficulté, et par rapport au hasard ? | `mart_perf_by_difficulty` |
| Biais de position | Les modèles préfèrent-ils certaines options (A, True) ? | `mart_position_bias` |
| Questions pièges | Quelles questions font tomber tous les modèles ? La difficulté annoncée est-elle réaliste ? | `mart_question_insights` |
| Méthodologie | Pipeline, protocole, règle de correction, définitions et limites | `mart_leaderboard`, `mart_question_insights` (volumes) |

Chaque page commence par une synthèse calculée à partir des données. Chaque graphique est suivi d'une phrase qui explique comment le lire. Les précisions sont toujours affichées avec leur intervalle de confiance et le niveau du hasard.

- **Lecture seule** : l'app ouvre et referme une connexion DuckDB à chaque requête. `dbt build` peut ainsi tourner pendant que le dashboard est ouvert. Le bouton « Recharger les données » affiche les nouveaux résultats.
- **Aucun calcul métier dans l'app** : tous les indicateurs viennent des marts. L'app se limite à filtrer, à faire des pivots d'affichage et à regrouper les catégories par famille (somme des bonnes réponses / somme des questions).
- **Couleur fixe par modèle** sur toutes les pages (palette adaptée aux daltoniens).
- Le cahier des charges complet se trouve dans [`docs/STREAMLIT_SPEC.md`](docs/STREAMLIT_SPEC.md).

---

## 8. Limites

- **Contamination possible** : les questions OpenTDB sont publiques et ont pu servir à l'entraînement des modèles.
- **Questions en anglais** uniquement.
- **Un seul tirage à T = 1** : l'effet de la température est mesuré sur une seule exécution par modèle.
- **Les temps de réponse dépendent de la machine** (GPU, quantification choisie dans LM Studio). Ils ne sont comparables qu'entre modèles exécutés sur la même machine.
- **Petits modèles uniquement** (1 à 8 B) : les conclusions ne s'étendent pas aux grands modèles.
