# ATL Housing - Households Served

This private lab implements the supplied execution guide against the existing
`ATLHousing` database and `fabridemo/atldemo` storage. It never runs the supplied
destructive loader, regenerates workbooks, or overwrites source data.

**Status: SQL/Fabric foundation implemented; Excel-dependent delivery blocked.**
The existing 24 workbooks are OLE/encrypted packages rather than readable XLSX
ZIP files. The user elected to supply unencrypted copies of the original files.
No availability, supportive, vacancy, complete semantic-model, report or
end-to-end acceptance result should be presented as complete before that gate.

## Environment

| Component | Approved existing resource |
|---|---|
| Workspace | ATLhousing, `4d77b5c8-d96f-41df-83e1-954c582336d8` |
| Capacity | maddyscapcity, existing F8 in West US 3 |
| SQL | `sql-atlhousing.database.windows.net`, database `ATLHousing`, schema `hs` |
| Files | `fabridemo`, container `atldemo`, prefixes `excel/` and `csv/` |
| Lakehouse | `LH_ATL_Landing` |
| Warehouse | `WH_ATL_HS` |

Reuse the existing capacity; do not create or resize paid resources. CSVs are
bootstrap/validation alternatives, not an additional ingestion feed on top of SQL.
The source `hs.AnswerKey` contains 108 control rows; it is never used to manufacture
report facts. Local checkpoints and data are excluded from Git.

## Architecture

```text
Azure SQL hs (read-only) ---> immutable SQL checkpoint ---> OneLake run folder
                                  |
                                  +--> WH_ATL_HS.stg --> prd dimensions + household snapshot

Existing Excel (read-only) --> all-24 preflight --> approved run folder
                                                       |
                          DF_Excel_HouseholdsServed Gen2 (binding pending)
                                                       |
                       stg availability/roster --> Excel facts --> reconciliation
                                                       |
                       explicit Direct Lake model --> HT1-HT10 report
```

The local checkpoint runner is a working foundation/catch-up path, **not a claim
that the Data Factory Lookup/ForEach ingestion pipeline is finished**. See the
[detailed build plan](build-plan.md) and [runbook](runbook.md) for precise gates.
The [deployment evidence](deployment-status.md) separates verified outcomes from
authoring definitions and blocked stages.

The Dataflow item has authored M transformations and a deliberate empty-batch
guard. Its organizational-account connection, Warehouse replace destinations,
publish and successful refresh are still required. `PL_Transform` invokes the
transformation notebook and will fail explicitly at the Excel gate while staging
is empty. No unattended schedule or alert destination has been enabled.

## Local lab

```powershell
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
python -m pip install -r requirements-docs.txt
python -m mkdocs build --strict
```

GitHub Pages is intentionally not configured: publishing private-repository
content publicly requires separate approval. No screenshots, PBIP exports,
mirrors, labels, Viewer RLS tests or performance measurements are fabricated.
