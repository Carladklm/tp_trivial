WITH source AS (
    SELECT * FROM {{ source('silver', 'questions_clean') }}
),

renamed AS (
    SELECT
        question_id,
        type AS question_type,      
        difficulty,                                                
        CAST(difficulty_level AS tinyint)  AS difficulty_level,  
        category,
        category_group,
        category_name,
        question AS question_text,
        correct_answer,
        incorrect_answers,                                        
        CAST(nb_options AS tinyint) AS nb_options

    FROM source

)

SELECT * FROM renamed
