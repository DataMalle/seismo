{#- USGS-platser ser ut som "5 km SSW of Ridgecrest, CA". Avstånd och riktning är regelbundna och plockas ut med regex.
    Bara själva orten ("Ridgecrest, CA") är tvetydig, och det är den som skickas till LLM:en. -#}
{% macro locality(place) -%}
    nullif(trim(regexp_replace({{ place }}, '^[0-9.]+ km [NSEW]{1,3} of ', '')), '')
{%- endmacro %}

{% macro distance_km(place) -%}
    try_cast(nullif(regexp_extract({{ place }}, '^([0-9.]+) km [NSEW]{1,3} of ', 1), '') as double)
{%- endmacro %}

{% macro direction(place) -%}
    nullif(regexp_extract({{ place }}, '^[0-9.]+ km ([NSEW]{1,3}) of ', 1), '')
{%- endmacro %}

{% macro magnitude_bucket(magnitude) -%}
    case
        when {{ magnitude }} is null then 'unknown'
        when {{ magnitude }} < 2 then '<2'
        when {{ magnitude }} < 3 then '2-3'
        when {{ magnitude }} < 4 then '3-4'
        when {{ magnitude }} < 5 then '4-5'
        else '5+'
    end
{%- endmacro %}
