{{ config(severity='warn') }}
{#- Rader som saknar id eller updated hamnar i karantän. Det är ingen katastrof, men någon ska titta på dem. -#}
select event_id, updated_ms, source_file
from {{ source('bronze', 'usgs_events_quarantine') }}
