# ATL Housing - Households Served

This workshop implements the supplied execution guide against the existing
`ATLHousing` database and `fabridemo/atldemo` storage. It never runs the supplied
destructive loader, regenerates workbooks or overwrites source data.

**Core end-to-end master completed on 2026-11-11 UTC.** Native SQL and real Gen2
ingestion, transformations, Spark DQ, model framing and reconciliation all
succeeded. All 17 metrics matched across 108 Warehouse program-months and 27
Direct Lake model keys. The actual HT1-HT10 Power BI report is deployed.
Security, fiscal-calendar, alert/schedule and optional environment gates remain
explicitly separate from core data acceptance.

## Environment

| Component | Approved existing resource |
|---|---|
| Workspace | ATLhousing, `4d77b5c8-d96f-41df-83e1-954c582336d8` |
| Capacity | maddyscapcity, existing F8 in West US 3 |
| SQL | `sql-atlhousing.database.windows.net`, database `ATLHousing`, schema `hs` |
| Files | `fabridemo`, container `atldemo`, prefixes `excel/` and `csv/` |
| Lakehouse | `LH_ATL_Landing` |
| Warehouse | `WH_ATL_HS` |
| Semantic model | `SM_HouseholdsServed`, explicit Direct Lake on OneLake |
| Report | `RPT_MTW_Detail_HT`, actual PBIR |
| Ontology | `ONT_ATL_Housing`, 11 analytical entities / 11 source relationships |
| Data agent | `DA_ATL_Housing`, published model-grounded aggregate Q&A with ontology context |

Reuse the existing capacity; do not create or resize paid resources. CSVs are
bootstrap/validation alternatives, not an additional ingestion feed on top of SQL.
AnswerKey is validation/control data, never the source of report facts.

## Working architecture

```text
PL_Master_HouseholdsServed (manual, typed reporting month)
  -> PL_Ingest_SQL
       metadata Lookup -> ForEach (4)
       Azure SQL (read-only) -> current-run OneLake Parquet -> WH.stg
  -> DF_Excel_HouseholdsServed (real Gen2)
       24 original XLSX files, approved immutable batch -> typed WH.stg
  -> PL_Transform / NB_Transform
       effective-dated dimensions + household / availability / supportive facts
  -> NB_DQ_Checks
       actual Spark structural checks + retained seeded warnings
  -> NB_Reconcile
       108-key Warehouse comparison -> model framing -> 27-key DAX comparison
  -> master success log

SM_HouseholdsServed -> RPT_MTW_Detail_HT
                       month / categories / inventory / supportive / DQ / definitions
                   -> ONT_ATL_Housing -> DA_ATL_Housing
                        business context + original model measures, not another fact feed
```

Every stage has an explicit failure branch; failures are not converted into
success. The local checkpoint path remains available for immutable replay, but it
is no longer the only implemented ingestion path.

See the [detailed guide-aligned build plan](build-plan.md),
[manual attendee workshop with screenshots](workshop-attendee-guide.md),
[execution runbook](runbook.md), [actual deployment evidence](deployment-status.md)
and [security/reporting gates](security-reporting.md).

The manual is also available as [PDF](downloads/ATL-Housing-Workshop-Manual.pdf)
and [editable Word](downloads/ATL-Housing-Workshop-Manual.docx). The
[offline lab pack](downloads/ATL-Housing-Manual-Workshop-Pack.zip) includes manual
editor assets and the unchanged supplied synthetic workbooks and controls.
Credentials and private session data are excluded. M15-M16 add the requested ontology/data-agent
extension, with numbered UI actions, real screenshots, 15 sample questions and
nine independently executed DAX answer baselines. Ontology is preview; source
authorization and actual Viewer RLS acceptance remain separate from AI instructions.

## Local lab

```powershell
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
python -m pip install -r requirements-docs.txt
python -m mkdocs build --strict
```

GitHub Pages is intentionally not configured: public repository approval does not
enable separate website hosting. The approved synthetic workbooks are distributed
inside the offline ZIP; other local source data, credentials and browser profiles
remain excluded. No recurring schedule is enabled.
