{{
    config(
        materialized='incremental',
        incremental_strategy='merge',
        unique_key='event_id',
        liquid_clustered_by=['event_time'],
        tblproperties={
            'delta.enableIcebergCompatV2': 'true',
            'delta.universalFormat.enabledFormats': 'iceberg'
        }
    )
}}

{#- Senaste kända version av varje händelse. Inkrementell på *inläsningstid*, inte på uppdateringstid, så att en sent
    levererad version aldrig missas. Äldre versioner än den som redan finns hoppas över, så att en omkörning eller
    out-of-order-leverans inte kan skriva över ny data med gammal. -#}
with versions as (

    select * from {{ ref('stg_usgs_event_versions') }} v
    {% if is_incremental() %}
    where v.ingested_at > (select coalesce(max(last_ingested_at), timestamp'1970-01-01') from {{ this }})
      and not exists (
          select 1 from {{ this }} t
          where t.event_id = v.event_id and t.updated_at >= v.updated_at
      )
    {% endif %}

),

latest as (

    select * from versions
    qualify row_number() over (partition by event_id order by updated_ms desc, ingested_at desc) = 1

)

select
    event_id,
    event_time,
    updated_at,
    magnitude,
    magnitude_type,
    place,
    {{ locality('place') }}     as locality,
    {{ distance_km('place') }}  as distance_km,
    {{ direction('place') }}    as direction,
    review_status,
    event_type,
    tsunami_flag,
    significance,
    felt_reports,
    pager_alert,
    network,
    url,
    longitude,
    latitude,
    depth_km,
    coalesce(review_status = 'deleted', false) as is_deleted,
    ingested_at as last_ingested_at
from latest
