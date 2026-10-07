WITH responses AS (
    SELECT * FROM {{ ref('stg_ai_responses') }}
),

cleaned AS (
    SELECT
        *,
        {{ strip_whitespace(
            "REGEXP_REPLACE(
                REGEXP_REPLACE(
                    REGEXP_REPLACE(raw_response, '<think>.*?</think>', '', 'gs'),
                    '^.*_REASONING_END_[0-9a-f]+__', '', 's'),
                '^\\s*(answer|réponse)\\s*[:\\-]\\s*', '', 'i')"
        ) }} AS clean_response
    FROM responses
),

split AS (
    SELECT
        *,
        CASE label_style
            WHEN 'letters' THEN LIST_SLICE(['A', 'B', 'C', 'D'], 1, LEN(choices))
            WHEN 'numbers' THEN LIST_SLICE(['1', '2', '3', '4'], 1, LEN(choices))
        END AS allowed_labels,
        UPPER(REGEXP_EXTRACT(
            REGEXP_EXTRACT(clean_response, '^(\S+)', 1),
            '^\(?([A-Da-d1-4])[).:]?$', 1)) AS first_label,
        {{ strip_whitespace("REGEXP_REPLACE(clean_response, '^\\S+', '')") }} AS label_rest,
        REGEXP_EXTRACT(clean_response, '^([^\r\n]*)', 1) AS first_line
    FROM cleaned
),

located AS (
    SELECT
        *,
        CASE
            WHEN clean_response = '' THEN NULL
            WHEN label_style IN ('letters', 'numbers') THEN
                CASE
                    WHEN LIST_POSITION(allowed_labels, first_label) IS NULL THEN NULL
                    WHEN label_rest = '' THEN LIST_POSITION(allowed_labels, first_label)
                    WHEN {{ normalize_answer('label_rest') }}
                         = {{ normalize_answer('choices[LIST_POSITION(allowed_labels, first_label)]') }}
                        THEN LIST_POSITION(allowed_labels, first_label)
                END
            WHEN label_style = 'text' THEN
                LIST_POSITION(
                    LIST_TRANSFORM(choices, c -> {{ normalize_answer('c') }}),
                    {{ normalize_answer('first_line') }}
                )
        END AS ai_position,
        LIST_POSITION(choices, correct_answer) AS correct_position
    FROM split
),

scored AS (
    SELECT
        *,
        CASE
            WHEN ai_position IS NULL THEN NULL
            WHEN label_style = 'text' THEN choices[ai_position]
            ELSE allowed_labels[ai_position]
        END AS ai_label,
        choices[ai_position] AS ai_answer,
        ai_position IS NOT NULL AS is_valid_format,
        COALESCE(choices[ai_position] = correct_answer, FALSE) AS ai_correct
    FROM located
)

SELECT
    run_id,
    run_order,
    model_key,
    lmstudio_id,
    model_name,
    model_publisher,
    model_country,
    model_params_b,
    prompt_version,
    label_style,
    temperature,
    max_tokens,
    sample_seed,
    sample_rank,
    question_id,
    choices,
    correct_answer,
    correct_label,
    correct_position,
    raw_response,
    clean_response,
    ai_position,
    ai_label,
    ai_answer,
    is_valid_format,
    ai_correct,
    CASE
        WHEN NOT is_valid_format THEN 'invalid_format'
        WHEN ai_correct THEN 'correct'
        ELSE 'incorrect'
    END AS answer_status,
    response_time_s,
    time_to_first_token_s,
    prompt_tokens,
    completion_tokens,
    stop_reason,
    stop_reason ILIKE '%maxPredictedTokens%' AS is_truncated,
    created_at
FROM scored