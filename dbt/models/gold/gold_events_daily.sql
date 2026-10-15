select
    cast(event_time as date)             as event_date,
    {{ magnitude_bucket('magnitude') }}  as magnitude_bucket,
    count(*)                             as events,
    max(magnitude)                       as max_magnitude,
    round(avg(depth_km), 1)              as avg_depth_km
from {{ ref('events') }}
where not is_deleted
group by 1, 2
