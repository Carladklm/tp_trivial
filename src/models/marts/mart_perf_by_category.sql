WITH responses AS (
    SELECT * FROM {{ ref('int_responses_enriched') }}
),

per_category AS (
    SELECT
        model_key,
        model_name,
        model_country,
        prompt_version,
        temperature,
        category_group,
        category_name,
        COUNT(*) AS n_questions,
        COUNT(*) FILTER (WHERE ai_correct) AS n_correct
    FROM responses
    GROUP BY ALL
),

model_average AS (
    SELECT
        model_key,
        prompt_version,
        AVG(ai_correct::INT) AS model_accuracy
    FROM responses
    GROUP BY ALL
),

category_average AS (
    SELECT
        prompt_version,
        category_group,
        category_name,
        AVG(ai_correct::INT) AS category_accuracy_all_models
    FROM responses
    GROUP BY ALL
),

metrics AS (
    SELECT
        per_category.*,
        per_category.n_correct::DOUBLE / per_category.n_questions AS accuracy,
        model_average.model_accuracy,
        category_average.category_accuracy_all_models
    FROM per_category
    INNER JOIN model_average
        ON per_category.model_key = model_average.model_key
        AND per_category.prompt_version = model_average.prompt_version
    INNER JOIN category_average
        ON per_category.prompt_version = category_average.prompt_version
        AND per_category.category_group = category_average.category_group
        AND per_category.category_name = category_average.category_name
)

SELECT
    model_key,
    model_name,
    model_country,
    prompt_version,
    temperature,
    category_group,
    category_name,
    n_questions,
    n_correct,
    ROUND(accuracy, 4) AS accuracy,
    ROUND({{ wilson_low('n_correct', 'n_questions') }}, 4) AS accuracy_ci_low,
    ROUND({{ wilson_high('n_correct', 'n_questions') }}, 4) AS accuracy_ci_high,
    ROUND(model_accuracy, 4) AS model_accuracy,
    ROUND(accuracy - model_accuracy, 4) AS delta_vs_model_average,
    ROUND(category_accuracy_all_models, 4) AS category_accuracy_all_models,
    RANK() OVER (
        PARTITION BY prompt_version, category_group, category_name
        ORDER BY accuracy DESC
    ) AS rank_in_category,
    RANK() OVER (
        PARTITION BY prompt_version, category_group, category_name
        ORDER BY accuracy DESC
    ) = 1 AS is_best_in_category
FROM metrics
