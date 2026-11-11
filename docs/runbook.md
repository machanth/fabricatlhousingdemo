# Runbook and checkpoints

## Authenticate once

Use an account authorized for the approved subscription, source SQL, source
storage and existing Fabric workspace. No SQL passwords, storage keys, SAS tokens
or service-principal secrets are required by the implemented runner.

```powershell
az login --tenant f35d82dd-ecb9-45ea-91ab-d89b40790e3e
az account set --subscription c6c48e05-64f0-4906-a23b-96123ad4e0ae
python -m pip install -r requirements.txt
```

ODBC Driver 18 must be installed separately on the machine. The runner refuses a
different configured account or capacity; fix the selected account rather than
editing the safety checks.

## Run the deployed end-to-end demo

Open `PL_Master_HouseholdsServed` in the approved ATLhousing workspace, set
`EffectiveMonth` to a control month such as `2025-01`, and choose **Run**.
Monitor the actual run to terminal **Completed**; do not treat submission or
successful individual previews as completion.

The chain is typed month validation -> native SQL -> real Gen2 Excel -> three
Warehouse transforms -> Spark DQ -> Warehouse/model reconciliation and model
framing -> success log. A stage failure writes its failure log and explicitly
fails the master. Inspect the linked child run, not only the parent status.
`EffectiveMonth` is reporting/control context: this demo performs full loads of
all approved months, not an incremental month-filtered source load.

**Run one publisher at a time**, including local runners and Fabric pipelines.
The local publisher lock does not coordinate Fabric service runs. Do not start
another master, SQL pipeline, Gen2 refresh or local loader during an active run.
No recurring schedule is enabled.

After completion:

```powershell
python scripts\validate.py --include-excel
python scripts\validate_model.py
```

Expect all 17 metrics/all 108 Warehouse keys and 27 model keys (January, July,
December) to reconcile. Open the saved report; its default month is January.
Reset to default if a previous viewer's persistent filters override the author.

For a safe negative test, run the master with `EffectiveMonth=2025-13`.
It must fail validation before ingestion, log failure and finish **Failed**.
This tests pipeline handling only; outbound notification requires an approved
destination/connection and a separate delivery test.

## Foundation deployment and checkpoint alternative

```powershell
python scripts\deploy.py
python scripts\checkpoint.py --load
python scripts\landing.py --sql-checkpoint
python scripts\transform.py
python scripts\validate.py
python scripts\deploy_items.py
```

Run these **sequentially**, never run two publishers. Checkpoint loading uses native
Warehouse `COPY INTO` from typed SQL-derived Parquet in OneLake (no storage secrets
or source-CSV second feed). This optimized path replaces the initial slow ODBC
batch implementation. Do not start transformations before it finishes.
Local state is in `.state`; immutable cloud checkpoints are in OneLake
`LH_ATL_Landing/Files/landing/sql/<run-id>` and typed copies in
`Files/landing/sql_parquet/<run-id>`. To replay the latest checkpoint without
rereading source SQL, run `python scripts\bulk_load.py`.

The runner initially loads all source rows, not just one month. It does not reload
SQL from the storage CSVs. If a stage fails, the exception is visible and its
Warehouse transaction rolls back. Preserve the checkpoint manifest for diagnosis;
the staging runner can be rerun to capture and replace from a new complete source
checkpoint.

`deploy.py` reuses named items and creates missing objects; it does not overwrite
existing item definitions. `deploy_items.py` likewise preserves existing
definitions. To change an already-deployed notebook/Dataflow/pipeline, review its
live definition and use the Fabric editor or explicit updateDefinition API after
checking for other edits. Never assume a rerun pushed a local definition change.

### SQL acceptance checkpoints

```sql
SELECT COUNT(*) AS ActiveTables FROM mtd.TablesToCopy WHERE IsActive=1; -- 10
SELECT COUNT(*) AS Dates, MIN([Date]) AS FirstDate, MAX([Date]) AS LastDate
FROM prd.DimDate; -- 5844, 2015-01-01, 2030-12-31
SELECT Stage,Status,[RowCount],ErrorMessage FROM mtd.PipelineRunLog
ORDER BY StartedAt DESC;
SELECT COUNT_BIG(*) FROM prd.FactHouseholdSnapshot; -- 240819 for current source
SELECT COUNT(*) FROM prd.vw_HouseholdMetrics; -- 108
SELECT COUNT(*) FROM prd.vw_DQ_DuplicatePrograms;
SELECT COUNT(*) FROM prd.vw_DQ_MissingUnits;
```

Counts are dataset-specific observations, not a substitute for metric
reconciliation. `validate.py` must compare every expected program-month and every
SQL household metric.

## Original-workbook intake

The supplied readable originals are already landed as approved batch
`9ebe0cfa-3ef7-4cff-bacd-49eaa9cbd5a5`. Gen2 is bound, published and has refreshed
successfully. It reads only this immutable batch; it never recursively combines
historical landing folders. Original encrypted storage files remain unchanged.

For a new approved original batch, use the same preflight/landing procedure:

The preflight command deliberately exits nonzero while any workbook is encrypted:

```powershell
python scripts\landing.py --excel-preflight
```

Once the user supplies readable copies of the original 24 files at the agreed
storage location, inspect them and rerun. Do not generate substitute workbooks.
When all files are readable:

```powershell
python scripts\landing.py --land-excel
```

This preflights every workbook **before any destination write**, checks source
hashes again during upload, creates a new run folder, and registers the 24 files.
The output contains the approved batch UUID for Dataflow `pApprovedBatch`.

If readable originals are supplied as a local folder rather than replacing blob
storage, append `--local-excel-directory 'C:\path\to\out\excel'` to either preflight
or landing command. The same strict 24-file checks apply; files are copied directly
to a new OneLake batch without altering local originals or existing source blobs.

Review the Dataflow's OneLake Organizational account binding, set the exact new
batch ID, retain both typed Warehouse Replace destinations and explicit mappings,
publish, refresh and inspect the row counts. Current observed counts are 72
availability and 20,752 supportive rows. Do not load helper, parameter or hidden
destination queries as report tables.

`dataflow\DF_Excel_HouseholdsServed.Dataflow` contains the real working exported
M and connection/destination metadata. The top-level `.pq` remains the guarded
initial authoring template, not a substitute for bound destination annotations.
To preserve reviewed UI changes or explicitly reapply this environment's bindings:

```powershell
python scripts\deploy_dataflow.py --export
# Review the diff before overwriting a live definition:
python scripts\deploy_dataflow.py --apply
```

Reapplication is not proof of refresh success. Connection IDs and OneLake paths
are specific to this approved environment; authenticate/rebind deliberately before
using exports elsewhere. No credentials are embedded in these files.

Only after that refresh succeeds:

```powershell
python scripts\transform.py --include-excel
python scripts\validate.py --include-excel
```

The first command creates the all-metrics view as well as facts. All 17 metrics and
all months must reconcile, including zero support counts, negative vacancy and
null voucher inventory. A successful preflight alone does not mean Gen2 ingestion
or downstream acceptance succeeded.

## DQ notebook

Open `NB_DQ_Checks` and run after the household fact and DQ views exist. It reads
Warehouse tables with the built-in Spark connector and appends run-scoped checks
to `prd.DQ_Results`. The SQL connection uses the in-memory NotebookUtils `pbi` token,
whose Warehouse SQL authentication was verified separately.

Expected seeded defects are warnings; malformed dates/SCD2 intervals are errors.
Without Excel, occupancy has severity `Blocked`, not `Passed`. With the approved
batch the scope is `SQL+Excel`; exactly MIXED_HF and MIXED_RAD account for 24
negative-vacancy program-months.

The same on-demand run can be submitted and monitored with
`python scripts\run_dq.py`. This does not install a recurring schedule.

## Redeploy reviewed artifacts

The native SQL connection is `ATL_HS_SQL_Source`, organizational OAuth, restricted
by its connection details to `sql-atlhousing.database.windows.net;ATLHousing`.
The generated SQL pipeline resolves ten approved active Full metadata entries,
ForEach concurrency 4, immutable current-run Parquet, transactional staging
publication/count checks and a separate AnswerKey control copy.

```powershell
python scripts\deploy_ingestion.py
python scripts\deploy_model.py
python scripts\deploy_report.py
python scripts\deploy_master.py
```

These commands explicitly update their named definitions, unlike the preserving
foundation deployer. Review changes/live edits first. The model command exports
and configures real TMSL, removes unnecessary source identifiers and installs
measures/relationships/role; it does not assign users or fabricate an approved
ProgramScope map. The report command generates actual PBIR, including the saved
single-month filter, expanded category hierarchy, metric rows and per-cell red
negative vacancy. The master command also deploys `NB_Reconcile`.

No automatic schedule, outbound alert, sensitivity label, mirror or external
Databricks environment is created by these commands.

## Lab site

```powershell
python -m pip install -r requirements-docs.txt
python -m mkdocs build --strict
```

`site/` is generated locally and excluded from Git. No public Pages deployment is
configured. Use the private repository or approved private hosting for the lab.
