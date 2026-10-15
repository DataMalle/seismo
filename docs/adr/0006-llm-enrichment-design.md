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
3. **Kostnadstak.** Högst `llm_batch_size` (100) nya orter per körning. Ett backlog tas ikapp över flera körningar.
4. **Validering.** Svaret måste vara tolkbar JSON, `location_type` måste vara ett av fyra tillåtna värden och landskoden måste
   vara två tecken. Annars sparas raden med `is_valid = false` och försöks om först efter ett dygn. `gold`-modellerna använder bara giltiga rader.
5. **Isolering.** AI-modellerna har taggen `ai` och körs i en egen task *efter* kärnbygget. Ett LLM-fel blockerar aldrig kärndata.
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
