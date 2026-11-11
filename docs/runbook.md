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

## Independent foundation

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

## Readable originals gate

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

Open the deployed Dataflow in Fabric, bind its OneLake Organizational account,
configure both Warehouse replace destinations, set that exact batch ID, publish,
refresh and inspect the row counts. Its M source is committed in `dataflow/`.
The helper/parameter queries must not be loaded as report tables.

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
Without Excel, occupancy has severity `Blocked`, not `Passed`.

The same on-demand run can be submitted and monitored with
`python scripts\run_dq.py`. This does not install a recurring schedule.

## Native orchestration completion

Follow build-plan modules 4 and 8 to bind and run native SQL ingestion and create
the master pipeline. The deployed `PL_Transform` invokes the transformation
notebook; running it before readable Excel ingestion is expected to fail at
`prd.usp_Load_FactUnitAvailability`. It is not a substitute for a complete master
run or for a verified failure notification.

## Lab site

```powershell
python -m pip install -r requirements-docs.txt
python -m mkdocs build --strict
```

`site/` is generated locally and excluded from Git. No public Pages deployment is
configured. Use the private repository or approved private hosting for the lab.
