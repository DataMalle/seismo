{#- Den aktuella versionen i historiken ska ha samma uppdateringstid som raden i events. Skiljer de sig har silver
    och historiken tappat synkronisering. -#}
select h.event_id, h.valid_from, e.updated_at
from {{ ref('event_history') }} h
join {{ ref('events') }} e on e.event_id = h.event_id
where h.is_current and h.valid_from <> e.updated_at
