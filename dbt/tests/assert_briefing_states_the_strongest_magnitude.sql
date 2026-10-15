{{ config(severity='warn') }}
{#- AI-validering: texten måste innehålla den magnitud som SQL räknade fram. Fångar modeller som hittar på eller avrundar fel. -#}
select briefing_date, max_magnitude_text, briefing
from {{ ref('gold_daily_briefing') }}
where max_magnitude_text is not null
  and briefing is not null
  and not contains(replace(briefing, ',', '.'), max_magnitude_text)
