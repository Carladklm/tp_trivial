# Cahier des charges — Dashboard Streamlit du benchmark Trivial Pursuit

Ce document décrit l'application Streamlit à développer. Il est destiné à un développeur (ou à Claude Code) qui n'a pas suivi la construction du projet : tout ce qui est nécessaire est ici. Les noms de tables et de colonnes sont exacts.

---

## 0. Contexte

**Projet** : benchmark de petits modèles de langage (LLM) exécutés en local avec LM Studio, sur des questions de culture générale issues de l'API Open Trivia DB (OpenTDB).

**Pipeline existant** (architecture médaillon, déjà en place, ne pas modifier) :

- **Bronze** : `bronze/questions_raw.csv`, questions brutes de l'API.
- **Silver** :
  - `silver/questions_clean.parquet` : 5 296 questions nettoyées ;
  - `silver/ai_responses/part_*.parquet` : réponses brutes des modèles ;
  - vues et tables dbt `silver.stg_*` et `silver.int_*`.
- **Gold** : 8 tables dbt `gold.mart_*`, une par question métier. **L'application lit uniquement ces tables.**

**Plan du benchmark** : 4 modèles × 4 prompts × 5 296 questions, soit 84 736 réponses. Chaque question est posée en QCM (4 options) ou en vrai/faux (2 options).

**Rôle de l'application** : présenter les résultats du benchmark de façon interactive, pour une soutenance de 10 minutes et pour l'exploration. **L'application ne calcule aucun indicateur métier** : tous les calculs sont faits dans dbt. Streamlit se limite à lire, filtrer, mettre en forme, et à faire de légers pivots pour l'affichage.

---

## 1. Contraintes techniques

### 1.1 Environnement
- Python, Streamlit **1.46 ou plus** (utiliser `width="stretch"` et non `use_container_width`, qui est obsolète), DuckDB, pandas, Altair (fourni avec Streamlit).
- **Ne pas ajouter de dépendance lourde** (pas de Plotly, ni de Dash). Altair suffit pour tous les graphiques. Si une dépendance est ajoutée, l'inscrire dans `requirements.txt`.
- Langue de l'interface : **français**.

### 1.2 Base de données
- Fichier : `warehouse/trivial_questions.duckdb`, chemin relatif à la racine du projet. Le construire avec `ROOT = Path(__file__).resolve().parents[n]` selon la profondeur du fichier, **jamais** à partir du dossier courant.
- Schéma à lire : **`gold`** uniquement.
- **Connexion en lecture seule, ouverte et refermée à chaque requête** :
  ```python
  @st.cache_data
  def query(sql: str) -> pd.DataFrame:
      with duckdb.connect(str(DB_PATH), read_only=True) as con:
          return con.sql(sql).df()
  ```
  C'est **obligatoire** : DuckDB verrouille le fichier tant qu'une connexion est ouverte, et `dbt build` doit pouvoir tourner pendant que l'application est ouverte. Ne pas garder de connexion globale ni utiliser `st.cache_resource` pour la connexion.
- Si le fichier n'existe pas : afficher `st.error("Base introuvable … lance dbt build")` puis `st.stop()`.
- Si une table `gold.mart_*` manque : afficher un message clair sur la page concernée, sans faire planter l'application.
- Un bouton **« Recharger les données »** dans la barre latérale vide le cache (`st.cache_data.clear()` puis `st.rerun()`), pour voir les résultats d'un nouveau `dbt build`.

### 1.3 Structure des fichiers

```
app/
├── streamlit_app.py            ← page d'accueil (existe déjà, peut être réécrite)
├── lib/
│   ├── __init__.py
│   ├── data.py                 ← DB_PATH, query(), chargement de chaque mart
│   ├── style.py                ← couleurs, libellés, formats (voir § 3)
│   └── charts.py               ← fonctions Altair réutilisables
└── pages/
    ├── 1_Modeles.py
    ├── 2_Formats_de_prompt.py
    ├── 3_Temperature.py
    ├── 4_Categories.py
    ├── 5_Difficulte.py
    ├── 6_Biais_de_position.py
    ├── 7_Questions_pieges.py
    └── 8_Methodologie.py
```

Lancement depuis la racine du projet : `streamlit run app/streamlit_app.py`. Pour que `from lib import ...` fonctionne depuis les pages, ajouter le dossier `app/` au `sys.path` en tête de chaque page, ou utiliser une importation relative robuste.

---

## 2. Référentiel des données

### 2.1 Modèles (4)

| `model_key` | `model_name` | Éditeur | Pays | Taille (`model_params_b`, en milliards) |
|---|---|---|---|---|
| `gemma3_1b` | Gemma 3 1B | Google | États-Unis | 1.0 |
| `lfm2_1_2b` | LFM2 1.2B | Liquid AI | États-Unis | 1.2 |
| `qwen2_5_3b` | Qwen2.5 3B Instruct | Alibaba | Chine | 3.0 |
| `ministral3_8b` | Ministral 3 8B Instruct | Mistral AI | France | 8.0 |

Le code ne doit **pas** coder ces valeurs en dur pour filtrer. Il les lit dans les tables. Le tableau ne sert qu'à fixer les couleurs et l'ordre d'affichage (§ 3), avec une couleur de repli pour un modèle inconnu.

### 2.2 Prompts (4)

| `prompt_version` | `label_style` | Température | Libellé à afficher | Réponse attendue |
|---|---|---|---|---|
| `v1_letters` | `letters` | 0 | Lettres (A–D) | `A`, `B`, `C` ou `D` (`A`/`B` pour un vrai/faux) |
| `v2_numbers` | `numbers` | 0 | Chiffres (1–4) | `1` à `4` (`1`/`2` pour un vrai/faux) |
| `v3_text` | `text` | 0 | Texte de la réponse | le texte exact de l'option (`True`/`False`) |
| `v4_letters_hot` | `letters` | 1.0 | Lettres, température 1 | comme `v1_letters` |

`v4_letters_hot` est **identique** à `v1_letters`, à la température près. Elle sert **uniquement** à l'analyse de la température.

### 2.3 Autres dimensions
- `difficulty` : `easy`, `medium`, `hard`. Trier avec `difficulty_level` (1, 2, 3). Libellés affichés : Facile, Moyen, Difficile.
- `question_type` : `multiple` (QCM à 4 options, score au hasard 25 %) et `boolean` (vrai/faux, score au hasard 50 %). Libellés : QCM, Vrai/Faux.
- `category_group` : 12 familles (Entertainment, Science, History, Geography…). `category_name` : 24 catégories (Video Games, Film, Music, Computers…). Les catégories sans sous-catégorie ont la même valeur dans les deux colonnes (ex. History / History).

### 2.4 Tables Gold : grain et colonnes

Tous les taux (`accuracy`, `*_rate`, `share_*`) sont des **fractions entre 0 et 1**, à afficher en pourcentage avec une décimale.

**`gold.mart_leaderboard`** : 1 ligne = 1 modèle × 1 prompt (16 lignes).
`model_key, model_name, model_publisher, model_country, model_params_b, prompt_version, label_style, temperature, is_temperature_variant, n_questions, n_correct, accuracy, accuracy_ci_low, accuracy_ci_high, random_baseline, chance_corrected_score, valid_format_rate, accuracy_when_valid, truncated_rate, avg_response_time_s, p95_response_time_s, avg_completion_tokens, correct_per_minute, accuracy_rank`

**`gold.mart_model_profile`** : 1 ligne = 1 modèle, calculée sur les prompts à température 0 uniquement (4 lignes).
`model_key, model_name, model_publisher, model_country, model_params_b, size_class, n_responses, accuracy, accuracy_ci_low, accuracy_ci_high, chance_corrected_score, valid_format_rate, accuracy_when_valid, best_prompt, best_prompt_accuracy, worst_prompt, worst_prompt_accuracy, prompt_spread, avg_response_time_s, correct_per_minute, accuracy_rank`

**`gold.mart_prompt_format`** : 1 ligne = 1 modèle × 1 format, température 0 uniquement (12 lignes).
`model_key, model_name, model_params_b, prompt_version, label_style, n_questions, accuracy, valid_format_rate, accuracy_when_valid, accuracy_delta_vs_letters, valid_format_delta_vs_letters, truncated_rate, avg_completion_tokens, avg_response_time_s, rank_within_model`

**`gold.mart_temperature_effect`** : 1 ligne = 1 modèle × 1 difficulté, plus une ligne `difficulty = 'all'` par modèle (16 lignes). On compare le prompt lettres à T=0 et à T=1, **sur les mêmes questions**.
`model_key, model_name, model_params_b, difficulty, difficulty_level, temperature_cold, temperature_hot, n_questions, accuracy_cold, accuracy_hot, accuracy_delta, valid_format_rate_cold, valid_format_rate_hot, answer_stability, rate_correct_to_wrong, rate_wrong_to_correct`
(`difficulty_level` vaut 0 pour la ligne `all`.)

**`gold.mart_perf_by_category`** : 1 ligne = 1 modèle × 1 prompt × 1 catégorie (environ 384 lignes).
`model_key, model_name, model_country, prompt_version, temperature, category_group, category_name, n_questions, n_correct, accuracy, accuracy_ci_low, accuracy_ci_high, model_accuracy, delta_vs_model_average, category_accuracy_all_models, rank_in_category, is_best_in_category`

**`gold.mart_perf_by_difficulty`** : 1 ligne = 1 modèle × 1 prompt × 1 difficulté × 1 type de question (96 lignes).
`model_key, model_name, model_params_b, prompt_version, temperature, difficulty, difficulty_level, question_type, n_questions, n_correct, accuracy, accuracy_ci_low, accuracy_ci_high, random_baseline, chance_corrected_score, valid_format_rate`

**`gold.mart_position_bias`** : 1 ligne = 1 modèle × 1 prompt × 1 type de question × 1 position (96 lignes).
`model_key, model_name, prompt_version, label_style, temperature, question_type, position, position_label, n_chosen, n_correct_here, share_chosen, share_expected, position_bias, accuracy_when_correct_here`
(`position_label` vaut `A`–`D` pour les QCM, `True`/`False` pour les vrai/faux.)

**`gold.mart_question_insights`** : 1 ligne = 1 question, calculée sur tous les modèles et les prompts à T=0 (5 296 lignes, soit 12 réponses par question).
`question_id, question_text, question_type, difficulty, difficulty_level, category_group, category_name, correct_answer, n_models, n_answers, n_correct, success_rate, ai_difficulty, ai_difficulty_level, n_models_correct_once, majority_answer, majority_votes, is_majority_correct, top_wrong_answer, top_wrong_votes, is_all_wrong, is_all_correct, is_common_trap`

### 2.5 Définitions des indicateurs (à reprendre dans les infobulles et la page Méthodologie)

| Indicateur | Définition |
|---|---|
| `accuracy` (Précision) | Part des questions répondues correctement. **Une réponse au format invalide compte comme fausse.** |
| `accuracy_ci_low` / `_high` | Intervalle de confiance à 95 % de la précision (méthode de Wilson). |
| `valid_format_rate` (Format valide) | Part des réponses qui respectent le format demandé (« C » et non « The answer is C »). |
| `accuracy_when_valid` (Précision si format valide) | Précision parmi les seules réponses bien formatées : mesure la **connaissance**, sans la discipline de format. |
| `random_baseline` (Hasard) | Score d'un modèle qui répondrait au hasard : 0,25 pour un QCM, 0,5 pour un vrai/faux (moyenne pondérée sur un mélange). |
| `chance_corrected_score` (Score corrigé du hasard) | (précision − hasard) / (1 − hasard). 0 = niveau du hasard, 1 = parfait, négatif = pire que le hasard. Permet de comparer QCM et vrai/faux. |
| `correct_per_minute` | Bonnes réponses produites par minute de calcul : efficacité. |
| `prompt_spread` | Écart de précision entre le meilleur et le pire prompt d'un modèle : plus il est faible, plus le modèle est **robuste** au format. |
| `answer_stability` | Part des questions où le modèle donne la même réponse à T=0 et à T=1. |
| `position_bias` | Part des réponses données sur une position, moins la part des bonnes réponses réellement sur cette position. > 0 : le modèle sur-choisit cette option. |
| `ai_difficulty` | Difficulté « vécue » par les modèles : `easy` si au moins 2/3 des 12 réponses sont justes, `hard` si moins d'1/3, sinon `medium`. |
| `is_common_trap` | Aucun modèle n'a juste **et** au moins la moitié des réponses désignent la **même** mauvaise option (idée reçue, ou possible erreur du dataset). |
| `is_majority_correct` | La réponse la plus donnée par l'ensemble des modèles est la bonne (« vote à la majorité »). |

---

## 3. Règles de présentation (communes à toutes les pages)

### 3.1 Règles d'analyse à respecter
1. **Comparer les modèles à température 0.** Le filtre de prompt par défaut est `v1_letters`. Ne jamais faire la moyenne de `v4_letters_hot` avec les autres prompts.
2. **Toujours montrer l'incertitude.** Partout où une précision est affichée en barre ou en point, ajouter l'intervalle de confiance (`accuracy_ci_low` / `accuracy_ci_high`) sous forme de trait d'erreur, quand la colonne existe.
3. **Toujours montrer le niveau du hasard** (`random_baseline`) en ligne pointillée sur les graphiques de précision.
4. **Petits effectifs** : si `n_questions < 30`, griser ou rendre semi-transparent l'élément, et l'indiquer dans l'infobulle (« Échantillon faible : n = … »).
5. **Pays, éditeur et taille sont confondus avec le modèle.** Il n'y a qu'un modèle par pays, sauf les États-Unis qui en ont deux. Toute vue « par pays » ou « par taille » doit afficher un encadré `st.info` rappelant qu'avec 4 modèles on **observe**, on ne **généralise** pas, et que le pays ne peut pas être séparé de la taille.
6. Les phrases de synthèse générées automatiquement (ex. « Le meilleur modèle est … ») doivent être **calculées à partir des données affichées**, jamais écrites en dur.

### 3.2 Couleurs et ordre
- **Une couleur fixe par modèle**, identique sur toutes les pages, adaptée aux daltoniens (palette Okabe-Ito) :
  - `gemma3_1b` : `#0072B2` (bleu)
  - `lfm2_1_2b` : `#E69F00` (orange)
  - `qwen2_5_3b` : `#009E73` (vert)
  - `ministral3_8b` : `#CC79A7` (violet)
  - modèle inconnu : couleur de repli grise `#999999`
- **Ordre d'affichage des modèles** : par taille croissante (`model_params_b`), sauf dans les classements, triés par précision.
- **Statut des réponses** : Juste `#009E73`, Faux `#D55E00`, Format invalide `#999999`.
- **Cartes de chaleur** : palette séquentielle (`blues`) pour une précision, palette divergente centrée sur 0 (`redblue`) pour un écart.
- Centraliser couleurs, libellés de prompts, libellés de difficulté et formats dans `app/lib/style.py`.

### 3.3 Mise en forme
- Pourcentages avec 1 décimale (`71.1 %`), temps en secondes avec 3 décimales, scores corrigés avec 3 décimales.
- Chaque graphique a un **titre**, des **axes nommés en français**, une **infobulle** avec les valeurs exactes et `n`, et une **légende de lecture** d'une phrase sous le graphique (`st.caption`), qui dit comment lire le graphique.
- `layout="wide"`. En haut de chaque page : titre, puis une phrase qui énonce la **question métier** de la page.
- Tableaux avec `st.dataframe(..., hide_index=True)` et `column_config` : libellés français, `ProgressColumn` pour les précisions, format pourcentage.
- Pas de surcharge : 3 à 4 graphiques par page au maximum. Pas d'émojis dans les titres.

### 3.4 Barre latérale
- Bouton « Recharger les données ».
- Filtres propres à chaque page (décrits ci-dessous), avec des valeurs par défaut qui affichent immédiatement quelque chose d'utile.

---

## 4. Pages

### Page 0 — Accueil : classement général (`streamlit_app.py`)
**Question métier** : quel modèle, avec quel prompt, répond le mieux ?
**Source** : `gold.mart_leaderboard`.
**Filtres** : prompt (selectbox, défaut `v1_letters`, avec les libellés du § 2.2) ; modèles (multiselect, tous par défaut).

**Contenu :**
1. **4 indicateurs** (`st.metric`) : meilleur modèle (pour le prompt choisi), sa précision, son écart avec le second modèle (en points), nombre de questions par modèle.
2. **Graphique principal** : barres horizontales de la précision par modèle, triées décroissantes, avec traits d'intervalle de confiance et ligne pointillée du hasard. Infobulle : précision, intervalle, format valide, `n`.
3. **Graphique « Juste / Faux / Format invalide »** : barre empilée à 100 % par modèle, pour le prompt choisi. Les trois parts se calculent à l'affichage : juste = `accuracy`, faux = `valid_format_rate − accuracy`, invalide = `1 − valid_format_rate`. Il montre d'un coup d'œil si un modèle perd des points par ignorance ou par non-respect du format.
4. **Carte de chaleur récapitulative** : modèles (lignes) × 4 prompts (colonnes), cellule = précision en pourcentage. C'est la vue d'ensemble des 16 exécutions.
5. **Tableau détaillé** : toutes les colonnes utiles de `mart_leaderboard` pour le prompt choisi.

**Synthèse automatique** (texte, une ou deux phrases) : meilleur modèle, sa précision, et si les intervalles de confiance du 1er et du 2e se chevauchent (« écart non significatif ») ou non.

### Page 1 — Modèles : taille, éditeur, pays, efficacité
**Question métier** : un modèle plus gros, ou d'un autre pays, fait-il mieux ? À quel coût en temps ?
**Source** : `gold.mart_model_profile` (et `mart_leaderboard` pour le graphique de vitesse par prompt si utile).

**Contenu :**
1. **Encadré `st.info`** sur la confusion pays / taille / modèle (règle 3.1-5).
2. **Taille contre précision** : nuage de points, x = `model_params_b` (échelle logarithmique, « Taille du modèle, en milliards de paramètres »), y = `accuracy`, traits verticaux d'intervalle de confiance, étiquette du nom du modèle à côté de chaque point, couleur = modèle, ligne pointillée du hasard.
3. **Compromis précision / vitesse** : nuage de points, x = `avg_response_time_s` (« Temps moyen par question (s) »), y = `accuracy`, taille du point = `model_params_b`, étiquettes. Légende de lecture : « en haut à gauche = rapide et précis ».
4. **Connaissance contre respect du format** : barres groupées par modèle, `accuracy` et `accuracy_when_valid`. L'écart entre les deux barres = points perdus à cause du format.
5. **Robustesse au prompt** : barres de `prompt_spread` par modèle, avec dans l'infobulle `best_prompt` / `worst_prompt` et leurs précisions.
6. **Tableau** : nom, éditeur, pays, taille, `size_class`, précision et intervalle, score corrigé du hasard, format valide, meilleur et pire prompt, temps moyen, bonnes réponses par minute.

### Page 2 — Formats de prompt
**Question métier** : demander la réponse en lettre, en chiffre ou en texte change-t-il le résultat ?
**Source** : `gold.mart_prompt_format`.
**Filtres** : modèles (multiselect).

**Contenu :**
1. **Barres groupées** : x = modèle, couleur = format (3 formats, avec une palette distincte de celle des modèles, ou des facettes par modèle), y = `accuracy`.
2. **Barres groupées du format valide** (`valid_format_rate`), même disposition. C'est souvent là que se trouve l'écart principal.
3. **Graphique en pente (slope chart)** : x = format (Lettres → Chiffres → Texte), y = précision, une ligne par modèle (couleurs des modèles). Il montre si tous les modèles réagissent de la même façon au format.
4. **Tableau des écarts** : `accuracy_delta_vs_letters` et `valid_format_delta_vs_letters` en points, colorés (négatif en rouge, positif en vert), `truncated_rate`, `avg_completion_tokens`.

**Synthèse automatique** : format moyen le plus favorable, et modèle le plus sensible au format (plus grand écart absolu par rapport aux lettres).

### Page 3 — Température
**Question métier** : ajouter de l'aléatoire (T=1) fait-il perdre en précision et en régularité ?
**Source** : `gold.mart_temperature_effect`.
**Filtres** : modèles.

**Contenu :**
1. **Graphique haltère (dumbbell)**, lignes où `difficulty = 'all'` : un modèle par ligne, un point pour `accuracy_cold` (T=0), un point pour `accuracy_hot` (T=1), reliés par un segment. On y voit la perte de chaque modèle.
2. **Barres de `answer_stability`** par modèle (`difficulty = 'all'`), avec la légende : « part des questions où le modèle répond la même chose à T=0 et à T=1 ».
3. **Écart par difficulté** : barres groupées, x = difficulté (Facile, Moyen, Difficile, triées par `difficulty_level`, sans la ligne `all`), couleur = modèle, y = `accuracy_delta`. Hypothèse à vérifier : l'effet est plus fort sur les questions difficiles, où le modèle hésite davantage.
4. **Flux de réponses** : barres divergentes par modèle, `rate_correct_to_wrong` vers la gauche (perdues) et `rate_wrong_to_correct` vers la droite (gagnées par chance).

**Avertissement** à afficher : à T=1, relancer l'exécution donnerait des chiffres légèrement différents.

### Page 4 — Catégories
**Question métier** : chaque modèle a-t-il des thèmes forts et faibles ?
**Source** : `gold.mart_perf_by_category`.
**Filtres** : prompt (défaut `v1_letters`) ; niveau de détail (radio : « Familles (category_group) » / « Catégories (category_name) ») ; mode d'affichage (radio : « Précision » / « Écart à la moyenne du modèle »).

**Contenu :**
1. **Carte de chaleur** : lignes = catégories (triées par `category_accuracy_all_models` décroissante), colonnes = modèles (ordre de taille), couleur = `accuracy` (palette séquentielle) ou `delta_vs_model_average` (palette divergente centrée sur 0) selon le mode, texte de la valeur dans chaque cellule, cellules semi-transparentes si `n_questions < 30`. Infobulle : précision, intervalle, `n`, rang du modèle dans la catégorie.
   - Au niveau « Familles », regrouper les catégories **à l'affichage** en sommant `n_correct` et `n_questions` par `category_group`, puis en recalculant précision = somme(`n_correct`) / somme(`n_questions`). **Ne pas faire la moyenne des précisions.**
2. **Meilleur modèle par catégorie** : tableau ou barres comptant les catégories où chaque modèle est premier (`is_best_in_category`).
3. **Zoom sur un modèle** (selectbox) : barres horizontales de `delta_vs_model_average` par catégorie, triées, avec ses 3 points forts et ses 3 points faibles en évidence.
4. **Encadré d'hypothèse** : « Qwen (modèle chinois) est-il plus faible sur la pop culture occidentale (Film, Music, Television) ? », avec la réponse lue dans les données. Rappeler la règle de confusion 3.1-5.

### Page 5 — Difficulté et type de question
**Question métier** : comment la performance évolue-t-elle avec la difficulté, et par rapport au hasard ?
**Source** : `gold.mart_perf_by_difficulty`.
**Filtres** : prompt (défaut `v1_letters`) ; métrique (radio : « Précision » / « Score corrigé du hasard »).

**Contenu :**
1. **Courbes** : x = difficulté (ordre `difficulty_level`), y = métrique choisie, une ligne par modèle, **facettes par type de question** (QCM, Vrai/Faux), bandes ou traits d'intervalle de confiance, ligne pointillée du hasard propre à chaque facette (0,25 et 0,5) quand la métrique est la précision.
2. **Tableau croisé** : modèles × (difficulté, type), cellule = précision.
3. **Légende de lecture** : expliquer pourquoi le score corrigé du hasard est nécessaire pour comparer QCM et vrai/faux.

### Page 6 — Biais de position
**Question métier** : les modèles ont-ils une préférence pour certaines options (A, ou True), indépendamment de la bonne réponse ?
**Source** : `gold.mart_position_bias`.
**Filtres** : prompt (défaut `v1_letters`) ; type de question (radio : QCM / Vrai/Faux).

**Contenu :**
1. **Barres groupées** par modèle (facettes), x = `position_label`, deux barres par position : `share_chosen` (part des réponses du modèle) et `share_expected` (part des bonnes réponses réellement à cette position). Si les deux barres sont égales, il n'y a pas de biais.
2. **Carte de chaleur de `position_bias`** : modèles × positions, palette divergente centrée sur 0, valeur en points dans chaque cellule.
3. **Vrai/Faux** : indicateur par modèle de la part de « True » donnée, comparée à la part réelle de « True » parmi les bonnes réponses.
4. **Synthèse automatique** : le biais le plus fort observé (modèle, position, valeur en points).

**Note** : pour le prompt texte, « position » désigne le rang de l'option dans la liste présentée au modèle.

### Page 7 — Questions pièges et difficulté réelle
**Question métier** : quelles questions font tomber tous les modèles, et la difficulté annoncée par OpenTDB est-elle réaliste ?
**Source** : `gold.mart_question_insights`, et `gold.mart_model_profile` pour comparer avec le meilleur modèle.
**Filtres** : famille de catégorie, difficulté annoncée, type de question (multiselects) ; recherche texte dans `question_text` (`st.text_input`, filtre insensible à la casse).

**Contenu :**
1. **Indicateurs** :
   - part des questions ratées par tous (`is_all_wrong`) ;
   - nombre de pièges communs (`is_common_trap`) ;
   - part des questions réussies par tous (`is_all_correct`) ;
   - **précision du vote à la majorité** (moyenne de `is_majority_correct`), comparée à la **précision du meilleur modèle seul** (maximum de `accuracy` dans `mart_model_profile`), avec l'écart en points. Question posée : « Plusieurs petits modèles ensemble font-ils mieux que le meilleur seul ? »
2. **Difficulté annoncée contre difficulté vécue** : carte de chaleur 3 × 3, lignes = `difficulty` (annoncée), colonnes = `ai_difficulty` (vécue), cellule = nombre de questions et pourcentage de la ligne. La diagonale = accord. Le croisement se calcule dans pandas (`pd.crosstab`), c'est un pivot d'affichage autorisé. Ajouter la part de questions sur la diagonale.
3. **Distribution du taux de réussite** : histogramme de `success_rate` (13 valeurs possibles, de 0/12 à 12/12), couleur par difficulté annoncée.
4. **Tableau des pièges communs** (`is_common_trap = True`), triés par `top_wrong_votes` décroissant : question, catégorie, difficulté, bonne réponse, mauvaise réponse la plus donnée, nombre de votes pour cette mauvaise réponse. Ce sont les meilleurs exemples à montrer en soutenance.
5. **Explorateur** : tableau complet filtrable de toutes les questions, avec `success_rate` en `ProgressColumn`.

### Page 8 — Méthodologie
**Contenu statique** (Markdown), utile en soutenance :
1. **Le pipeline** : Bronze → Silver → Gold, avec les outils (Python, LM Studio, dbt, DuckDB, Streamlit). Un schéma simple (texte ou Graphviz avec `st.graphviz_chart`) : API OpenTDB → CSV bronze → Parquet silver (questions nettoyées, réponses brutes des modèles) → dbt staging → intermediate (correction des réponses) → marts gold → Streamlit.
2. **Le protocole** : 4 modèles, 4 prompts (tableau du § 2.2), mêmes questions pour tous, options mélangées avec une graine (`question_id`), température 0 sauf v4, `max_tokens` = 5 (40 pour le texte).
3. **La règle de correction** : comment une réponse est lue (étiquette seule, « C. Canada » accepté si le texte correspond, raisonnement `<think>` retiré, « The answer is C » = format invalide) ; une réponse illisible compte comme fausse.
4. **Les définitions des indicateurs** : tableau du § 2.5.
5. **Les limites** : 4 modèles seulement (pays confondu avec taille), une seule exécution par configuration, T=1 non reproductible à l'identique, questions OpenTDB en anglais et orientées culture occidentale, petites catégories peu fiables.
6. Les volumes réels lus dans la base : nombre de réponses, de questions, de modèles et de prompts (requête `COUNT` sur `mart_leaderboard` et `mart_question_insights`).

---

## 5. Critères d'acceptation

- `streamlit run app/streamlit_app.py` démarre sans erreur, et les 9 pages s'ouvrent sans exception.
- Toutes les données viennent du schéma `gold`, avec des connexions DuckDB en lecture seule et refermées après chaque requête. `dbt build` fonctionne pendant que l'application est ouverte.
- Chaque page fonctionne quand un filtre est vide (message « Aucune donnée pour cette sélection » au lieu d'une erreur) et quand une catégorie ou un modèle manque (benchmark partiel sur 1 000 questions par exemple).
- Couleurs des modèles identiques sur toutes les pages.
- Les intervalles de confiance et la ligne du hasard apparaissent sur les graphiques de précision.
- Ajouter un test de fumée `tests/test_app.py` avec `streamlit.testing.v1.AppTest` : chaque page se charge sans exception sur la base réelle.
- Code lisible : fonctions courtes, docstrings, aucune requête SQL dupliquée (les chargements sont centralisés dans `lib/data.py`).

## 6. Hors périmètre

- Aucune modification du pipeline (scripts Python, modèles dbt, base DuckDB).
- Aucun calcul d'indicateur métier dans Streamlit au-delà des pivots et regroupements d'affichage explicitement autorisés ci-dessus. Si un indicateur manque, le signaler plutôt que de le calculer dans l'application.
- Pas d'authentification ni de déploiement en ligne.
