select
    event_id,
    event_time,
    magnitude,
    place,
    latitude,
    longitude,
    depth_km
from {{ ref('events') }}
where not is_deleted
  and magnitude is not null
  and latitude is not null
  and longitude is not null
  and event_time >= current_timestamp() - interval 7 days
order by event_time desc
limit 5000
