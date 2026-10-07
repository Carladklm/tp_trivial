WITH scored AS (
    SELECT * FROM {{ ref('int_ai_responses_scored') }}
),

questions AS (
    SELECT * FROM {{ ref('stg_questions') }}
)

SELECT
    scored.run_id,
    scored.model_key,
    scored.model_name,
    scored.model_publisher,
    scored.model_country,
    scored.model_params_b,
    scored.prompt_version,
    scored.label_style,
    scored.temperature,
    scored.question_id,
    scored.sample_rank,
    questions.question_type,
    questions.difficulty,
    questions.difficulty_level,
    questions.category,
    questions.category_group,
    questions.category_name,
    questions.question_text,
    questions.nb_options,
    1.0 / questions.nb_options AS random_baseline,
    scored.choices,
    scored.correct_answer,
    scored.correct_position,
    scored.raw_response,
    scored.ai_position,
    scored.ai_answer,
    scored.is_valid_format,
    scored.ai_correct,
    scored.answer_status,
    scored.response_time_s,
    scored.time_to_first_token_s,
    scored.prompt_tokens,
    scored.completion_tokens,
    scored.stop_reason,
    scored.is_truncated,
    scored.created_at
FROM scored
INNER JOIN questions
    ON scored.question_id = questions.question_id