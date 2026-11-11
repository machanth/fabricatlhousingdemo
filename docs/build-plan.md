# Detailed build plan

## 1. Prerequisites and resource guardrails

**Objective:** implement the supplied Households Served guide without replacing
existing resources or modifying the populated source.

Authenticate using Azure CLI and select the configured subscription. Deployment
checks the exact subscription, tenant, workspace and capacity. Source SQL uses
Entra token authentication and ODBC Driver 18, with encryption and certificate
validation. No credentials are committed or written to state files.

Checkpoint: `python scripts\deploy.py`. Verify the Lakehouse, Warehouse, three
schemas, ten active full-load metadata rows and the 5,844-row date dimension.
The guide's sample SQL database names are superseded by the user's explicit
choice of `ATLHousing`, not `sql-atlhousingnew1`.

## 2. Source inspection and SQL landing

**Objective:** capture the actual source schema and an immutable recoverable run.

`scripts\checkpoint.py` reflects the ten allowlisted `hs` tables and `hs.AnswerKey`,
reads them under a single serializable transaction, and records rows, column types
and SHA-256 hashes. Source transactions are read-only and rolled back after reading.
The supplied loader is intentionally not included as an executable deployment step
because it truncates every source table.

`scripts\landing.py --sql-checkpoint` writes those files to
`Files/landing/sql/<run-id>/`, verifies destination sizes, and uploads the completion
manifest last. Reusing the run ID verifies existing content instead of overwriting.
Checkpoint files contain synthetic data and stay out of Git.

The verified source counts are SourceSystem 2, ProgramType 9, VoucherType 5,
ActionType 5, IncomeSource 6, Property 127, Unit 25,794, UnitLocation 25,794,
Member 240,819, FamilyMember 48,021 and AnswerKey 108.

## 3. Warehouse staging and metadata

**Objective:** replay a checkpoint without appending duplicate source observations.

`--load` converts the SQL checkpoint into typed, immutable Parquet files in OneLake,
creates compatible Fabric staging tables from reflected SQL types and uses native
`COPY INTO` to replace each table transactionally, checking its exact row count
before commit and again after all tables are published.
`mtd.PipelineRunLog` records stage status and counts. All tables start as full loads;
no unsupported incremental watermark is implied by monthly snapshot dates.

`mtd.FilesToLoad` records the approved Excel run, file, month, target and hash.
Historical run folders must not be recursively combined in later refreshes.

No global truncate procedure is used by the local runner: per-table transactional
replacement keeps the prior table intact if its replacement fails. Serialize
ingestions and transformations; a local process lock prevents competing CLI
publishers. Cross-host publishing still requires orchestration-level serialization.

## 4. Metadata-driven Data Factory ingestion

**Objective:** replace the catch-up runner with the guide's native
`PL_Ingest_SQL` pattern.

**Pending connection binding:** Fabric has no matching reusable connection for the
selected source. In Manage connections and gateways, create an Azure SQL connection
to the configured server/database using Organizational account; test it, and select
it in the pipeline. Do not copy credentials from unrelated existing connections.

Create `PL_Ingest_SQL` with Warehouse Lookup on:

```sql
SELECT SourceSchema,SourceTable,TargetTable,LoadType,WatermarkColumn
FROM mtd.TablesToCopy WHERE IsActive=1;
```

Disable First row only; ForEach items is
`@activity('TablesToCopyLookup').output.value`, batch count **4**. Each Copy reads
the allowlisted SQL source and replaces its matching `stg` table. Prefer loading
run-specific staging first and promoting only after all ten copies/counts succeed;
never transform a partially completed run. Load `hs.AnswerKey` separately as control
data. Add failure logging and a terminal Fail activity so logging does not turn a
failed ingestion into a successful parent run.

Acceptance: ten copied tables plus the separately copied answer key reconcile to
the source checkpoint; rerun does not change observation counts. This native
ingestion pipeline is **not deployed/verified** by the local SQL checkpoint runner.

## 5. Original Excel preflight and Dataflow Gen2

**Objective:** use the user's original files, not regenerated substitutes.

**Update:** all 24 user-supplied unencrypted originals passed preflight and were
landed directly from the attached local folder. The original encrypted storage
files were not changed. Gen2 binding/refresh remains pending.
Run `--excel-preflight` to validate all filenames, months,
sheet names, required columns, nulls and grain. Inspect replacement schemas before
accepting the generator's mapping.

After preflight succeeds, `--land-excel` uploads the same verified bytes to a new
`Files/landing/excel/<run-id>/` folder, registers `mtd.FilesToLoad`, and writes the
completion manifest. It never overwrites the storage source.

The deployed `DF_Excel_HouseholdsServed` contains M queries for:

| Query | Expected original workbook shape |
|---|---|
| UnitAvailability | ReportMonth, Program, TotalUnits, AvailableUnits, LIHTCUnits |
| SupportiveHousing | ReportMonth, HouseholdID, Program, SupportType |

Bind the OneLake organizational connection, set `pApprovedBatch` to the approved
run ID, configure Warehouse **replace** destinations `stg.UnitAvailability` and
`stg.SupportiveHousing`, publish and refresh. Retain `SourceFile` and derive integer
`EffectiveDateKey`; use only that run, not all historical landing folders.

Acceptance: exactly 12 files of each kind, no duplicate program-month availability
or household-program-month roster keys, every roster row matches its own program.
A missing workbook must fail refresh rather than silently produce partial totals.

## 6. Production transformations

**Objective:** preserve observation grain and valid historical dimension versions.

Run `prd.usp_Load_Dimensions`, then `prd.usp_Load_FactHouseholdSnapshot`.
Run `prd.usp_Load_FactUnitAvailability` only after successful Excel ingestion.
Production excludes names, DOB, ethnicity, citizenship, income and street addresses.

Important corrections to the guide's summary tables:

- Unit has **PropertyID**, not PropertyKey; resolve the property version using the
  snapshot date and inclusive SCD2 boundaries.
- FamilyMember has **HouseholdID**, not MemberKey; do not directly join people to
  every monthly fact. Member already supplies aide-excluded demographic counts.
- Snapshot grain is **household-program-month**, preserving planted second-program
  observations; Households is a row count, not a distinct-household count.
- Elderly takes precedence over Disabled, then Workforce; child count above zero
  means With children. Preserve missing-unit observations with key `-1`.
- Property history is supplied SCD2. Unit has only one source version per key;
  expose its observed validity interval but **do not invent unobserved SCD2 history**.
- Supportive membership joins month + household + its own program, preventing the
  planted second-program observation from multiplying support counts.
- Availability comes from Excel, excludes LIHTC, and applies only to unit-based
  programs. Preserve negative vacancy and voucher nulls.

Structural errors raise exceptions. Transactional replacements protect each
production table group. Reruns must produce identical keys and metrics.

## 7. Data quality and reconciliation

**Objective:** distinguish expected teaching defects from structural failures.

Views detect duplicate-program household-months, missing units and over-occupancy.
`NB_DQ_Checks` uses PySpark to read Warehouse facts/staging and writes rule counts,
severity and run ID into `prd.DQ_Results`. Occupancy is explicitly Blocked while
Excel is absent. Invalid dates, overlapping SCD2 intervals or invalid current-row
counts fail the notebook.

`scripts\validate.py` independently recomputes all nine household metrics and
full-outer-compares all 108 program-month keys with `hs.AnswerKey` copied to staging.
`--include-excel` adds the eight supportive/inventory/vacancy metrics (17 total).
Null is not zero. Extra and missing keys fail validation.

Acceptance: all SQL household comparisons pass now; after Excel, all 17 metrics
pass for every month. Negative vacancy must identify exactly MIXED_HF and MIXED_RAD.
Do not treat answer-key values as a source for missing Excel observations.

## 8. Orchestration and operations

**Objective:** native parent/child monitoring without false unattended readiness.

`PL_Transform` is deployed with `NB_Transform`; Excel gating remains active.
After binding and validating ingestion/Dataflow, create
`PL_Master_HouseholdsServed`: SQL ingestion -> approved Excel landing/Dataflow ->
PL_Transform -> DQ -> full reconciliation -> semantic-model framing.

Add EffectiveMonth for report selection or explicitly validated partial-load
handling; current implementation is a full 12-month load and does not pretend this
parameter performs incremental ingestion. Block overlapping runs.

Choose a Teams channel or Outlook recipient with the user, configure the failure
path, deliberately fail a safe test activity, and verify actual receipt with run ID
and failed activity. Prepare a disabled 06:00 Eastern schedule with daylight-saving
aware time zone; enable it only after user confirmation and a successful dry run.

## 9. Date dimension, Direct Lake and reporting

DimDate covers 2015-01-01 through 2030-12-31 (5,844 dates), ISO week, month, quarter,
labels, month start and locale-independent weekend flags. **AgencyFiscalYear is
NULL until ATL confirms the convention**. Do not assume calendar year is fiscal year.
Copilot availability must be checked independently of the F8 capacity.

The complete model/report are **blocked, not deployed**. Create explicit
`SM_HouseholdsServed` in Direct Lake after data gates pass; use the provided
measures, RLS filter, reconciliation query and report specification.
See [security and reporting](security-reporting.md) for exact relationships and
acceptance. Keep source PII and answer-key controls out of the model.

## 10. Governance, shortcuts and presenter modules

Use approved Entra groups and approved existing sensitivity labels only. No roles,
labels or users have been invented. Git code is preserved in the private repository;
Fabric Git binding requires account authorization. Do not publish Pages publicly.

An ADLS Gen2 shortcut to `fabridemo/atldemo` is supported by the HNS account. Create it
only after binding an approved connection; demonstrate read-in-place, without
changing the primary run-scoped ingestion feed or double-counting files.

Azure SQL mirroring remains an optional prerequisite/approval-gated module. Do not
change server identity, source configuration, or a Member row to demonstrate CDC.
Databricks Unity Catalog belongs in the separate presenter environment: none was
supplied; do not reuse unrelated discovered connections or create a paid workspace.
Deployment pipelines/Test/Prod workspaces also require approval and capacity review.

## Completion gates

The demo is complete only after: readable originals, native ingestion/Gen2 refresh,
17-metric reconciliation, all DQ checks, explicit Direct Lake framing, three-month
model reconciliation spanning July SCD changes, Viewer RLS test, approved labels,
actual report performance measurement under three seconds, and a verified failure
alert. Unattended scheduling and public documentation remain separate approvals.
