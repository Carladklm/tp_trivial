WITH responses AS (
    SELECT * FROM {{ ref('int_responses_enriched') }}
    WHERE temperature = 0
),

per_question AS (
    SELECT
        question_id,
        ANY_VALUE(question_text) AS question_text,
        ANY_VALUE(question_type) AS question_type,
        ANY_VALUE(difficulty) AS difficulty,
        ANY_VALUE(difficulty_level) AS difficulty_level,
        ANY_VALUE(category_group) AS category_group,
        ANY_VALUE(category_name) AS category_name,
        ANY_VALUE(correct_answer) AS correct_answer,
        COUNT(*) AS n_answers,
        COUNT(*) FILTER (WHERE ai_correct) AS n_correct,
        COUNT(DISTINCT model_key) AS n_models,
        COUNT(DISTINCT model_key) FILTER (WHERE ai_correct) AS n_models_correct_once
    FROM responses
    GROUP BY question_id
),

answer_votes AS (
    SELECT
        question_id,
        ai_answer,
        ai_answer = correct_answer AS is_correct_answer,
        COUNT(*) AS n_votes
    FROM responses
    WHERE is_valid_format
    GROUP BY ALL
),

majority AS (
    SELECT
        question_id,
        ARG_MAX(ai_answer, n_votes) AS majority_answer,
        MAX(n_votes) AS majority_votes
    FROM answer_votes
    GROUP BY question_id
),

top_wrong AS (
    SELECT
        question_id,
        ARG_MAX(ai_answer, n_votes) AS top_wrong_answer,
        MAX(n_votes) AS top_wrong_votes
    FROM answer_votes
    WHERE NOT is_correct_answer
    GROUP BY question_id
),

metrics AS (
    SELECT
        per_question.*,
        per_question.n_correct::DOUBLE / per_question.n_answers AS success_rate,
        majority.majority_answer,
        majority.majority_votes,
        top_wrong.top_wrong_answer,
        COALESCE(top_wrong.top_wrong_votes, 0) AS top_wrong_votes
    FROM per_question
    LEFT JOIN majority
        ON per_question.question_id = majority.question_id
    LEFT JOIN top_wrong
        ON per_question.question_id = top_wrong.question_id
)

SELECT
    question_id,
    question_text,
    question_type,
    difficulty,
    difficulty_level,
    category_group,
    category_name,
    correct_answer,
    n_models,
    n_answers,
    n_correct,
    ROUND(success_rate, 4) AS success_rate,
    CASE
        WHEN success_rate >= 2.0 / 3 THEN 'easy'
        WHEN success_rate >= 1.0 / 3 THEN 'medium'
        ELSE 'hard'
    END AS ai_difficulty,
    CASE
        WHEN success_rate >= 2.0 / 3 THEN 1
        WHEN success_rate >= 1.0 / 3 THEN 2
        ELSE 3
    END AS ai_difficulty_level,
    n_models_correct_once,
    majority_answer,
    majority_votes,
    COALESCE(majority_answer = correct_answer, FALSE) AS is_majority_correct,
    top_wrong_answer,
    top_wrong_votes,
    n_correct = 0 AS is_all_wrong,
    n_correct = n_answers AS is_all_correct,
    n_correct = 0 AND top_wrong_votes * 2 >= n_answers AS is_common_trap
FROM metrics
