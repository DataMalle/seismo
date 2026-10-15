# ADR 0006: LLM-berikning, regex först, cachad, validerad och med kostnadstak

**Status:** Beslutad

## Kontext
USGS `place` är fri text, till exempel `5 km SSW of Ridgecrest, CA` eller `Mid-Atlantic Ridge`. Land och region saknas som
strukturerade fält men behövs för analys per land. En LLM kan extrahera dem, men LLM-anrop kostar, kan ge felaktiga eller
ogiltiga svar och ska inte köras om i onödan.

## Beslut
1. **Deterministiskt först.** Avstånd och riktning är regelbundna och plockas ut med regex (`macros/location.sql`). LLM:en
   får bara den tvetydiga delen: orten (`Ridgecrest, CA`).
2. **Cache per ort.** Resultatet sparas i `event_locations` med ort som nyckel. Samma ort frågas aldrig två gånger, och orter är
   få jämfört med antalet händelser.
3. **Kostnadstak.** Högst `llm_batch_size` (300) nya orter per körning. Ett backlog tas ikapp över flera körningar. I stabilt läge är nya orter få, så taket styr bara kostnaden i värsta fall.
4. **Validering.** Svaret måste vara tolkbar JSON, `location_type` måste vara ett av fyra tillåtna värden, landskoden måste
   vara två tecken och minst ett av land och region måste finnas. Land krävs *inte* för hav och regioner: min första regel krävde
   land och avvisade därför korrekta svar för Mid-Atlantic Ridge, vilket syntes först i produktion. Annars sparas raden med `is_valid = false` och försöks om först efter ett dygn. `gold`-modellerna använder bara giltiga rader.
5. **Isolering.** AI-modellerna har taggen `ai` och körs som sista kommandot i dbt-tasken, *efter* kärnbygget och freshness. Ett LLM-fel kan
   därför aldrig blockera kärndata, som redan är publicerad. En hook skapar en tom `event_locations` om den saknas, så att gold alltid kan joina mot den.
   (Jag körde först AI-stegen som en egen task, men varje dbt-task betalar en egen miljöstart på minuter, så de delar nu task.)
6. **Siffror räknas aldrig av modellen.** Det dagliga sammandraget (`gold_daily_briefing`) får färdigräknade fakta från SQL och
   formulerar dem bara. Ett dbt-test verifierar att den starkaste magnituden står i texten.

## Varför inte låta LLM:en göra allt
Att be en modell extrahera avstånd, riktning *och* land ger fler fel och högre kostnad än att låta regex ta det regelbundna.
Princip: använd en LLM där indata är tvetydig, inte där en regel räcker. Mina tidigare projekt visade dessutom att modeller tappar
siffror när de läser eller räknar långa tal, vilket är skälet till punkt 6.

## Konsekvenser
- Förutsägbar kostnad och låg latens (de flesta orter är cache-träffar).
- Mätbar kvalitet: `llm_valid_ratio` exponeras i `gold_pipeline_health` och visas i appen.
- Endpointen och promptversionen sparas per rad (`llm_endpoint`, `prompt_version`), så att resultat går att spåra och göras om vid modellbyte.
