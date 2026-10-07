WITH questions AS (
    SELECT * FROM {{ ref('stg_questions') }}
),

correct_options AS (
    SELECT
        question_id,
        correct_answer AS option_text,
        TRUE AS is_correct
    FROM questions
),

incorrect_options AS (
    SELECT
        question_id,
        UNNEST(incorrect_answers) AS option_text,
        FALSE AS is_correct
    FROM questions
)

SELECT * FROM correct_options
UNION ALL
SELECT * FROM incorrect_options