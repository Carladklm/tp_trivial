{% macro wilson_low(n_success, n_total, z=1.96) -%}
    CASE WHEN {{ n_total }} > 0 THEN
        (
            {{ n_success }}::DOUBLE / {{ n_total }}
            + {{ z }} * {{ z }} / (2.0 * {{ n_total }})
            - {{ z }} * SQRT(
                ({{ n_success }}::DOUBLE / {{ n_total }}) * (1 - {{ n_success }}::DOUBLE / {{ n_total }}) / {{ n_total }}
                + {{ z }} * {{ z }} / (4.0 * {{ n_total }} * {{ n_total }})
            )
        ) / (1 + {{ z }} * {{ z }} / {{ n_total }})
    END
{%- endmacro %}


{% macro wilson_high(n_success, n_total, z=1.96) -%}
    CASE WHEN {{ n_total }} > 0 THEN
        (
            {{ n_success }}::DOUBLE / {{ n_total }}
            + {{ z }} * {{ z }} / (2.0 * {{ n_total }})
            + {{ z }} * SQRT(
                ({{ n_success }}::DOUBLE / {{ n_total }}) * (1 - {{ n_success }}::DOUBLE / {{ n_total }}) / {{ n_total }}
                + {{ z }} * {{ z }} / (4.0 * {{ n_total }} * {{ n_total }})
            )
        ) / (1 + {{ z }} * {{ z }} / {{ n_total }})
    END
{%- endmacro %}
