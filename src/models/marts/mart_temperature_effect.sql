WITH letters AS (
    SELECT * FROM {{ ref('int_responses_enriched') }}
    WHERE label_style = 'letters'
),

cold AS (
    SELECT * FROM letters WHERE temperature = 0
),

hot AS (
    SELECT * FROM letters WHERE temperature > 0
),

paired AS (
    SELECT
        cold.model_key,
        cold.model_name,
        cold.model_params_b,
        cold.difficulty,
        cold.difficulty_level,
        cold.question_id,
        cold.temperature AS temperature_cold,
        hot.temperature AS temperature_hot,
        cold.ai_correct AS correct_cold,
        hot.ai_correct AS correct_hot,
        cold.is_valid_format AS valid_cold,
        hot.is_valid_format AS valid_hot,
        cold.ai_position IS NOT DISTINCT FROM hot.ai_position AS same_answer
    FROM cold
    INNER JOIN hot
        ON cold.model_key = hot.model_key
        AND cold.question_id = hot.question_id
)

SELECT
    model_key,
    model_name,
    model_params_b,
    COALESCE(difficulty, 'all') AS difficulty,
    COALESCE(difficulty_level, 0) AS difficulty_level,
    ANY_VALUE(temperature_cold) AS temperature_cold,
    ANY_VALUE(temperature_hot) AS temperature_hot,
    COUNT(*) AS n_questions,
    ROUND(AVG(correct_cold::INT), 4) AS accuracy_cold,
    ROUND(AVG(correct_hot::INT), 4) AS accuracy_hot,
    ROUND(AVG(correct_hot::INT) - AVG(correct_cold::INT), 4) AS accuracy_delta,
    ROUND(AVG(valid_cold::INT), 4) AS valid_format_rate_cold,
    ROUND(AVG(valid_hot::INT), 4) AS valid_format_rate_hot,
    ROUND(AVG(same_answer::INT), 4) AS answer_stability,
    ROUND(AVG((correct_cold AND NOT correct_hot)::INT), 4) AS rate_correct_to_wrong,
    ROUND(AVG((NOT correct_cold AND correct_hot)::INT), 4) AS rate_wrong_to_correct
FROM paired
GROUP BY GROUPING SETS (
    (model_key, model_name, model_params_b, difficulty, difficulty_level),
    (model_key, model_name, model_params_b)
)
