{# Normalise un texte de réponse pour comparer la réponse du modèle aux choix :
   guillemets et apostrophes typographiques remplacés par leur version droite,
   sans * ni `, en minuscules, sans espaces ni ponctuation en fin de texte. #}
{% macro normalize_answer(expr) -%}
    lower(regexp_replace(
        regexp_replace(translate(trim({{ expr }}), '‘’“”', '''''""'), '[*`]', '', 'g'),
        '[\s.!?,;:"''`]+$', ''
    ))
{%- endmacro %}
