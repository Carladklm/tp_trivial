-- Échoue si une même question apparaît deux fois dans un même run
SELECT question_id, run_id, COUNT(*) AS nb
FROM {{ ref('stg_ai_responses') }}
GROUP BY question_id, run_id
HAVING COUNT(*) > 1
