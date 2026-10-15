{#- SCD2-invariant: exakt en aktuell version per händelse. -#}
select event_id, count_if(is_current) as current_versions
from {{ ref('event_history') }}
group by event_id
having count_if(is_current) <> 1
