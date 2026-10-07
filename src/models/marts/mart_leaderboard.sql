WITH responses AS (
    SELECT * FROM {{ ref('int_responses_enriched') }}
),

aggregated AS (
    SELECT
        model_key,
        model_name,
        model_publisher,
        model_country,
        model_params_b,
        prompt_version,
        label_style,
        temperature,
        COUNT(*) AS n_questions,
        COUNT(*) FILTER (WHERE ai_correct) AS n_correct,
        COUNT(*) FILTER (WHERE is_valid_format) AS n_valid_format,
        COUNT(*) FILTER (WHERE is_truncated) AS n_truncated,
        AVG(random_baseline) AS random_baseline,
        AVG(response_time_s) AS avg_response_time_s,
        QUANTILE_CONT(response_time_s, 0.95) AS p95_response_time_s,
        SUM(response_time_s) AS total_response_time_s,
        AVG(completion_tokens) AS avg_completion_tokens
    FROM responses
    GROUP BY ALL
),

metrics AS (
    SELECT
        *,
        n_correct::DOUBLE / n_questions AS accuracy,
        {{ wilson_low('n_correct', 'n_questions') }} AS accuracy_ci_low,
        {{ wilson_high('n_correct', 'n_questions') }} AS accuracy_ci_high,
        n_valid_format::DOUBLE / n_questions AS valid_format_rate,
        n_correct::DOUBLE / NULLIF(n_valid_format, 0) AS accuracy_when_valid,
        n_truncated::DOUBLE / n_questions AS truncated_rate,
        n_correct / NULLIF(total_response_time_s / 60.0, 0) AS correct_per_minute
    FROM aggregated
)

SELECT
    model_key,
    model_name,
    model_publisher,
    model_country,
    model_params_b,
    prompt_version,
    label_style,
    temperature,
    temperature > 0 AS is_temperature_variant,
    n_questions,
    n_correct,
    ROUND(accuracy, 4) AS accuracy,
    ROUND(accuracy_ci_low, 4) AS accuracy_ci_low,
    ROUND(accuracy_ci_high, 4) AS accuracy_ci_high,
    ROUND(random_baseline, 4) AS random_baseline,
    ROUND((accuracy - random_baseline) / (1 - random_baseline), 4) AS chance_corrected_score,
    ROUND(valid_format_rate, 4) AS valid_format_rate,
    ROUND(accuracy_when_valid, 4) AS accuracy_when_valid,
    ROUND(truncated_rate, 4) AS truncated_rate,
    ROUND(avg_response_time_s, 4) AS avg_response_time_s,
    ROUND(p95_response_time_s, 4) AS p95_response_time_s,
    ROUND(avg_completion_tokens, 2) AS avg_completion_tokens,
    ROUND(correct_per_minute, 1) AS correct_per_minute,
    RANK() OVER (ORDER BY accuracy DESC) AS accuracy_rank
FROM metrics
