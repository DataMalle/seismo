{#- Avstämning mellan lagren: varje händelse i bronze måste finnas i silver. Returnerade rader är händelser som tappats. -#}
select distinct s.event_id
from {{ ref('stg_usgs_event_versions') }} s
left join {{ ref('events') }} e on e.event_id = s.event_id
where e.event_id is null
