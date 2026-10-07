WITH responses AS (
    SELECT * FROM {{ ref('int_responses_enriched') }}
),

totals AS (
    SELECT
        model_key,
        prompt_version,
        question_type,
        COUNT(*) AS n_total,
        COUNT(*) FILTER (WHERE is_valid_format) AS n_valid
    FROM responses
    GROUP BY ALL
),

expected AS (
    SELECT
        model_key,
        model_name,
        prompt_version,
        label_style,
        temperature,
        question_type,
        correct_position AS position,
        COUNT(*) AS n_correct_here,
        COUNT(*) FILTER (WHERE ai_correct) AS n_found_here
    FROM responses
    GROUP BY ALL
),

chosen AS (
    SELECT
        model_key,
        prompt_version,
        question_type,
        ai_position AS position,
        COUNT(*) AS n_chosen
    FROM responses
    WHERE is_valid_format
    GROUP BY ALL
)

SELECT
    expected.model_key,
    expected.model_name,
    expected.prompt_version,
    expected.label_style,
    expected.temperature,
    expected.question_type,
    expected.position,
    CASE
        WHEN expected.question_type = 'boolean' THEN CASE expected.position WHEN 1 THEN 'True' ELSE 'False' END
        ELSE CHR(64 + expected.position)
    END AS position_label,
    COALESCE(chosen.n_chosen, 0) AS n_chosen,
    expected.n_correct_here,
    ROUND(COALESCE(chosen.n_chosen, 0)::DOUBLE / NULLIF(totals.n_valid, 0), 4) AS share_chosen,
    ROUND(expected.n_correct_here::DOUBLE / totals.n_total, 4) AS share_expected,
    ROUND(
        COALESCE(chosen.n_chosen, 0)::DOUBLE / NULLIF(totals.n_valid, 0)
        - expected.n_correct_here::DOUBLE / totals.n_total, 4
    ) AS position_bias,
    ROUND(expected.n_found_here::DOUBLE / expected.n_correct_here, 4) AS accuracy_when_correct_here
FROM expected
INNER JOIN totals
    ON expected.model_key = totals.model_key
    AND expected.prompt_version = totals.prompt_version
    AND expected.question_type = totals.question_type
LEFT JOIN chosen
    ON expected.model_key = chosen.model_key
    AND expected.prompt_version = chosen.prompt_version
    AND expected.question_type = chosen.question_type
    AND expected.position = chosen.position
