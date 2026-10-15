{% test value_between(model, column_name, min_value, max_value) %}
    {#- Värden utanför intervallet. NULL räknas inte här, det täcks av not_null där det krävs. -#}
    select {{ column_name }} as offending_value
    from {{ model }}
    where {{ column_name }} is not null
      and ({{ column_name }} < {{ min_value }} or {{ column_name }} > {{ max_value }})
{% endtest %}

{% test recency(model, column_name, max_age_minutes) %}
    {#- Underkänd om den senaste raden är äldre än max_age_minutes (tom tabell underkänns också). -#}
    select max({{ column_name }}) as latest
    from {{ model }}
    having max({{ column_name }}) is null
        or max({{ column_name }}) < current_timestamp() - interval {{ max_age_minutes }} minutes
{% endtest %}
