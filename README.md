# ATL Housing - Households Served

Microsoft Fabric demo using the existing `ATLHousing` SQL database and
`fabridemo/atldemo` storage in the approved ATLhousing workspace.

## Workshop downloads

- [Workshop manual (PDF)](docs/downloads/ATL-Housing-Workshop-Manual.pdf)
- [Editable manual (Word)](docs/downloads/ATL-Housing-Workshop-Manual.docx)
- [Complete offline workshop pack (ZIP)](docs/downloads/ATL-Housing-Manual-Workshop-Pack.zip)

The public pack contains the supplied synthetic Excel workbooks, control files,
screenshots and manual editor assets. Azure/Fabric credentials, local session
state and browser profiles are not published. Making this repository public
does not grant access to the deployed Fabric workspace or its data.

**Core end-to-end demo deployed and run successfully:** native metadata-driven SQL
ingestion, real Gen2 Excel ingestion, Warehouse transformations, Spark DQ,
all-17-metric reconciliation, explicit Direct Lake model and HT1-HT10 Power BI
report. The master completed on 2026-11-11 UTC; all 108 Warehouse program-months
and 27 model program-months reconciled with zero errors.

[Open the report](https://app.fabric.microsoft.com/groups/4d77b5c8-d96f-41df-83e1-954c582336d8/reports/bc0a171e-8712-4f4e-98e6-5968613bb191).
RLS Viewer acceptance, fiscal calendar, sensitivity label, alert delivery,
schedule enablement and optional environment-dependent guide modules remain
approval/prerequisite gates, not completed production controls.
No source data was regenerated or overwritten; no new capacity, public Pages site
or unattended schedule was created.

Start with [the detailed build plan](docs/build-plan.md), then
[the runbook](docs/runbook.md). See [security/reporting](docs/security-reporting.md)
and [troubleshooting](docs/troubleshooting.md) for exact remaining gates.
The [deployment evidence](docs/deployment-status.md) records created item IDs,
successful run IDs and remaining acceptance gates.

```powershell
python -m pip install -r requirements.txt
python scripts\validate.py --include-excel
python scripts\validate_model.py
```

Run `PL_Master_HouseholdsServed` in Fabric for a complete refresh; see the runbook
for deployment/replay commands. Run publishers sequentially. Azure CLI Entra
sign-in and ODBC Driver 18 are required for local commands. Credentials and
checkpoint data are excluded from Git.

The [manual attendee workbook](docs/workshop-attendee-guide.md) includes the
requested ontology/data-agent extension in M15-M16, with UI steps, screenshots
and 15 sample questions/answers. [ONT_ATL_Housing](https://app.fabric.microsoft.com/groups/4d77b5c8-d96f-41df-83e1-954c582336d8/ontologies/432b00a8-8c6b-4f37-9a93-57821260365e)
provides reviewed analytical context for the published
[DA_ATL_Housing](https://app.fabric.microsoft.com/groups/4d77b5c8-d96f-41df-83e1-954c582336d8/aiskills/58a8a6ce-989b-47f7-9035-4d718e0e17ab).
Published definitions, instructions and independent DAX baselines are preserved
under `ontology` and `data-agent`. Source permissions and actual Viewer RLS still
require separate acceptance. The existing F8 was resumed with approval for this
extension; no capacity upgrade or new access grant was made.

```powershell
python -m unittest discover -s tests -v
python -m pip install -r requirements-docs.txt
python -m mkdocs build --strict
```
