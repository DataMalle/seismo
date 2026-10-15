# ADR 0007: Datakontrakt och kvalitetsgrindar

**Status:** Beslutad

## Kontext
Konsumenter (dashboarden, och i ett verkligt team andra analytiker) förlitar sig på gold-tabellerna. En tyst schemaändring eller
ett kvalitetsproblem ska upptäckas vid byggtid, inte av en användare.

## Beslut
Kvalitet säkras i fem lager, från billigast till dyrast att upptäcka för sent:

| Lager | Mekanism | Effekt vid brott |
|---|---|---|
| Ingest | Karantäntabell för rader utan id/updated | Strömmen fortsätter, `quarantined_rows` larmar |
| Staging | Enhetstester med mockad indata (`unit_tests`) | CI/körning stoppar |
| Silver | `unique`, `not_null`, intervalltester, avstämning mot bronze, SCD2-invarianter | Körningen stoppar |
| **Gold** | **`contract: enforced`** (namn, typer, constraints) och `on_schema_change: fail` | **Körningen stoppar innan konsumenter påverkas** |
| Drift | Source freshness, watchdog-SLA, `llm_valid_ratio` | Varning eller GitHub-issue |

Underkända testrader sparas i `ops`-schemat (`store_failures`) för felsökning.

## Principer
- **Fail fast på kontrakt, varna på heuristik.** Schema och unikhet stoppar. Orimliga värden, LLM-kvalitet och färskhet varnar eller larmar.
- **AI-utdata valideras som all annan indata.** LLM-svar är opålitlig indata tills de passerat `is_valid` och dbt-testet.
- **Kontraktet är koden.** `gold.yml` är källan, och `persist_docs` skriver beskrivningarna till Unity Catalog.

## Konsekvenser
- Ett medvetet schemabrott kräver en explicit ändring av kontraktet, vilket syns i kodgranskningen.
- Fler tester ger längre körtid. Kärnan körs ändå på under några minuter eftersom datamängden är liten.
