{#- Schema-on-read: råpayloaden tolkas här med ett explicit schema. Okända nya fält från USGS ignoreras tills de läggs till
    nedan, vilket gör att en uppströmsändring aldrig kan bryta ingesten, bara fördröja ett nytt fält. -#}
with raw as (

    select event_id, updated_ms, ingested_at, source_file,
        from_json(
            payload,
            'struct<
                id:string,
                properties:struct<
                    mag:double, magType:string, place:string, time:bigint, updated:bigint, status:string, type:string,
                    tsunami:int, sig:int, felt:int, cdi:double, mmi:double, alert:string, net:string, url:string,
                    nst:int, dmin:double, rms:double, gap:double
                >,
                geometry:struct<coordinates:array<double>>
            >'
        ) as p
    from {{ source('bronze', 'usgs_events') }}

),

typed as (

    select
        event_id,
        updated_ms,
        timestamp_millis(updated_ms)            as updated_at,
        timestamp_millis(p.properties.time)     as event_time,
        p.properties.mag                        as magnitude,
        p.properties.magType                    as magnitude_type,
        p.properties.place                      as place,
        p.properties.status                     as review_status,
        p.properties.type                       as event_type,
        p.properties.tsunami                    as tsunami_flag,
        p.properties.sig                        as significance,
        p.properties.felt                       as felt_reports,
        p.properties.alert                      as pager_alert,
        p.properties.net                        as network,
        p.properties.url                        as url,
        p.geometry.coordinates[0]               as longitude,
        p.geometry.coordinates[1]               as latitude,
        p.geometry.coordinates[2]               as depth_km,
        ingested_at,
        source_file
    from raw

)

{#- Samma version kan ha lästs in flera gånger (omkörningar, överlappande fönster). Behåll en. -#}
select * from typed
qualify row_number() over (partition by event_id, updated_ms order by ingested_at desc) = 1
