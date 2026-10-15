# Runbook

Hur plattformen drivs. Varje avsnitt är ett scenario: vad du ser, hur du tar reda på orsaken och vad du gör.

## Översikt

| Del | Var | Frekvens |
|---|---|---|
| Pipeline | Databricks-jobbet `seismo-pipeline` | varje timme |
| Watchdog | GitHub Actions `watchdog.yml` | varje timme (minut 17) |
| Dashboard | Streamlit Community Cloud | läser gold med 5 minuters cache |
| CI | GitHub Actions `ci.yml` | varje push och PR |

Jobbet har tre tasks: `poll_usgs` → `bronze_stream` → `dbt`. Tasken `dbt` kör tre kommandon i följd: kärnbygget, freshness och sist
AI-stegen. Kärndata är därför publicerad innan AI-steget körs, och ett LLM-fel påverkar den inte (se ADR 0005 och 0006).

## Larm: "Datafärskhet: SLA bruten"

Watchdog öppnar ett GitHub-issue med etiketten `data-sla` när senaste körning är äldre än 150 minuter, senaste körning
misslyckades eller karantäntabellen innehåller rader. Issuet stängs automatiskt när pipelinen är frisk igen.

**1. Hitta var det stannade.** Öppna jobbet i Databricks (Workflows → `seismo-pipeline`) och se vilken task som misslyckades. Eller fråga loggen:

```sql
SELECT polled_at, mode, windows, fetched, new_versions, status, error
FROM workspace.seismo_ops.poll_log ORDER BY polled_at DESC LIMIT 10;
```

**2. Åtgärda efter orsak.**

| Symptom | Trolig orsak | Åtgärd |
|---|---|---|
| `poll_usgs` misslyckas med HTTP 5xx/timeout | USGS tillfälligt nere | Vänta. Nästa körning tar igen luckan automatiskt (watermark). Inget att göra. |
| `poll_log.warnings` är större än 0 | Raderingsavstämningen (best effort) fick timeout hos USGS | Ofarligt. Nästa körning försöker igen. Larma först om det varar i många dygn. |
| `poll_usgs` misslyckas med HTTP 400 | USGS har ändrat API:et | Kör `pytest -m live`, som visar vilket kontrakt som brutits. Justera `pipeline/seismo_lib.py`. |
| `bronze_stream` misslyckas | Skadad checkpoint eller schema | Se "Bygg om bronze" nedan. |
| `dbt` misslyckas på ett test | Datakvalitet | Underkända rader finns i `seismo_ops.<testnamn>` (`store_failures`). Åtgärda data eller test. |
| `dbt` misslyckas på kontrakt | Oväntad schemaändring i gold | Det är kontraktet som gör sitt jobb. Uppdatera `gold.yml` medvetet. |
| `dbt` misslyckas i sista kommandot (AI) | LLM-endpoint nere eller kvot | Kärndata är opåverkad, eftersom den publicerades i första kommandot. Kör om `dbt build --select tag:ai` senare. |
| Inget körs alls | Schemat pausat eller kvoten slut | Kontrollera `schedule` i jobbet och Free Edition-kvoten. |

**3. Kör om manuellt.** `databricks bundle run seismo_pipeline`. Jobbet är idempotent: omkörning skriver inga dubbletter.

## Backfill (hämta historik eller laga en lucka)

```bash
databricks bundle run seismo_pipeline \
  --params mode=backfill,backfill_start=2026-09-01,backfill_end=2026-10-01
```

- Hämtar dagsfönster av händelsetid, ett fönster per fil, och **hoppar över fönster som redan finns**, så ett avbrutet backfill går att återuppta.
- Versioner som redan finns i bronze skrivs inte igen. Det går alltså säkert att köra om samma intervall.
- Backfill hämtar skalvens *senaste* version. Äldre revideringar av historiska skalv går inte att återskapa från USGS.

## Bygg om silver från bronze (replay)

Bronze är en komplett ändringslogg och aldrig sanningskälla att rätta i. Om en parser- eller transformationsbugg rättats:

```bash
cd dbt && dbt build --full-refresh --select events event_history --target prod
```

Ingen ny hämtning från USGS behövs.

## Bygg om bronze (sällsynt)

Landing-filerna är oföränderliga. Raderas checkpointen (`landing/_checkpoints/usgs_events`) och bronze-tabellen läser Auto Loader
om alla filer vid nästa körning. Rader utan `id`/`updated` hamnar i `usgs_events_quarantine`.

## Uppströms schemaändring (USGS lägger till eller ändrar fält)

1. Bronze påverkas **inte**: råpayloaden bevaras oförändrad.
2. Lägg till fältet i schemat i `dbt/models/staging/stg_usgs_event_versions.sql`.
3. Lägg till ett enhetstest i `staging.yml` och, om fältet ska ut i gold, ändra kontraktet i `gold.yml`.
4. Kör `dbt build --full-refresh --select stg_usgs_event_versions+` för att fylla i fältet bakåt.

## Kostnadskontroll

- **LLM:** `llm_batch_size` (standard 300) i `dbt_project.yml` begränsar nya anrop per körning.
- **Paus:** sätt `schedule_status=PAUSED` och kör `databricks bundle deploy`, eller pausa jobbet i Databricks.
- **Compute:** hela pipelinen går på serverless. Se `docs/cost-and-performance.md` för mätta siffror och kostnadsuppskattning.

## Miljöer och deploy

| Miljö | Schema | Schema (tid) | Hur |
|---|---|---|---|
| `prod` | `seismo_*` | varje timme | `databricks bundle deploy -t prod` |
| `dev` | `seismo_dev_*` | pausat | `databricks bundle deploy -t dev` |

Prova alltid ändringar i `dev` först (`databricks bundle run seismo_pipeline -t dev`). dbt väljer schema via variabeln `env`.

## Rotera hemligheter

Service principals och deras OAuth-secrets finns i Databricks. Tre ställen använder dem: GitHub Actions-secrets, Streamlit-secrets och
(vid behov) lokala `.env`-filer. Skapa en ny secret, uppdatera de tre ställena och radera den gamla.

| Service principal | Rättigheter | Används av |
|---|---|---|
| `seismo-public` | `SELECT` på gold-schemat, `CAN_USE` på warehouse | Dashboarden och watchdog |
| `seismo-ci` | `CAN_USE` på warehouse | CI och deploy |
