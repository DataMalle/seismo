# Datakontrakt: gold-lagret

Gold är det som konsumenter läser (dashboarden, och i ett verkligt team andra analytiker). Kontraktet gäller schemat `seismo_gold`.
**Källan är `dbt/models/gold/gold.yml`.** Det här dokumentet är en läsbar sammanfattning av den.

## Vad ett kontrakt innebär här

- **Enforced:** `contract: {enforced: true}` på varje gold-modell. dbt jämför kolumnnamn, ordning och datatyper mot modellens faktiska
  utdata *innan* tabellen skapas. Avviker något stoppas körningen och den gamla tabellen ligger kvar orörd.
- **Constraints skapas i Delta:** `NOT NULL` och `PRIMARY KEY` (informativ i Unity Catalog, vilket gör att verktyg kan läsa den).
- **`on_schema_change: fail`:** en oväntad ny kolumn sprids aldrig tyst till konsumenter.
- **Dokumentation i katalogen:** `persist_docs` skriver beskrivningarna som kommentarer i Unity Catalog, så de syns i katalogen och för LLM-verktyg.

Kontraktet har redan gjort nytta: när jag byggde `gold_pipeline_health` stoppades den av kontraktet eftersom `avg()` över decimaltal gav
typen `decimal` istället för `double`. Utan kontraktet hade typen tyst ändrats för alla konsumenter.

## Tabeller

| Tabell | Nyckel | Innehåll | Uppdatering |
|---|---|---|---|
| `gold_events_daily` | `(event_date, magnitude_bucket)` | Antal skalv per dag och magnitudklass | varje timme |
| `gold_significant_events` | `event_id` | Skalv med magnitud 4,5 eller högre, senaste 90 dagarna, med land och antal revideringar | varje timme |
| `gold_country_summary` | `country` | Aktivitet per land, senaste 30 dagarna | varje timme |
| `gold_event_map` | `event_id` | Skalv senaste 7 dagarna med koordinater (högst 5 000 rader) | varje timme |
| `gold_pipeline_health` | (en rad) | Färskhet, volymer, revideringar och kvalitetssignaler | varje timme |
| `gold_daily_briefing` | `briefing_date` | AI-skrivet dagligt sammandrag | varje timme |

Kolumnnamn, typer och beskrivningar finns i `gold.yml` och i Unity Catalog.

## Garantier till konsumenter

| Garanti | Hur den säkras |
|---|---|
| Schema och typer ändras aldrig utan att kontraktet ändras | `contract: enforced` plus kodgranskning av `gold.yml` |
| Nycklarna är unika och icke-null | `PRIMARY KEY`/`NOT NULL` och dbt-tester |
| Magnitud, latitud och longitud är rimliga | `value_between`-tester |
| Raderade händelser ingår aldrig | Filtret `not is_deleted` i varje gold-modell |
| Land kommer bara från validerade LLM-svar | Join på `event_locations.is_valid`, annars `Unknown` |
| Ett LLM-fel ändrar inte kärndata | AI-modellerna körs som sista dbt-kommandot, efter att kärndata publicerats, och hooken skapar `event_locations` om den saknas |
| Färskhet: senaste *lyckade* körning är inte äldre än 150 minuter | Source freshness (dbt) och watchdog-workflowet (GitHub-issue) |

## Vad som *inte* garanteras

- **Fullständighet bakåt i tiden.** Historiken börjar vid första körningen plus backfill. Dagar nära början kan vara ofullständiga.
- **Realtid.** Datat är högst ca en timme gammalt när allt fungerar, inte sekunder.
- **Att USGS-data är slutgiltig.** USGS reviderar skalv i efterhand, vilket är själva poängen med `event_history` och `revisions`.
- **LLM-extraherat land är korrekt i varje enskilt fall.** Det valideras strukturellt, inte faktamässigt. `llm_valid_ratio` mäter andelen strukturellt giltiga svar.

## Hur ett brytande ändringsförslag går till

1. Ändra modellen och `gold.yml` i samma PR. CI kör `dbt parse --warn-error`.
2. Konsumenterna syns som `exposures` i dbt (dashboarden). Använd lineage-grafen för att se vem som påverkas.
3. Rulla ut i `dev` först och kontrollera att kontraktet håller, därefter `prod`.
