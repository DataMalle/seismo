{{
    config(
        materialized='incremental',
        incremental_strategy='merge',
        unique_key='locality',
        tags=['ai']
    )
}}

{#- LLM-berikning, designad för kostnad och tillförlitlighet:
    1. Avstånd och riktning plockas ut med regex i events. LLM:en får bara den tvetydiga delen (orten).
    2. Resultatet cachas per ort: samma ort frågas aldrig två gånger, och orter är få jämfört med händelser.
    3. Högst llm_batch_size nya orter per körning, så kostnaden har ett tak även om feeden skulle svämma över.
    4. Svaret valideras. Ogiltiga svar sparas med is_valid = false och försöks om först efter ett dygn. -#}

with todo as (

    select distinct locality
    from {{ ref('events') }} e
    where locality is not null
    {% if is_incremental() %}
      and not exists (
          select 1 from {{ this }} t
          where t.locality = e.locality
            and (t.is_valid or t.extracted_at > current_timestamp() - interval 1 day)
      )
    {% endif %}
    order by locality
    limit {{ var('llm_batch_size') }}

),

answered as (

    select
        locality,
        ai_query(
            '{{ var("llm_endpoint") }}',
            concat(
                'Return ONLY a compact JSON object with keys country (English name), country_code (ISO 3166-1 alpha-2 or null), ',
                'region (state, province or sea area, or null) and location_type (one of: city, region, ocean, unknown) ',
                'for this USGS earthquake location string: ', locality
            ),
            failOnError => false,
            modelParameters => named_struct('max_tokens', 120, 'temperature', 0.0)
        ) as response
    from todo

),

parsed as (

    select
        locality,
        response.result as raw_response,
        from_json(
            regexp_extract(response.result, '(?s)(\\{.*\\})', 1),
            'country string, country_code string, region string, location_type string'
        ) as x
    from answered

)

select
    locality,
    x.country                                   as country,
    x.country_code                              as country_code,
    x.region                                    as region,
    x.location_type                             as location_type,
    {{ is_valid_location('x.country', 'x.country_code', 'x.region', 'x.location_type') }} as is_valid,
    raw_response,
    '{{ var("llm_endpoint") }}'                 as llm_endpoint,
    '{{ var("prompt_version") }}'               as prompt_version,
    current_timestamp()                         as extracted_at
from parsed
