WITH responses AS (
    SELECT * FROM {{ ref('int_responses_enriched') }}
    WHERE temperature = 0
),

per_format AS (
    SELECT
        model_key,
        model_name,
        model_params_b,
        prompt_version,
        label_style,
        COUNT(*) AS n_questions,
        AVG(ai_correct::INT) AS accuracy,
        AVG(is_valid_format::INT) AS valid_format_rate,
        AVG(ai_correct::INT) FILTER (WHERE is_valid_format) AS accuracy_when_valid,
        AVG(is_truncated::INT) AS truncated_rate,
        AVG(completion_tokens) AS avg_completion_tokens,
        AVG(response_time_s) AS avg_response_time_s
    FROM responses
    GROUP BY ALL
),

letters_reference AS (
    SELECT
        model_key,
        accuracy AS letters_accuracy,
        valid_format_rate AS letters_valid_format_rate
    FROM per_format
    WHERE label_style = 'letters'
)

SELECT
    per_format.model_key,
    per_format.model_name,
    per_format.model_params_b,
    per_format.prompt_version,
    per_format.label_style,
    per_format.n_questions,
    ROUND(per_format.accuracy, 4) AS accuracy,
    ROUND(per_format.valid_format_rate, 4) AS valid_format_rate,
    ROUND(per_format.accuracy_when_valid, 4) AS accuracy_when_valid,
    ROUND(per_format.accuracy - letters_reference.letters_accuracy, 4) AS accuracy_delta_vs_letters,
    ROUND(per_format.valid_format_rate - letters_reference.letters_valid_format_rate, 4) AS valid_format_delta_vs_letters,
    ROUND(per_format.truncated_rate, 4) AS truncated_rate,
    ROUND(per_format.avg_completion_tokens, 2) AS avg_completion_tokens,
    ROUND(per_format.avg_response_time_s, 4) AS avg_response_time_s,
    RANK() OVER (PARTITION BY per_format.model_key ORDER BY per_format.accuracy DESC) AS rank_within_model
FROM per_format
LEFT JOIN letters_reference
    ON per_format.model_key = letters_reference.model_key
