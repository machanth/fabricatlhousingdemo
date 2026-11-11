# Deployment evidence and remaining gates

Observed in the existing ATLhousing workspace, 2026-11-11 UTC.
**The core end-to-end master completed successfully.** This is not a certificate
of production security, alert delivery or completion of prerequisite-gated modules.

## Live items

| Item | ID | Actual state |
|---|---|---|
| LH_ATL_Landing | b3fdd7c1-498f-45f6-82a6-3a1ed9fa2ae9 | Immutable SQL and original Excel landing; native run-scoped Parquet |
| WH_ATL_HS | 81bc6f59-4979-447b-aa5c-041c0e52ced2 | stg/prd/mtd, all three production facts, dimensions and control views |
| DF_Excel_HouseholdsServed | 6576d03c-9711-4039-91a0-b990c66e7760 | Real Gen2, approved OneLake batch, typed Warehouse Replace destinations; refreshed successfully |
| PL_Ingest_SQL | 1216fe95-4add-4c8d-a8bf-fa34dbf834a3 | Metadata Lookup, ForEach concurrency 4, ten SQL copies plus AnswerKey, transactional Warehouse publication |
| NB_Transform | 860b3aa7-9d96-4d41-b59f-fa75dfe9fe1f | All three transformation procedures executed in Fabric |
| PL_Transform | 39bf0d33-81b3-4b1a-866d-6998424a1c98 | Actual child execution succeeded |
| NB_DQ_Checks | a242b7fd-2ee8-4e71-af03-d5d385405291 | Actual Spark checks include Excel-dependent over-occupancy |
| NB_Reconcile | ff8356e7-2266-4092-b470-1d8c4ed6a9ce | Warehouse reconciliation, actual model framing and DAX reconciliation succeeded |
| SM_HouseholdsServed | a3f258a4-ebb2-4ac6-b2cd-a4ea817fc292 | Explicit Direct Lake on OneLake, dimensional relationships, measures, unassigned deny-unmapped RLS role |
| RPT_MTW_Detail_HT | bc0a171e-8712-4f4e-98e6-5968613bb191 | Real PBIR report: month slicer, three matrices, definitions tooltip and DQ page |
| PL_Master_HouseholdsServed | f66c68c2-d322-42bd-b0c9-725377fbb15f | Full actual run Completed; no recurring schedule |

Fabric also created managed Gen2 staging items on the existing F8.
No Azure capacity was provisioned or resized.

## Actual run evidence

Master **`2c003eb8-2c4c-446b-867c-d657cd3e65a4`** completed from
`2026-11-11T03:11:00.1393617Z` to `2026-11-11T03:18:19.33Z`.
Its stages all succeeded:

| Stage | Actual execution |
|---|---|
| Validate month | Typed `EffectiveMonth=2025-01`, checked against approved control data |
| Native SQL child | `4e195f9f-fb05-4124-887e-94d4077cbcb9` |
| Real Gen2 refresh | `4538eaf8-0317-4e5e-8a2f-87745599f07d` |
| Transform child | `879ec29a-a7ca-48d0-8ae5-7e9f44eda9ce` |
| Spark DQ | `00a9f02b-437d-401e-ac3c-a4f4f48a4520` |
| Reconcile/frame notebook | `c577a612-e0c1-4665-8c9c-552134f6bdc9` |
| Model framing | `e4120441-7ee5-4b5c-8c13-f3fa7338a3c8` |
| Master success log | Written to `mtd.PipelineRunLog` with the master run ID |

Independent native SQL run `92e09416-74c2-4e2b-9ecc-c3e732af0e17` and initial
real Gen2 refresh `43131a47-c2db-48ea-845a-5195a4fc4751` also completed.

Safe forced-failure run **`8ec51121-3d36-4e73-a7ba-2ed1858047d3`** used
`EffectiveMonth=2025-13`. Validation failed with the expected message, the failure
log succeeded, and the explicit Fail activity made the master terminal **Failed**.
No ingestion/transform activities ran. This proves failure propagation/logging,
**not** Teams/Outlook delivery.

An initial master definition used an unsupported activity type and failed before
execution. It was corrected to `RefreshDataFlow`; the successful run above is the
evidence, not that failed attempt.

## Data acceptance

| Check | Observed |
|---|---|
| SQL source | Ten approved `hs` sources plus 108-row AnswerKey, read-only |
| Readable originals | All 24 original workbooks; manifest/hash/schema/month/grain checks passed |
| Approved Excel batch | `9ebe0cfa-3ef7-4cff-bacd-49eaa9cbd5a5`, exact original bytes in OneLake |
| Actual Gen2 staging | 72 availability rows; 20,752 supportive roster rows |
| Household snapshot | 240,819 observations; deliberate second-program records retained |
| Full Warehouse reconciliation | All 17 metrics, all 108 program-months, zero errors |
| Actual model DAX reconciliation | All 17 metrics for 27 program-months: January, July, December; zero errors |
| Date dimension | 5,844 rows, 2015-01-01 through 2030-12-31 |
| Duplicate-program defects | 450 household-month groups, 50 households |
| Missing-unit retention | 10 observations, 5 households; unknown dimension member retained |
| Property SCD2 | Five changed properties; zero invalid current versions/overlaps |
| Negative vacancy | 24 program-months, exactly MIXED_HF and MIXED_RAD |
| January report | 19,998 households; vacancy -37/-75 actually rendered red (`rgb(192, 0, 0)`) |
| Month selection | Actual Ctrl-click test cannot select multiple months; January/July/December all three matrix totals verified |
| Warm report interactions | July 0.414s, December 0.409s, January 0.405s to correct rendered matrix totals |
| Page reload | 3.938s in the measured browser run; the full-page under-3s target is not met |
| Replay | Household snapshot SHA identical across prior replay; full master replay reconciled all metrics again |
| Source preservation | No source SQL updates/truncates/reloads, source blob overwrites or data regeneration |

The DQ notebook used by the successful master emitted the old scope label
`SQL-only` even though its actual rules included Excel over-occupancy. The label
was corrected to derive `SQL+Excel` from available staging, and corrected notebook
job `4f913664-4161-48de-923d-d6033e087bbe` completed. The rule results above
were not inferred from the stale label.

Browser timings measured interaction-to-rendered-correct-totals, not Performance
Analyzer or a guaranteed SLA. Page reload did not clear server cache; cold-capacity
timing remains unmeasured. Warm interactions meet the three-second target, but
full-page load acceptance remains open. Actual DQ page rendering was also verified.

Source checkpoints, complete job responses and detailed results remain private in
ignored `.state`; no source data or browser credentials are committed.
Real bound Gen2 M/metadata, native pipeline definitions, TMSL model and PBIR report
are preserved in the repository. Connection identifiers are environment bindings,
not credentials.

## Remaining approval/prerequisite gates

| Gate | Exact missing requirement |
|---|---|
| RLS enforcement acceptance | Approved UPN/program map and actual Viewer test identity; empty map and unassigned role are not an end-user access grant |
| Fiscal year | Agency-approved fiscal calendar; current field deliberately NULL |
| Sensitivity/access governance | Approved existing label and Entra groups; no invented labels or assignments |
| Report performance | Full-page reload measured 3.938s, above target; cold-capacity/Performance Analyzer acceptance remains open despite subsecond warm month interactions |
| Alerts | Approved Teams/Outlook destination/connection and verified safe-failure delivery |
| Schedule | Separate enablement approval; no unattended runs enabled |
| ADLS shortcut/mirroring | Dedicated approved connection and prerequisites; no source mutation for CDC demonstration |
| Databricks UC | Separate presenter environment, not supplied |
| Deployment pipeline/Test/Prod/Git binding | Target workspaces, binding/access decisions and approval; private Git source is already preserved |
| Public GitHub Pages | Explicit publishing approval; local private MkDocs lab is provided |

Copilot availability is not inferred from F8. Report authoring used the signed-in
account's Power BI trial; consumer licensing/capacity requirements still apply.

See the [runbook](runbook.md) for re-execution and
[security/reporting](security-reporting.md) for access acceptance.
