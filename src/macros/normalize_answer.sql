{% macro strip_whitespace(text) -%}
    REGEXP_REPLACE({{ text }}, '^\s+|\s+$', '', 'g')
{%- endmacro %}


{% macro normalize_answer(text) -%}
    LOWER(REGEXP_REPLACE(
        {{ strip_whitespace("RTRIM(" ~ strip_whitespace("TRIM(" ~ strip_whitespace(text) ~ ", '\"''`*')") ~ ", '.!')") }},
        '\s+', ' ', 'g'
    ))
{%- endmacro %}