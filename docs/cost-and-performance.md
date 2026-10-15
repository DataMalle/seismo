# Kostnad och prestanda

Allt här är **mätt** i det här projektet om inget annat anges, och det som är uppskattat är uttryckligen märkt som det, med antagandena
synliga. Ingen siffra är hämtad från minnet eller en broschyr: listpriser och förbrukningstakter kommer ur workspacets egna
tabeller (`system.billing.list_prices` och `system.billing.usage`).

Plattformen körs på Databricks Free Edition, där kostnaden för mig är noll men kvoterna är begränsade. Kostnadskalkylerna nedan visar därför vad
samma körning skulle kosta på en betald plan (AWS, region us-east-2, listpris), för att visa *var* pengarna går och vad som styr dem.

## Sammanfattning

| Fråga | Svar |
|---|---|
| Vad dominerar kostnaden? | **SQL-warehousens vakentid**, inte datamängd, lagring eller jobbcompute. Med timschema och 10 minuters auto-stop är warehouse vaket ca 12 av 60 minuter och står för ca 92 % av kostnaden. |
| Hur stort är datat? | Ca 0,5 MB i tabeller och 1,4 MB landing efter en vecka (ca 2 000 händelser). Lagring är försumbar. |
| Bästa tabelllayout? | **Liquid clustering.** ca 50 % snabbare tidsfrågor än ingen layout, och inga av partitioneringens nackdelar. |
| Småfilsproblemet? | Hanteras mest automatiskt av Predictive Optimization. 300 micro-batchar gav 21 filer, och `OPTIMIZE` gav 1 fil och 60 % mindre lagring. |
| Viktigaste kostnadsspaken? | Auto-stop på warehouse (10 till 1 minut) ger ca 66 % lägre månadskostnad vid timschema. Frekvens är den näst största. |

## 1. Datamängd

Mätt efter 7 dagars historik (bootstrap) plus några timkörningar:

| Tabell | Filer | Storlek | Layout |
|---|---|---|---|
| `bronze.usgs_events` (ändringslogg) | 4 | 0,22 MB | liten tabell, ingen klustring |
| `silver.events` | 1 | 0,11 MB | liquid clustering på `event_time` |
| `silver.event_history` (SCD2) | 1 | 0,04 MB | |
| `silver.event_locations` (LLM-cache) | 4 | 0,03 MB | |
| `gold_*` (sex tabeller) | 1 per tabell | 0,01 till 0,06 MB | |
| Landing-volym (rå NDJSON) | 4 filer | 1,37 MB | |

Ca 2 000 händelser per vecka, alltså cirka 100 000 per år. Även med flerfaldig historik rymmer allt sig i tiotals MB. Det är
varför **jag inte partitionerar** produktionstabellerna (se avsnitt 2) och varför lagring inte spelar någon roll för kostnaden.

## 2. Tabelllayout: benchmark

Syntetisk data med samma schema som `silver.events` (verkliga volymer är för små för att skilja layouterna åt). Tre layouter
jämfördes på två storlekar. Varje tid är medianen av fem körningar efter en uppvärmning, på serverless SQL.

- **q1:** antal händelser den senaste veckan (selektivt filter på tid, alltså klustringsnyckeln).
- **q2:** punktuppslag på `event_id` (filter på en kolumn som *inte* är klustringsnyckel).
- **q3:** aggregering per land och månad över hela tabellen.

**100 miljoner rader (ca 1,7 till 2,0 GB):**

| Layout | q1 tidsfilter | q2 punktuppslag | q3 helskanning | Filer | Storlek |
|---|---|---|---|---|---|
| a. Ingen layout | 1,74 s | 1,01 s | 2,05 s | 8 | 1 669 MB |
| b. Partitionerad per dag | 0,92 s | **1,47 s** | 2,11 s | **1 095** | **1 979 MB** |
| c. Liquid clustering | **0,86 s** | 1,05 s | **1,80 s** | 32 | 1 912 MB |

**10 miljoner rader (ca 170 till 200 MB):** alla tre layouter låg inom brus (0,75 till 1,3 s), eftersom frågorna domineras av ca 0,7 s fast
overhead. Partitionering per dag var redan här långsammast på q2 och q3 och gav 1 095 filer för 200 MB (ca 185 KB per fil).

**Vad det visar:**
- Både partitionering och klustring ger **data skipping** på tidsfiltret (ca 47 till 51 % snabbare än ingen layout vid 100 M rader).
- Partitionering per dag **betalar för det**: punktuppslaget blir 45 % långsammare (1 095 kataloger att öppna), lagringen växer 19 %
  och filantalet exploderar. Det är det klassiska överpartitioneringsfelet.
- Liquid clustering ger fördelen utan nackdelarna, och kräver ingen partitionshantering. Nyckeln kan ändras med `ALTER TABLE`.
- **Slutsats:** produktionstabellen `silver.events` använder liquid clustering på `event_time`.

**Begränsningar:** skillnaderna är under en sekund i absoluta tal, och effekten av data skipping växer med datamängden, så den skulle
vara mycket större vid terabyte-skala. Det har jag inte kunnat mäta här. Mätningarna är på serverless med viss varians mellan körningar.

## 3. Småfilsproblemet från micro-batchar

Strömmande ingest skriver många små filer. Experiment: 300 micro-batchar à 5 000 rader (liquid clustered tabell).

| | Filer | Storlek | q1 tidsfilter |
|---|---|---|---|
| Före `OPTIMIZE` | **21** | 3,3 MB | 0,83 s |
| Efter `OPTIMIZE` (13 s) | **1** | **1,3 MB** | 0,72 s |

- 300 batchar blev **21 filer**, inte 300. Predictive Optimization (på som standard i workspacet) och automatisk komprimering slår ihop
  småfiler i bakgrunden. Problemet är därför mycket mindre än teorin säger.
- Manuell `OPTIMIZE` gav ändå **60 % mindre lagring** (bättre komprimering av större filer) och 13 % snabbare frågor.
- Varje micro-batch tog ca 2 s att skriva. Vid ett timschema är det irrelevant, men det är skälet till att Seismo skriver *en* fil
  per körning i landing och låter Auto Loader läsa dem i en `availableNow`-körning istället för att strömma kontinuerligt.

## 4. Pipelinens körtid (mätt)

Stabil timkörning (efter bootstrap), summerat ur jobbets task-tider:

| Task | Tid |
|---|---|
| `poll_usgs` (extraktion) | 0,5 till 1,2 min |
| `bronze_stream` (Auto Loader) | 0,4 till 0,8 min |
| `dbt` (kärnbygge, freshness och AI-steg) | 2,9 min |
| **Totalt** | **3,5 till 3,9 min** (första laddningen med 7 dagars historik: 5,8 min) |

Två optimeringar kom ur mätningarna:
- **En enda dbt-task istället för tre.** Varje dbt-task betalade en egen miljöstart: freshness-kommandot tog 3 s men tasken 3,8 minuter.
  Genom att slå ihop dem sjönk den totala körtiden från över 7 till under 4 minuter.
- **Inkrementell `MERGE` och inkrementell extraktion.** Pipelinen läser bara det som ändrats sedan senaste watermark, så körtiden
  växer inte med historiken.

## 5. Kostnadsmodell

### Indata (från workspacets egna tabeller)

| Post | Värde | Källa |
|---|---|---|
| Serverless jobbcompute | 0,35 USD per DBU | `system.billing.list_prices` |
| Serverless SQL | 0,70 USD per DBU | `system.billing.list_prices` |
| Foundation Model-inferens | 0,07 USD per DBU | `system.billing.list_prices` |
| Förbrukning, **notebook-tasks** (Spark, `poll_usgs` och `bronze_stream`) | **ca 6,5 DBU per timme** | Seismos egna fakturaposter: 0,133 DBU för 1,2 min och 0,126 DBU för 0,9 min notebook-tid plus dbt |
| Förbrukning, **dbt-tasks** på jobbcompute | **ca 0,6 DBU per timme** (nästan inget) | Seismos egna poster: 0,023 till 0,038 DBU för 2,1 till 2,9 min. dbt-tasken orkestrerar bara, arbetet sker på warehouse |
| Förbrukning, SQL warehouse (2X-Small) när den är vaken | **4 DBU per timme** | antagande enligt Databricks storlekstabell, konsistent med mätta timposter på 0,5 till 0,75 DBU (=ca 8 till 11 minuters vakentid) |
| Warehouse auto-stop | 10 minuter | `databricks warehouses get` |
| Aktiv dbt-tid per körning | ca 2,4 min | jobbloggar (98 s + 3 s + 42 s) |
| Notebook-tid per körning | ca 0,9 till 1,2 min | task-tider (`poll_usgs` plus `bronze_stream`) |
| dbt-tid per körning | ca 2,9 min | task-tid |

### Per körning

- Jobbcompute: notebooks ca 1,0 min × 6,5 DBU/h = 0,11 DBU, dbt ca 2,9 min × 0,6 DBU/h = 0,03 DBU. Totalt ca **0,15 DBU** (0,05 USD).
- Warehouse: aktiv 2,4 min plus **auto-stop-svansen** (warehouse väntar 10 minuter på nästa fråga innan den stängs av).

### Scenarier (USD, listpris, per dygn och per månad)

| Scenario | Körningar/dygn | Warehouse vaken/dygn | USD/dygn | USD/månad |
|---|---|---|---|---|
| **A. Nuvarande: varje timme, auto-stop 10 min** | 24 | 5,0 h | ca 15 | **ca 455** |
| B. Varje timme, **auto-stop 1 min** | 24 | 1,4 h | ca 5,1 | **ca 150** |
| C. Var fjärde timme, auto-stop 10 min | 6 | 1,2 h | ca 3,8 | ca 115 |
| D. Var fjärde timme, auto-stop 1 min | 6 | 0,3 h | ca 1,3 | ca 40 |
| E. **Var 15:e minut**, auto-stop 10 min | 96 | 24 h (aldrig av) | ca 72 | ca 2 170 |

Beräkning: `körningar × 0,15 DBU × 0,35` plus `vaken timmar × 4 DBU × 0,70`. LLM-inferensen är försumbar (se nedan) och lagring ännu mer.

**Vad det visar:**
1. **Warehouse-tiden dominerar.** I scenario A står warehouse för ca 92 % av kostnaden, trots att den bara arbetar ca 2,4 minuter per körning. Resten är
   väntan på auto-stop. Jobbcompute är nästan en avrundningsfråga.
2. **Auto-stop är den billigaste spaken:** 10 till 1 minut sänker kostnaden med ca 66 % utan att ändra något annat. Priset är en något
   längre kallstart för dashboarden (ca 30 till 60 s för första besökaren), som appen hanterar med förvärmning.
3. **Frekvens är en kostnadsbeslut, inte en teknisk detalj.** Med körningar tätare än auto-stop (scenario E) sover warehouse aldrig, och kostnaden blir
   ca fem gånger högre än A, för data som i värsta fall är 45 minuter färskare. USGS-data ändras sällan så snabbt att det motiverar det.
4. **Vald avvägning:** timschema, eftersom färskhet inom en timme räcker för användningsfallet. På en betald plan skulle jag ändra auto-stop till 1 minut först.

### Andra kostnader

- **LLM (Foundation Model API):** workspacets samlade inferensförbrukning var 0,144 DBU på den mest aktiva dagen (alla projekt), alltså ca 0,01 USD.
  Seismos 531 unika ortbeskrivningar är en engångskostnad på någon cent, tack vare cachen per ort (ADR 0006). Stabilt läge: bara nya orter, en handfull per dygn.
- **Lagring:** 0,5 MB nu. Vid ett års historik (ca 100 000 händelser) uppskattar jag under 100 MB, alltså i storleksordningen **0,002 USD per månad**
  (S3 standard, ca 0,023 USD per GB och månad).
- **Datatrafik ut:** noll i förbrukningstabellerna (`INTERNET_EGRESS`).

### Validering mot Seismos egna fakturaposter

Förbrukningstabellerna släpar ca 2 timmar, så prod-körningarna syns inte än när jag skriver det här. Men Seismos **dev-jobb** hade åtta körningar
bokförda (0,76 DBU totalt), och de användes för att validera kalkylen. Det **ändrade den**: min första kalkyl antog 4,2 DBU/timme för all
task-tid (en takt jag härlett ur ett annat projekts jobb) och överskattade jobbkostnaden med ca 1,8 gånger. De riktiga posterna visade att
notebook-tasks kostar ca 6,5 DBU/timme medan dbt-tasks är nästan gratis på jobbcompute (ca 0,6 DBU/timme), eftersom de bara orkestrerar.
Kalkylen ovan bygger på de riktiga takterna. Slutsatsen blev dessutom starkare: warehouse står för ca 92 % av kostnaden, inte 86 %.

Så här verifierar du kalkylen mot Seismos prod-poster när de dykt upp:

```sql
SELECT usage_metadata.job_run_id, ROUND(SUM(usage_quantity), 3) AS dbus
FROM system.billing.usage
WHERE usage_metadata.job_id = <seismo-pipeline job id>
GROUP BY 1 ORDER BY MIN(usage_start_time) DESC;
```

Warehouse-delen går inte att attribuera per jobb (warehouse delas med andra projekt), så den bygger på den dokumenterade storleken
och mätta timposter. Det är den mest osäkra delen av kalkylen.

## 6. Vad jag skulle göra annorlunda i produktion

- Sätta **auto-stop till 1 minut** och en dedikerad warehouse för pipelinen, så att dashboardens frågor inte håller den vaken.
- Överväga att köra transformationerna som **Spark SQL på jobbcompute** istället för på en SQL warehouse. Då försvinner auto-stop-svansen helt,
  till priset av att dbt-adaptern och testerna måste anpassas.
- Sätta **budgetlarm** på `system.billing.usage` (en daglig kontroll i watchdog-workflowet).
- Mäta lagrings- och filutveckling över månader och köra `OPTIMIZE` och `VACUUM` med schema om Predictive Optimization inte räcker.

## Begränsningar

- Kostnaderna är **uppskattningar på listpris** och avser inte vad Free Edition faktiskt debiterar (noll). Rabatter, committed use och olika regioner ändrar siffrorna.
- Warehousens 4 DBU per timme är ett antagande enligt Databricks storlekstabell som stämmer med mätta timposter, men det är inte en direkt mätning av den här warehouse.
- Benchmarken är syntetisk och mätt på serverless med viss körningsvarians. Absoluta skillnader är under en sekund.
- Dashboardens egna frågor (varje besök kan väcka warehouse) ingår inte i kalkylen. Cachen på fem minuter begränsar dem.
