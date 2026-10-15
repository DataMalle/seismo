{{
    config(
        materialized='incremental',
        incremental_strategy='merge',
        unique_key='briefing_date',
        on_schema_change='fail',
        tags=['ai']
    )
}}

{#- AI-steg 2: ett dagligt textsammandrag. Alla siffror räknas i SQL (facts) och skickas färdiga till modellen, som bara
    formulerar dem. Små språkmodeller räknar och avrundar opålitligt, så modellen får aldrig räkna själv. Ett dbt-test
    kontrollerar att största magnituden verkligen står i texten. -#}
with today as (

    select * from {{ ref('events') }}
    where not is_deleted and event_time >= date_trunc('day', current_timestamp())

),

strongest as (

    select t.*, coalesce(l.country, t.place) as where_text
    from today t
    left join {{ ref('event_locations') }} l on l.locality = t.locality and l.is_valid
    order by t.magnitude desc nulls last
    limit 1

),

facts as (

    select
        current_date()                                                    as briefing_date,
        (select count(*) from today)                                      as events_today,
        (select count(*) from today where magnitude >= 4.5)               as strong_events_today,
        (select cast(round(magnitude, 1) as string) from strongest)       as max_magnitude_text,
        (select where_text from strongest)                                as max_magnitude_where

)

select
    briefing_date,
    events_today,
    strong_events_today,
    max_magnitude_text,
    max_magnitude_where,
    ai_query(
        '{{ var("llm_endpoint") }}',
        concat(
            'Write two short sentences in Swedish summarising todays global earthquake activity. ',
            'Use ONLY these facts and write numbers exactly as given (use a dot as decimal separator). ',
            'Total events: ', cast(events_today as string),
            '. Events with magnitude 4.5 or higher: ', cast(strong_events_today as string),
            '. Strongest event: magnitude ', coalesce(max_magnitude_text, 'unknown'),
            ' near ', coalesce(max_magnitude_where, 'unknown'), '.'
        ),
        modelParameters => named_struct('max_tokens', 160, 'temperature', 0.0)
    )                                                                     as briefing,
    '{{ var("llm_endpoint") }}'                                           as llm_endpoint,
    current_timestamp()                                                   as generated_at
from facts
where events_today > 0
