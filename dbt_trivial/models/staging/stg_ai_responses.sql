SELECT
    CAST(question_id AS VARCHAR)      AS question_id,
    CAST(run_id AS VARCHAR)           AS run_id,
    CAST(model AS VARCHAR)            AS model,
    CAST(prompt_version AS VARCHAR)   AS prompt_version,
    CAST(prompt_text AS VARCHAR)      AS prompt_text,
    choices,
    CAST(correct_letter AS VARCHAR)   AS correct_letter,
    CAST(raw_response AS VARCHAR)     AS raw_response,
    CAST(ai_letter AS VARCHAR)        AS ai_letter,
    CAST(ai_answer AS VARCHAR)        AS ai_answer,
    CAST(ai_correct AS BOOLEAN)       AS ai_correct,
    CAST(is_valid_format AS BOOLEAN)  AS is_valid_format,
    CAST(response_time AS DOUBLE)     AS response_time,
    CAST(created_at AS TIMESTAMP)     AS created_at
FROM {{ source('silver', 'ai_responses') }}
