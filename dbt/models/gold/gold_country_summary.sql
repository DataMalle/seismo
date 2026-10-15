select
    coalesce(l.country, 'Unknown')                       as country,
    count(*)                                             as events_30d,
    max(e.magnitude)                                     as max_magnitude,
    count_if(e.magnitude >= 4.5)                         as strong_events_30d,
    max(e.event_time)                                    as last_event_time
from {{ ref('events') }} e
left join {{ ref('event_locations') }} l on l.locality = e.locality and l.is_valid
where not e.is_deleted
  and e.event_time >= current_timestamp() - interval 30 days
group by 1
