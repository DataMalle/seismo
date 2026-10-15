# ADR 0005: Databricks Jobs för körning, GitHub Actions för CI och larm (inte Dagster/Airflow)

**Status:** Beslutad, med en tydlig migreringsväg

## Kontext
Asset-baserad orkestrering (Dagster) eller Airflow är vanliga val för pipelines i produktion. Plattformen ska dock köra
dygnet runt utan kostnad, och en Dagster- eller Airflow-instans kräver en värd som alltid är på.

## Beslut
- **Körning:** ett Databricks-jobb med schema varje timme och beroenden mellan tasks (extraktion, bronze, dbt).
  Jobbet har `max_concurrent_runs: 1` och kö, så att watermark och `MERGE` aldrig tävlar.
- **CI:** GitHub Actions kör lint, enhetstester och `dbt parse --warn-error` på varje push och PR.
- **Larm:** ett *separat* watchdog-workflow läser `gold_pipeline_health` och öppnar ett GitHub-issue när färskhets-SLA:n (150 min, två missade körningar)
  bryts. Det stänger issuet när pipelinen är frisk igen.

## Varför larmet ligger utanför jobbet
En pipeline som stannat kan inte larma om sig själv. Watchdog-workflowet körs av en annan scheduler på en annan plattform och
upptäcker därför både misslyckade körningar *och* att jobbet inte körs alls.

## Alternativ
- **Dagster:** hade gett asset-lineage och sensorer. Avstod eftersom det kräver ständig värd. Modellerna är redan uppdelade i
  assets (dbt-modeller plus ingest), så en senare migrering är att linda dem med `dagster-dbt`.
- **Airflow:** samma värdkrav och mer drift för en pipeline av den här storleken.

## Konsekvenser
- Allt körs på gratisnivåer och är reproducerbart med `databricks bundle deploy`.
- Orkestreringen är enklare men har färre funktioner (inga sensorer, ingen backfill-UI). Backfill görs med jobbparametrar.
- GitHub Actions cron är best-effort och kan fördröjas. Det räcker för ett SLA mätt i timmar, men vore otillräckligt för sekunder.
