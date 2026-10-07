WITH responses AS (
    SELECT * FROM {{ ref('int_responses_enriched') }}
    WHERE temperature = 0
),

per_prompt AS (
    SELECT
        model_key,
        prompt_version,
        AVG(ai_correct::INT) AS accuracy
    FROM responses
    GROUP BY ALL
),

prompt_spread AS (
    SELECT
        model_key,
        ARG_MAX(prompt_version, accuracy) AS best_prompt,
        MAX(accuracy) AS best_prompt_accuracy,
        ARG_MIN(prompt_version, accuracy) AS worst_prompt,
        MIN(accuracy) AS worst_prompt_accuracy,
        MAX(accuracy) - MIN(accuracy) AS prompt_spread
    FROM per_prompt
    GROUP BY model_key
),

per_model AS (
    SELECT
        model_key,
        model_name,
        model_publisher,
        model_country,
        model_params_b,
        COUNT(*) AS n_responses,
        COUNT(*) FILTER (WHERE ai_correct) AS n_correct,
        COUNT(*) FILTER (WHERE is_valid_format) AS n_valid_format,
        AVG(random_baseline) AS random_baseline,
        AVG(response_time_s) AS avg_response_time_s,
        SUM(response_time_s) AS total_response_time_s
    FROM responses
    GROUP BY ALL
)

SELECT
    per_model.model_key,
    per_model.model_name,
    per_model.model_publisher,
    per_model.model_country,
    per_model.model_params_b,
    CASE
        WHEN per_model.model_params_b < 2 THEN 'très petit (< 2B)'
        WHEN per_model.model_params_b < 5 THEN 'petit (2-5B)'
        ELSE 'moyen (5B et plus)'
    END AS size_class,
    per_model.n_responses,
    ROUND(per_model.n_correct::DOUBLE / per_model.n_responses, 4) AS accuracy,
    ROUND({{ wilson_low('per_model.n_correct', 'per_model.n_responses') }}, 4) AS accuracy_ci_low,
    ROUND({{ wilson_high('per_model.n_correct', 'per_model.n_responses') }}, 4) AS accuracy_ci_high,
    ROUND(
        (per_model.n_correct::DOUBLE / per_model.n_responses - per_model.random_baseline)
        / (1 - per_model.random_baseline), 4
    ) AS chance_corrected_score,
    ROUND(per_model.n_valid_format::DOUBLE / per_model.n_responses, 4) AS valid_format_rate,
    ROUND(per_model.n_correct::DOUBLE / NULLIF(per_model.n_valid_format, 0), 4) AS accuracy_when_valid,
    prompt_spread.best_prompt,
    ROUND(prompt_spread.best_prompt_accuracy, 4) AS best_prompt_accuracy,
    prompt_spread.worst_prompt,
    ROUND(prompt_spread.worst_prompt_accuracy, 4) AS worst_prompt_accuracy,
    ROUND(prompt_spread.prompt_spread, 4) AS prompt_spread,
    ROUND(per_model.avg_response_time_s, 4) AS avg_response_time_s,
    ROUND(per_model.n_correct / NULLIF(per_model.total_response_time_s / 60.0, 0), 1) AS correct_per_minute,
    RANK() OVER (ORDER BY per_model.n_correct::DOUBLE / per_model.n_responses DESC) AS accuracy_rank
FROM per_model
INNER JOIN prompt_spread
    ON per_model.model_key = prompt_spread.model_key
