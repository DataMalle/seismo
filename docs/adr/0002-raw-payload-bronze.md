# ADR 0002: Bronze lagrar rå payload (schema-on-read)

**Status:** Beslutad

## Kontext
USGS GeoJSON innehåller många fält som varierar mellan händelser och som kan ändras utan förvarning. Om bronze tolkar
schemat vid ingest kan ett nytt eller förändrat fält stoppa hela ingesten, och rådata går förlorad om tolkningen var fel.

## Beslut
Bronze lagrar **varje feature som oförändrad JSON-text** (`payload`) plus två extraherade nycklar (`event_id`, `updated_ms`),
filen den kom från och inläsningstid. Typning och fältval sker i dbt-staging med ett explicit schema (`from_json`).

Rader som saknar `id` eller `updated` går till en **karantäntabell** istället för att stoppa strömmen.

## Alternativ
- **Auto Loader med schemainferens och `addNewColumns`:** bekvämt, men en schemaändring stoppar strömmen tills den startas om,
  och bronze blir beroende av uppströms struktur.
- **Fullt typad bronze:** snabbare frågor, men flyttar parsningsrisken in i ingesten.

## Konsekvenser
- Ingesten kan inte gå sönder av uppströms schemaändringar. Ett nytt fält syns först när jag lägger till det i staging.
- Rådata går alltid att köra om genom en rättad parser (reprocessing utan ny hämtning från USGS).
- Kostnaden är lite mer lagring och att JSON tolkas vid läsning. Staging är en vy och silver är inkrementellt, så tolkningen sker bara för nya rader.
- dbt-enhetstestet `stg_tolerates_unknown_new_fields` bevisar att okända fält inte bryter tolkningen.
