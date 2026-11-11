"""Prepare offline copy/paste assets; never deploy or execute workshop workloads."""
import json
from pathlib import Path
import re
import shutil

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "docs" / "workshop-assets"
METRICS = (
    "Households", "HWC", "HWC_Elderly", "HWC_Disabled", "HWC_Workforce",
    "HWOC", "HWOC_Elderly", "HWOC_Disabled", "HWOC_Workforce",
    "VASH_HWC", "VASH_HWOC", "OtherSupportive_HWC", "OtherSupportive_HWOC",
    "TotalUnits", "AvailableUnits", "LIHTCUnits", "VacantUnits",
)


def write(name, text):
    path = DEST.joinpath(*name.split("/"))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def main():
    DEST.mkdir(exist_ok=True)
    copies = {
        "sql/01_foundation.sql": "01_foundation.sql",
        "sql/02_transform.sql": "03_transform_procedures.sql",
        "sql/03_dimdate.sql": "04_dimdate.sql",
        "sql/views/metrics.sql": "05_metrics_view.sql",
        "sql/views/dq.sql": "06_dq_views.sql",
        "notebooks/NB_Transform.py": "notebooks/NB_Transform.py",
        "notebooks/NB_DQ_Checks.py": "notebooks/NB_DQ_Checks.py",
        "notebooks/NB_Reconcile.py": "notebooks/NB_Reconcile.py",
        "semantic-model/ProgramScope.dax": "dax/ProgramScope.dax",
        "semantic-model/reconcile.dax": "dax/reconcile.dax",
        "data-agent/instructions.txt": "ai/agent-instructions.txt",
        "data-agent/sample-questions.json": "ai/sample-questions.json",
        "ontology/business-context.json": "ai/ontology-business-context.json",
        "ontology/review-prompt.txt": "ai/ontology-review-prompt.txt",
    }
    for source, target in copies.items():
        path = DEST.joinpath(*target.split("/"))
        path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT.joinpath(*source.split("/")), path)
    questions = json.loads((ROOT / "data-agent" / "sample-questions.json").read_text())
    for question in questions:
        if "dax" in question:
            write(f"ai/{question['id']}.dax", question["dax"])
    staging = DEST / "03_source_staging.sql"
    if staging.exists():
        staging.replace(DEST / "02_source_staging.sql")
    if not (DEST / "02_source_staging.sql").exists():
        raise RuntimeError("The reviewed, metadata-derived source staging DDL is required.")

    text = (ROOT / "dataflow" / "DF_Excel_HouseholdsServed.pq").read_text()
    queries = dict(re.findall(r"shared (\w+)\s*=\s*(.*?);(?=\s*shared|\s*\Z)", text, re.S))
    for name in ("WorkbookRows", "CurrentBatch", "UnitAvailability", "SupportiveHousing"):
        query = queries[name]
        if name == "CurrentBatch":
            query = re.sub(
                r'"https://onelake\.dfs\.fabric\.microsoft\.com/[^"]+" & pApprovedBatch',
                '"https://onelake.dfs.fabric.microsoft.com/" & pWorkspaceId & "/" & '
                'pLakehouseId & "/Files/landing/excel/" & pApprovedBatch', query)
        write(f"power-query/{name}.pq", query)
    measures = (ROOT / "semantic-model" / "measures.dax").read_text()
    for table, name, expression in re.findall(
        r"MEASURE\s+(\w+)\[([^\]]+)\]\s*=\s*(.*?)(?=\s+MEASURE\s|\Z)", measures, re.S
    ):
        write(f"dax/{name.replace(' ', '-').replace('%', 'Percent')}.dax",
              f"// Select table {table} before New measure.\n{name} = {expression.strip()}")
    write("dax/DQ-Observations.dax",
          "// Select table DQ_Results before New measure.\n"
          "DQ Observations = MAX(DQ_Results[ObservedCount])")
    write("08_approved_program_scope.sql", """-- Only an approved mapping in your participant Warehouse.
DECLARE @ApprovedUPN varchar(320) = '<APPROVED_VIEWER_UPN>';
DECLARE @ApprovedProgram varchar(20) = '<APPROVED_PROGRAM_CODE>';
IF @ApprovedUPN LIKE '<%' OR @ApprovedProgram LIKE '<%'
    THROW 51020,'Replace placeholders only with an explicitly approved mapping.',1;
IF NOT EXISTS (SELECT 1 FROM prd.DimProgramType WHERE ProgramTypeCode=@ApprovedProgram)
    THROW 51021,'Approved program code was not found; no permission was granted.',1;
INSERT INTO mtd.ProgramScope (UserPrincipalName,ProgramTypeKey)
SELECT @ApprovedUPN,p.ProgramTypeKey FROM prd.DimProgramType p
WHERE p.ProgramTypeCode=@ApprovedProgram AND NOT EXISTS (
    SELECT 1 FROM mtd.ProgramScope s WHERE LOWER(s.UserPrincipalName)=LOWER(@ApprovedUPN)
    AND s.ProgramTypeKey=p.ProgramTypeKey
);
SELECT s.UserPrincipalName,p.ProgramTypeCode FROM mtd.ProgramScope s
JOIN prd.DimProgramType p ON s.ProgramTypeKey=p.ProgramTypeKey
WHERE LOWER(s.UserPrincipalName)=LOWER(@ApprovedUPN);
-- Repeat only for each additional explicitly approved program grant.
""")
    write("notebooks/parameters.py",
          'warehouse_server = "<WAREHOUSE_SQL_ENDPOINT>"\n'
          'workspace_id = "<WORKSPACE_ID>"\n'
          'semantic_model_id = "<SEMANTIC_MODEL_ID>"\n'
          f'reconciliation_dax = {(ROOT / "semantic-model" / "reconcile.dax").read_text()!r}')
    pipeline = json.loads((ROOT / "pipelines" / "PL_Ingest_SQL.json").read_text())
    activities = pipeline["properties"]["activities"]
    lookup = activities[0]
    loop = activities[1]
    copy, publish = loop["typeProperties"]["activities"]
    lake = copy["typeProperties"]["sink"]["datasetSettings"]["linkedService"]["properties"]["typeProperties"]
    ws, lh = lake["workspaceId"], lake["artifactId"]

    def portable(value):
        return value.replace(ws, "<WORKSPACE_ID>").replace(lh, "<LAKEHOUSE_ID>")

    write("expressions/lookup.sql", lookup["typeProperties"]["source"]["sqlReaderQuery"])
    write("expressions/foreach-items.txt", loop["typeProperties"]["items"]["value"])
    write("expressions/sql-source-query.txt",
          copy["typeProperties"]["source"]["sqlReaderQuery"]["value"])
    location = copy["typeProperties"]["sink"]["datasetSettings"]["typeProperties"]["location"]
    for field in ("folderPath", "fileName"):
        write(f"expressions/{field}.txt", location[field]["value"])
    write("expressions/publish-sql-table.txt",
          portable(publish["typeProperties"]["scripts"][0]["text"]["value"]))
    write("expressions/publish-answer-key.txt",
          portable(activities[3]["typeProperties"]["scripts"][0]["text"]["value"]))

    master = json.loads((ROOT / "pipelines" / "PL_Master_HouseholdsServed.json").read_text())
    stages = master["properties"]["activities"]
    validate = stages[0]["typeProperties"]["scripts"][0]
    write("expressions/validate-month.sql", validate["text"])
    write("expressions/master-success.txt",
          next(a for a in stages if a["name"] == "Log master success")[
              "typeProperties"]["scripts"][0]["text"]["value"])
    failure = next(a for a in stages if a["name"] == "Log failure - Validate reporting month")
    write("expressions/master-failure.txt",
          failure["typeProperties"]["scripts"][0]["text"]["value"].replace(
              "Master: Validate reporting month", "Master: <FAILED_ACTIVITY_NAME>"))

    pairs = ",\n      ".join(f"('{m}',a.[{m}],e.[{m}])" for m in METRICS)
    write("07_validate_all_metrics.sql", f"""-- Run only against your participant Warehouse.
SELECT 'actual' AS Side,COUNT(*) AS ProgramMonths FROM prd.vw_AllMetrics
UNION ALL SELECT 'expected',COUNT(*) FROM stg.AnswerKey;

SELECT 'actual' AS Side,EffectiveDateKey,ProgramTypeCode,COUNT(*) AS DuplicateCount
FROM prd.vw_AllMetrics GROUP BY EffectiveDateKey,ProgramTypeCode HAVING COUNT(*)>1
UNION ALL
SELECT 'expected',EffectiveDateKey,ProgramTypeCode,COUNT(*)
FROM stg.AnswerKey GROUP BY EffectiveDateKey,ProgramTypeCode HAVING COUNT(*)>1;

SELECT COALESCE(a.EffectiveDateKey,e.EffectiveDateKey) AS EffectiveDateKey,
       COALESCE(a.ProgramTypeCode,e.ProgramTypeCode) AS ProgramTypeCode,
       m.Metric,m.Actual,m.Expected
FROM prd.vw_AllMetrics a
FULL OUTER JOIN stg.AnswerKey e ON a.EffectiveDateKey=e.EffectiveDateKey
    AND a.ProgramTypeCode=e.ProgramTypeCode
CROSS APPLY (VALUES
      {pairs}
) m(Metric,Actual,Expected)
WHERE a.EffectiveDateKey IS NULL OR e.EffectiveDateKey IS NULL
   OR m.Actual<>m.Expected
   OR (m.Actual IS NULL AND m.Expected IS NOT NULL)
   OR (m.Actual IS NOT NULL AND m.Expected IS NULL)
ORDER BY EffectiveDateKey,ProgramTypeCode,m.Metric;
-- Expected: two 108 counts; zero duplicate keys; zero mismatch rows. NULL is not zero.
""")
    print(f"Prepared {len(list(DEST.rglob('*.*')))} manual copy/paste assets. Nothing deployed.")


if __name__ == "__main__":
    main()
