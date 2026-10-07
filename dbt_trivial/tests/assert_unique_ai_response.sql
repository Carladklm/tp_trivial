-- Échoue s'il existe un doublon question x modèle x prompt
SELECT question_id, model, prompt_version, COUNT(*) AS nb
FROM {{ ref('stg_ai_responses') }}
GROUP BY question_id, model, prompt_version
HAVING COUNT(*) > 1
