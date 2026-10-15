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

{#- Giltigt LLM-svar: platstypen är en av de tillåtna och minst ett av land/region finns. Land krävs *inte* för hav och
    regioner (Mid-Atlantic Ridge har inget land), men ett svar utan både land och region säger ingenting. -#}
{% macro is_valid_location(country, country_code, region, location_type) -%}
    coalesce(
        {{ location_type }} in ('city', 'region', 'ocean', 'unknown')
        and ({{ country }} is not null or {{ region }} is not null)
        and ({{ country_code }} is null or length({{ country_code }}) = 2),
        false
    )
{%- endmacro %}

{#- Etikett för gold: land, annars Ocean för hav, annars Unknown. -#}
{% macro country_label(country, location_type) -%}
    coalesce({{ country }}, case when {{ location_type }} = 'ocean' then 'Ocean' else 'Unknown' end)
{%- endmacro %}
