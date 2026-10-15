{#- Kärndata ska aldrig bero på att LLM-steget lyckats. event_locations byggs av AI-steget (tag:ai), men gold-modellerna
    left joinar den. Hooken skapar därför en tom tabell med rätt schema om den saknas, så att kärnbygget alltid har något
    att joina mot. AI-steget fyller den sedan med MERGE. Kolumnerna måste matcha models/silver/event_locations.sql. -#}
{% macro ensure_event_locations() %}
    {% set silver = target.catalog ~ '.' ~ schema_prefix() ~ '_silver' %}
    {% do run_query('create schema if not exists ' ~ silver) %}
    {% do run_query(
        'create table if not exists ' ~ silver ~ '.event_locations ('
        ~ 'locality string, country string, country_code string, region string, location_type string, '
        ~ 'is_valid boolean, raw_response string, llm_endpoint string, prompt_version string, extracted_at timestamp)'
    ) %}
{% endmacro %}
