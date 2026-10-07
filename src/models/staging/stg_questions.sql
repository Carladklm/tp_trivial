-- Staging des questions : copie fidèle de questions_clean.parquet.
-- Rôle du staging : renommer et typer, SANS transformer le contenu ni changer le grain.
-- Grain : 1 ligne = 1 question.

with source as (

    select * from {{ source('silver_files', 'questions_clean') }}

),

renamed as (

    select
        -- identifiant
        question_id,

        -- caractéristiques de la question
        type                               as question_type,      -- 'multiple' ou 'boolean'
        difficulty,                                                -- 'easy', 'medium', 'hard'
        cast(difficulty_level as tinyint)  as difficulty_level,   -- 1, 2, 3
        category,
        category_group,
        category_name,

        -- contenu
        question                           as question_text,
        correct_answer,
        incorrect_answers,                                         -- liste : varchar[]
        cast(nb_options as tinyint)        as nb_options           -- 4 (QCM) ou 2 (Vrai/Faux)

    from source

)

select * from renamed
