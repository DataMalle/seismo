# ADR 0004: dbt för transformationer, Auto Loader för ingest

**Status:** Beslutad

## Kontext
Databricks erbjuder Lakeflow Declarative Pipelines (tidigare DLT) som hanterar bronze-till-gold deklarativt med inbyggda
expectations. dbt är branschstandard för analytics engineering och bär med sig tester, dokumentation, lineage och datakontrakt
som är oberoende av motorn.

## Beslut
- **Ingest (strömmande, tillståndsfull):** Spark Structured Streaming med Auto Loader i ett notebook. Där behövs checkpoints och exactly-once.
- **Transformation (SQL, deklarativ):** dbt med medaljlager (staging, silver, gold). Modeller, tester, enhetstester, kontrakt
  och dokumentation ligger i samma kodbas som körs i CI.

## Varför dbt för transformationerna
- **Portabelt:** modellerna är SQL och bär inte med sig Databricks-specifik orkestrering. De kan flyttas till en annan motor.
- **Kvalitet som kod:** generiska och singulära tester, enhetstester med mockade indata, `contract: enforced` och `persist_docs`
  (beskrivningar skrivs som kommentarer i Unity Catalog).
- **Lineage:** `dbt docs` ger lineage-grafen inklusive exponeringen för dashboarden.
- **Inkrementell logik jag själv styr:** `MERGE` på inläsningstid med skydd mot out-of-order-leverans (se `silver/events.sql`).

## Alternativ
- **Lakeflow Declarative Pipelines:** mindre kod och inbyggd observability, men starkare inlåsning och sämre testbarhet av logiken
  utanför pipelinen. Ett rimligt val om hela teamet är Databricks-nativt.
- **Rena notebooks med Spark:** mest flexibelt men ingen standardiserad testning, dokumentation eller lineage.

## Konsekvenser
- Två verktyg i stället för ett (Auto Loader plus dbt). Gränsen är tydlig: *flytta* data med Spark, *forma* den med dbt.
- dbt körs som en `dbt_task` i samma Databricks-jobb, så orkestreringen är en och densamma.
