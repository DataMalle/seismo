{#- Ett giltigt LLM-svar måste säga något: minst ett av land och region. Skyddar mot att valideringsregeln luckras upp av misstag. -#}
select locality, country, region, location_type
from {{ ref('event_locations') }}
where is_valid and country is null and region is null
