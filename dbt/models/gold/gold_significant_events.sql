select
    e.event_id,
    e.event_time,
    e.magnitude,
    e.place,
    coalesce(l.country, 'Unknown')   as country,
    l.region                         as region,
    e.depth_km,
    e.latitude,
    e.longitude,
    coalesce(e.tsunami_flag, 0) = 1  as tsunami_warning,
    e.significance,
    e.felt_reports,
    h.revisions,
    e.url
from {{ ref('events') }} e
left join {{ ref('event_locations') }} l on l.locality = e.locality and l.is_valid
left join (
    select event_id, max(revision_number) as revisions from {{ ref('event_history') }} group by event_id
) h on h.event_id = e.event_id
where not e.is_deleted
  and e.magnitude >= 4.5
  and e.event_time >= current_timestamp() - interval 90 days
