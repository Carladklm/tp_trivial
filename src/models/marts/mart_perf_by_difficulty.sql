WITH responses AS (
    SELECT * FROM {{ ref('int_responses_enriched') }}
),

aggregated AS (
    SELECT
        model_key,
        model_name,
        model_params_b,
        prompt_version,
        temperature,
        difficulty,
        difficulty_level,
        question_type,
        COUNT(*) AS n_questions,
        COUNT(*) FILTER (WHERE ai_correct) AS n_correct,
        AVG(is_valid_format::INT) AS valid_format_rate,
        AVG(random_baseline) AS random_baseline
    FROM responses
    GROUP BY ALL
)

SELECT
    model_key,
    model_name,
    model_params_b,
    prompt_version,
    temperature,
    difficulty,
    difficulty_level,
    question_type,
    n_questions,
    n_correct,
    ROUND(n_correct::DOUBLE / n_questions, 4) AS accuracy,
    ROUND({{ wilson_low('n_correct', 'n_questions') }}, 4) AS accuracy_ci_low,
    ROUND({{ wilson_high('n_correct', 'n_questions') }}, 4) AS accuracy_ci_high,
    ROUND(random_baseline, 4) AS random_baseline,
    ROUND((n_correct::DOUBLE / n_questions - random_baseline) / (1 - random_baseline), 4) AS chance_corrected_score,
    ROUND(valid_format_rate, 4) AS valid_format_rate
FROM aggregated
