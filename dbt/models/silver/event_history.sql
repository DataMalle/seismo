{#- SCD2 av varje händelse. Bronze är redan en komplett ändringslogg, så historiken kan räknas fram deterministiskt med
    fönsterfunktioner. En dbt-snapshot behövs inte och skulle dessutom vara omöjlig att återskapa vid backfill. -#}
select
    event_id,
    updated_at                                                          as valid_from,
    lead(updated_at) over (partition by event_id order by updated_ms)   as valid_to,
    lead(updated_at) over (partition by event_id order by updated_ms) is null as is_current,
    row_number() over (partition by event_id order by updated_ms)       as revision_number,
    magnitude,
    magnitude - lag(magnitude) over (partition by event_id order by updated_ms) as magnitude_delta,
    review_status,
    lag(review_status) over (partition by event_id order by updated_ms) as previous_review_status,
    place
from {{ ref('stg_usgs_event_versions') }}
