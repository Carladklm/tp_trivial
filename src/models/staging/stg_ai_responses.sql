WITH source AS (
    SELECT * FROM {{ source('silver', 'ai_responses') }}
),

renamed AS (
    SELECT
        run_id,
        CAST(run_order AS integer) AS run_order,
        model_key,
        lmstudio_id,
        model_name,
        publisher AS model_publisher,
        country AS model_country,
        CAST(params_b AS double) AS model_params_b,
        prompt_version,
        label_style,                                               
        CAST(temperature AS double) AS temperature,
        CAST(max_tokens AS integer) AS max_tokens,
        CAST(sample_seed AS integer) AS sample_seed,
        CAST(sample_rank AS integer) AS sample_rank,
        question_id,
        choices,                                                    
        correct_answer,
        correct_label,                                              
        system_prompt,
        user_prompt,
        raw_response,
        CAST(response_time AS double) AS response_time_s,
        CAST(time_to_first_token AS double) AS time_to_first_token_s,
        CAST(prompt_tokens AS integer) AS prompt_tokens,
        CAST(completion_tokens AS integer) AS completion_tokens,
        stop_reason,
        CAST(created_at AS timestamp) AS created_at

    FROM source

)

SELECT * FROM renamed
