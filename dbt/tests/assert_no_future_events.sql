{#- Händelser från framtiden tyder på klock- eller parsningsfel (t.ex. sekunder tolkade som millisekunder). -#}
select event_id, event_time
from {{ ref('events') }}
where event_time > current_timestamp() + interval 10 minutes
