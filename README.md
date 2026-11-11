# ATL Housing - Households Served

Microsoft Fabric demo using the existing `ATLHousing` SQL database and
`fabridemo/atldemo` storage in the approved ATLhousing workspace.

**Partial delivery:** deployed SQL/Fabric foundation and runnable checkpoint,
transformation and reconciliation code. All 24 original Excel files are encrypted;
Excel-dependent ingestion, complete model/report and end-to-end acceptance remain
blocked until the user supplies readable originals. No source data was regenerated
or overwritten; no new capacity, public Pages site or unattended schedule was created.

Start with [the detailed build plan](docs/build-plan.md), then
[the runbook](docs/runbook.md). See [security/reporting](docs/security-reporting.md)
and [troubleshooting](docs/troubleshooting.md) for exact remaining gates.
The [deployment evidence](docs/deployment-status.md) records created item IDs,
verified reconciliation and the stages that are not yet delivered.

```powershell
python -m pip install -r requirements.txt
python scripts\deploy.py
python scripts\checkpoint.py --load
python scripts\landing.py --sql-checkpoint
python scripts\transform.py
python scripts\validate.py
python scripts\deploy_items.py
```

Run sequentially. Azure CLI Entra sign-in and ODBC Driver 18 are required.
Credentials and checkpoint data are excluded from Git.

```powershell
python -m unittest discover -s tests -v
python -m pip install -r requirements-docs.txt
python -m mkdocs build --strict
```
