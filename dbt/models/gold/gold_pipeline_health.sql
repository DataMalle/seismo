{#- Plattformens egen hälsa som en enda rad: färskhet, volymer, revideringar och kvalitetssignaler. Läses av appen och av
    watchdog-workflowet som öppnar ett GitHub-issue om SLA:n bryts. -#}
with last_poll as (

    select polled_at, status, error from {{ source('ops', 'poll_log') }}
    order by polled_at desc limit 1

),

polls_24h as (

    select count(*) as polls, count_if(status <> 'success') as failed
    from {{ source('ops', 'poll_log') }}
    where polled_at > current_timestamp() - interval 24 hours

)

select
    current_timestamp()                                                                 as computed_at,
    (select polled_at from last_poll)                                                   as last_poll_at,
    (select status from last_poll)                                                      as last_poll_status,
    (select max(event_time) from {{ ref('events') }})                                   as latest_event_time,
    (select max(updated_at) from {{ ref('events') }})                                   as latest_update_time,
    (select count(*) from {{ ref('events') }} where not is_deleted)                     as events_total,
    (select count(*) from {{ ref('events') }} where is_deleted)                         as events_deleted,
    (select count(*) from {{ ref('events') }} where updated_at > current_timestamp() - interval 24 hours) as updates_24h,
    (select count(*) from {{ ref('event_history') }}
        where revision_number > 1 and valid_from > current_timestamp() - interval 24 hours)               as revisions_24h,
    (select count(*) from {{ source('bronze', 'usgs_events_quarantine') }})             as quarantined_rows,
    (select cast(avg(case when is_valid then 1.0 else 0.0 end) as double) from {{ ref('event_locations') }}) as llm_valid_ratio,
    (select polls from polls_24h)                                                       as polls_24h,
    (select failed from polls_24h)                                                      as failed_polls_24h
