# Deployment evidence and remaining gates

Observed in the existing ATLhousing workspace, 2026-11-11 UTC. This is a partial
SQL/Fabric foundation, **not an end-to-end completion certificate**.

## Created items

| Item | ID | Actual state |
|---|---|---|
| LH_ATL_Landing | b3fdd7c1-498f-45f6-82a6-3a1ed9fa2ae9 | SQL JSON and typed Parquet checkpoints landed, immutable run manifest |
| WH_ATL_HS | 81bc6f59-4979-447b-aa5c-041c0e52ced2 | Metadata, 11 staging tables, production dimensions, household snapshot, date dimension and DQ views |
| NB_DQ_Checks | a242b7fd-2ee8-4e71-af03-d5d385405291 | Executed successfully in Fabric |
| NB_Transform | 860b3aa7-9d96-4d41-b59f-fa75dfe9fe1f | Definition deployed; full execution intentionally gated by Excel |
| DF_Excel_HouseholdsServed | 6576d03c-9711-4039-91a0-b990c66e7760 | Gen2 M authoring definition deployed; connection/destinations/publish/refresh pending |
| PL_Transform | 39bf0d33-81b3-4b1a-866d-6998424a1c98 | Notebook activity definition deployed and read back; not claimed as a successful complete transform run |

Fabric also created its managed Dataflow staging Lakehouse/Warehouse on the
existing capacity. No new Azure capacity was provisioned or resized.

## Verified outcomes

| Check | Observed |
|---|---|
| SQL-source checkpoint | Ten `hs` sources plus 108-row AnswerKey; hashes and schemas captured |
| Native OneLake COPY | All eleven tables loaded from typed SQL-derived Parquet; no storage key/SAS |
| Household snapshot | 240,819 rows and 240,819 distinct MemberKeys |
| SQL metric reconciliation | All nine household metrics matched every one of 108 program-month keys |
| Date dimension | 5,844 rows, 2015-01-01 through 2030-12-31 |
| Duplicate-program defects | 450 household-month groups, 50 distinct households |
| Missing-unit retention | 10 observations, 5 distinct households; unknown key retained |
| Property SCD2 | Five changed properties; zero invalid fact-to-property date resolutions |
| Idempotent replay | Full 240,819-row snapshot SHA-256 identical before and after bulk reload/transform; reconciliation passed again |
| DQ notebook | Fabric job `54f14629-da7b-4ab1-8ff1-bc6c672fd125`, Completed |
| Excel preflight | All 24 original files blocked as OLE/encrypted containers |
| Excel staging | Empty by design; no fabricated availability/supportive facts |
| Excel transform gate | Confirmed expected SQL error 51008 before creating Excel facts |
| Source preservation | No source SQL updates/truncates/reloads and no source storage overwrites |

An initial ODBC batch loader was too slow and was retired in favor of native
OneLake COPY. A lingering process after a shell-stop caused a competing staging
write; the grain guard detected it before fact publication. The exact orphaned
process was terminated, staging was replayed cleanly from the immutable checkpoint,
and the final runner now uses a publisher lock, per-attempt run IDs and a
post-publication count verification. The obsolete ODBC loading implementation is
not retained.

Raw run manifests, hashes, job responses and detailed results remain private in
the worktree's ignored `.state` directory; they are not published as source data.

## Not delivered / next dependency

| Stage | Exact dependency |
|---|---|
| PL_Ingest_SQL Lookup/ForEach/Copy | Create and bind selected Azure SQL Organizational account connection in Fabric; validate ten copies at concurrency 4 |
| Excel ingestion | User's unencrypted original 24 workbooks, inspection, approved run landing, Dataflow bindings and successful refresh |
| Excel-dependent facts and all 17 metrics | Successful original-workbook ingestion; do not substitute AnswerKey facts |
| PL_Master_HouseholdsServed | Complete native ingestion/Gen2 bindings, success/failure logging, DQ and reconciliation wiring |
| SM_HouseholdsServed Direct Lake | Excel gates, explicit model creation, relationships/measures and three-month reconciliation |
| RPT_MTW_Detail_HT | Complete model; actual report authoring/export and measured visual timings |
| RLS and labels | Approved UPN/program mapping, Viewer test account, Entra groups and existing sensitivity label |
| Fiscal year | Agency-approved fiscal calendar; current field deliberately NULL |
| Alerts/schedule | Approved Teams/Outlook destination, verified failure delivery and separate schedule enablement confirmation |
| Shortcut/mirroring | Approved connection and prerequisite checks; no source mutation for demo |
| Databricks UC | Separate presenter environment; none supplied |
| Pages/Git/deployment-pipeline binding | Explicit authorization and hosting/access decisions; repository remains private |

See the [build plan](build-plan.md) and [runbook](runbook.md) for executable
checkpoints and exact manual steps. The report JSON is a specification, not a PBIP
export; DAX files are prepared expressions, not evidence of a deployed model.
