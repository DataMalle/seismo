# ADR 0003: FDSN `updatedafter` som ändringsfeed, inte live-feeden

**Status:** Beslutad

## Kontext
USGS erbjuder två sätt att hämta data: färdiga sammanfattningsfeeds (`all_hour.geojson`, `all_day.geojson`) och FDSN-frågor.
USGS revideras i efterhand: magnituder justeras, status går från `automatic` till `reviewed`, och händelser raderas.

Sammanfattningsfeedsen innehåller händelser efter *händelsetid*. Om ett skalv från igår revideras idag syns ändringen
**aldrig** i `all_hour` eller `all_day`. En pipeline byggd på dem missar tyst revideringar av allt som är äldre än fönstret.

## Beslut
All inkrementell extraktion använder FDSN-frågan med `updatedafter=<watermark - 10 min>` och `includedeleted=true`. Det är en
riktig ändringsfeed: den returnerar nya, reviderade och raderade händelser.

- **Watermark** läses ur `bronze.usgs_events` (`max(updated_ms)`), så det finns inget externt tillstånd som kan tappas bort.
- **Gap-medveten:** efter ett längre stopp delas luckan i dagsfönster (och paginerar vid 20 000 träffar), så ingen fråga blir för stor.
- **Idempotent:** versioner som redan finns i bronze skrivs inte igen, och filer landar atomiskt.
- **Backfill** använder samma kod med ett explicit intervall.

## Alternativ
- **Live-feeds med korta intervall:** billiga och cachade av CDN, men missar revideringar. Avfärdat av just det skälet.
- **Streaming (WebSocket/Kafka):** USGS har ingen sådan push-feed för jordbävningar.

## Konsekvenser
- Plattformen fångar revideringar och raderingar, vilket gör SCD2-historiken (`event_history`) meningsfull.
- FDSN är tyngre än en cachad statisk fil. Med 30-minutersintervall och små fönster ryms det väl inom USGS rimliga användning.
- Överlappet på 10 minuter ger dubbletter som tas bort på två ställen (extraktionens `drop_known` och stagingens `qualify`).
