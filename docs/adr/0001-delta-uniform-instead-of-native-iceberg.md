# ADR 0001: Delta med UniForm istället för native Iceberg

**Status:** Beslutad

## Kontext
Plattformen ska använda ett öppet tabellformat så att data inte låses in hos en motor. Iceberg är det format fler motorer
(Trino, Snowflake, DuckDB, Athena) har gemensamt, medan Delta har bäst stöd i Databricks, där jobb, Auto Loader, `MERGE` och
Predictive Optimization är byggda kring det.

## Beslut
Tabellerna lagras som **Delta** med **UniForm** påslaget (`delta.universalFormat.enabledFormats = 'iceberg'`). Databricks skriver
då Iceberg-metadata vid varje commit, och tabellerna kan läsas som Iceberg av andra motorer utan kopiering.

Jag verifierade i det aktuella workspacet att UniForm fungerar (tabellmetadata visar `Delta Uniform Iceberg` med en
`metadata.json`-plats) innan jag valde det.

## Alternativ
- **Native Iceberg med egen katalog (t.ex. REST/Nessie/Polaris):** mest portabelt, men kräver att jag driftar en katalog och
  ger sämre stöd för `MERGE`, liquid clustering och automatisk optimering i Databricks.
- **Bara Delta:** enklast, men låser läsare till Delta-kompatibla motorer.

## Konsekvenser
- Jag behåller Databricks styrkor (strömmande skrivningar, MERGE, automatisk compaction) och ger Iceberg-läsare tillgång.
- UniForm är en *läs*-brygga: skrivningar sker alltid via Delta. Det är en medveten begränsning.
- Vissa Delta-funktioner begränsar UniForm (t.ex. kolumnmappning måste vara `name`). Dessa ställs in av `delta.enableIcebergCompatV2`.
- Byter jag senare till native Iceberg är datafilerna redan Parquet, så migreringen är i huvudsak en metadataoperation.
