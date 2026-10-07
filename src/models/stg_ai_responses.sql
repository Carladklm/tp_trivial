with source as (
    select * from {{ source('silver_files', 'ai_responses') }}
),

renamed as (

    select
        -- exécution (modèle + prompt + paramètres)
        run_id,
        cast(run_order as integer)            as run_order,
        model_key,
        lmstudio_id,
        model_name,
        publisher                             as model_publisher,
        country                               as model_country,
        cast(params_b as double)              as model_params_b,
        prompt_version,
        label_style,                                                -- 'letters', 'numbers', 'text'
        cast(temperature as double)           as temperature,
        cast(max_tokens as integer)           as max_tokens,
        cast(sample_seed as integer)          as sample_seed,
        cast(sample_rank as integer)          as sample_rank,

        -- question posée
        -- (les autres attributs : type, difficulté, catégorie... viennent de stg_questions,
        --  la source de vérité, via une jointure sur question_id en intermediate)
        question_id,
        choices,                                                    -- options dans l'ordre présenté
        correct_answer,
        correct_label,                                              -- 'C', '3' ou le texte

        -- prompt envoyé
        system_prompt,
        user_prompt,

        -- réponse brute et mesures de l'appel
        raw_response,
        cast(response_time as double)         as response_time_s,
        cast(time_to_first_token as double)   as time_to_first_token_s,
        cast(prompt_tokens as integer)        as prompt_tokens,
        cast(completion_tokens as integer)    as completion_tokens,
        stop_reason,
        cast(created_at as timestamp)         as created_at

    from source

)

select * from renamed
