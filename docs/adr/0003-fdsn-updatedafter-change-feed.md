# ADR 0003: FDSN `updatedafter` som ändringsfeed, inte live-feeden

**Status:** Beslutad. Reviderad efter test mot det riktiga API:et (se "Vad testet visade").

## Kontext
USGS erbjuder två sätt att hämta data: färdiga sammanfattningsfeeds (`all_hour.geojson`, `all_day.geojson`) och FDSN-frågor.
USGS revideras i efterhand: magnituder justeras, status går från `automatic` till `reviewed`, och händelser raderas.

Sammanfattningsfeedsen innehåller händelser efter *händelsetid*. Om ett skalv från igår revideras idag syns ändringen
**aldrig** i `all_hour` eller `all_day`. En pipeline byggd på dem missar tyst revideringar av allt som är äldre än fönstret.

## Beslut
- **Ändringar (nya och reviderade):** ett FDSN-anrop med `updatedafter=<watermark - 10 min>`. Det är en riktig ändringsfeed.
- **Raderingar (best effort):** ett separat anrop över *händelsetid* (`starttime`/`endtime`, senaste tre dygnen eller hela luckan efter
  ett längre stopp) med `includedeleted=true`, där bara features med `status = deleted` behålls. Anropet har ett försök och 25 sekunders
  timeout, och ett fel loggas som varning (`poll_log.warnings`) istället för att fälla körningen. Nästa körning försöker igen.
- **Bootstrap och backfill:** dagsfönster av händelsetid *utan* `includedeleted`, så att inget anrop passerar USGS sidgräns på 20 000 träffar.
- **Watermark** läses ur `bronze.usgs_events` (`max(updated_ms)`), så det finns inget externt tillstånd som kan tappas bort.
- **Idempotent:** versioner som redan finns i bronze skrivs inte igen, och filer landar atomiskt.

## Vad testet visade
Min första design byggde på antaganden som API:et motsäger. Jag upptäckte det genom att köra mot det riktiga API:et:

| Antagande | Verklighet |
|---|---|
| `updatedbefore` avgränsar ett fönster uppåt | Parametern finns inte (**HTTP 400**: `Unknown parameter "updatedbefore"`) |
| `updatedafter` + `includedeleted=true` hämtar ändringar inklusive raderingar | Fungerar men tar **54 sekunder till gateway-timeout (504)**, mot 0,5 s utan `includedeleted` |
| `starttime`/`endtime` + `includedeleted=true` är pålitligt | **Sporadiskt**: 1 s för de flesta dagar men **504 efter 60 s** för andra (t.ex. 9 oktober), medan samma fönster utan `includedeleted` tar under en sekund |

Det sista fyndet kom först i produktion: dev-miljön hade tur med sina datum, och första prod-laddningen föll på ett fönster som gav 504.
Lärdomen är att inget flaksigt anrop får ligga i pipelinens kritiska väg, så `includedeleted` används bara best effort.
Designen följer därför det API:et faktiskt klarar. Mina enhetstester med mockad fetch hade aldrig hittat något av detta, vilket är
anledningen till att `tests/test_usgs_contract.py` kör riktiga anrop (`pytest -m live`, och nattligen i CI). De kontrollerar att
frågorna accepteras, att fälten vi förlitar oss på finns, och att anropen går snabbt.

## Alternativ
- **Live-feeds med korta intervall:** billiga och cachade av CDN, men missar revideringar. Avfärdat av just det skälet.
- **`updatedafter` + `includedeleted=true` i ett anrop:** hade varit enklast men är för långsamt och opålitligt för en pipeline som körs varje timme.
- **Streaming (WebSocket/Kafka):** USGS har ingen sådan push-feed för jordbävningar.

## Konsekvenser
- Plattformen fångar revideringar och raderingar, vilket gör SCD2-historiken (`event_history`) meningsfull.
- Avstämningen av raderingar är ett *fönster*, inte en strömmande ändringsfeed, och den är best effort. En radering av ett skalv äldre än
  fönstret, eller en radering under ett USGS-avbrott, kan dröja tills ett senare anrop lyckas.
- Backfill hämtar skalvens *senaste* version. Äldre revideringar av historiska skalv går inte att återskapa från USGS.
- Överlappet på 10 minuter ger dubbletter som tas bort på två ställen (extraktionens `drop_known` och stagingens `qualify`).
- Pagineringen (`offset`) kan i teorin missa en händelse om data ändras mellan sidorna. I praktiken ryms ett timsvar långt under en sida.
