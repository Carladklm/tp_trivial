-- Grain : 1 ligne = 1 réponse d'un modèle à une question, pour un run (modèle x prompt).
-- Rôle : interpréter la réponse brute, la corriger, et l'enrichir avec les attributs
-- de la question (type, difficulté, catégorie) venant de stg_questions.

with responses as (
    select * from {{ ref('stg_ai_responses') }}
),

questions as (
    select * from {{ ref('stg_questions') }}
),

cleaned as (
    select
        *,
        -- 1) retire un éventuel raisonnement <think>...</think>
        -- 2) retire le gras/code Markdown (* et `)
        -- 3) retire une puce en début de réponse ("- 2016"), sans toucher aux nombres négatifs ("-40")
        -- 4) remplace retours à la ligne et espaces multiples par un espace
        trim(regexp_replace(regexp_replace(regexp_replace(
            regexp_replace(coalesce(raw_response, ''), '(?s)<think>.*?</think>', '', 'g'),
            '[*`]', '', 'g'),
            '^\s*[-•]\s+', ''),
            '\s+', ' ', 'g'
        )) as response_clean
    from responses
),

extracted as (
    select
        *,
        -- étiquette donnée par le modèle, selon le style de prompt
        case label_style
            when 'letters' then nullif(regexp_extract(upper(response_clean), '^[\s(\[]*([A-D])([\s)\].:,]|$)', 1), '')
            when 'numbers' then nullif(regexp_extract(response_clean, '^[\s(\[]*([1-4])([\s)\].:,]|$)', 1), '')
            when 'text'    then nullif(response_clean, '')
        end as ai_label
    from cleaned
),

positioned as (
    select
        *,
        -- position (1 à 4) de l'option choisie dans la liste présentée au modèle
        case label_style
            when 'letters' then ascii(ai_label) - ascii('A') + 1
            when 'numbers' then try_cast(ai_label as integer)
            -- même normalisation des deux côtés : réponse du modèle et choix proposés
            when 'text'    then list_position(
                                   [{{ normalize_answer('c') }} for c in choices],
                                   {{ normalize_answer('ai_label') }}
                               )
        end as ai_position
    from extracted
)

select
    -- run
    p.run_id,
    p.run_order,
    p.model_key,
    p.model_name,
    p.model_publisher,
    p.model_country,
    p.model_params_b,
    p.prompt_version,
    p.label_style,
    p.temperature,
    p.max_tokens,
    p.sample_seed,
    p.sample_rank,

    -- question (attributs issus de stg_questions, la source de vérité)
    p.question_id,
    q.question_type,
    q.difficulty,
    q.difficulty_level,
    q.category_group,
    q.category_name,
    q.question_text,
    p.choices,
    p.correct_answer,
    p.correct_label,

    -- réponse et correction
    p.raw_response,
    p.ai_label,
    case when p.ai_position between 1 and len(p.choices)
         then p.choices[p.ai_position] end                                   as ai_answer,
    coalesce(p.ai_position between 1 and len(p.choices), false)              as is_valid_format,
    coalesce(p.ai_position between 1 and len(p.choices)
             and p.choices[p.ai_position] = p.correct_answer, false)         as ai_correct,

    -- mesures
    p.response_time_s,
    p.time_to_first_token_s,
    p.prompt_tokens,
    p.completion_tokens,
    p.stop_reason,
    p.created_at

from positioned p
left join questions q
    on p.question_id = q.question_id
