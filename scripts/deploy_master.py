"""Deploy the native, failure-propagating end-to-end master orchestration."""
import json

from common import CONFIG, ROOT, check_account, fabric, items, save_state
from deploy_ingestion import POLICY, after, expression
from deploy_items import notebook_definition, part


def publish(name, collection, definition, available):
    existing = next((i for i in available if i["displayName"] == name), None)
    endpoint = f"workspaces/{CONFIG['workspace_id']}/{collection}"
    if existing:
        fabric("POST", f"{endpoint}/{existing['id']}/updateDefinition",
               {"definition": definition}, has_result=False)
        return existing
    return fabric("POST", endpoint, {"displayName": name, "definition": definition})


def main():
    check_account()
    available = items()
    by_name = {i["displayName"]: i for i in available if i["type"] != "SQLEndpoint"}
    ws = CONFIG["workspace_id"]
    warehouse = by_name[CONFIG["warehouse"]]
    lake = by_name[CONFIG["lakehouse"]]
    server = fabric("GET", f"workspaces/{ws}/warehouses/{warehouse['id']}")["properties"]["connectionString"]
    definition = notebook_definition(ROOT / "notebooks" / "NB_Reconcile.py", server, lake)
    import base64
    notebook = json.loads(base64.b64decode(definition["parts"][0]["payload"]))
    notebook["cells"][0]["source"] += [
        f"workspace_id = {ws!r}\n",
        f"semantic_model_id = {by_name['SM_HouseholdsServed']['id']!r}\n",
        f"reconciliation_dax = {(ROOT / 'semantic-model' / 'reconcile.dax').read_text()!r}\n",
    ]
    definition["parts"] = [part("notebook-content.ipynb", json.dumps(notebook))]
    reconcile = publish("NB_Reconcile", "notebooks", definition, available)
    linked = {"name": CONFIG["warehouse"], "properties": {
        "annotations": [], "type": "DataWarehouse", "typeProperties": {
            "endpoint": server, "artifactId": warehouse["id"], "workspaceId": ws,
        }}}

    def invoke(name, pipeline):
        return {"name": name, "type": "ExecutePipeline", "policy": POLICY,
                "typeProperties": {"pipeline": {"referenceName": by_name[pipeline]["id"],
                                                "type": "PipelineReference"},
                                   "waitOnCompletion": True}}

    validate = {
        "name": "Validate reporting month", "type": "Script", "policy": POLICY,
        "linkedService": linked, "typeProperties": {
            "scripts": [{"type": "NonQuery", "text":
                         "IF LEN(@EffectiveMonth)<>7 OR "
                         "TRY_CONVERT(date,@EffectiveMonth+'-01',23) IS NULL "
                         "THROW 51021,'EffectiveMonth must be YYYY-MM.',1; "
                         "IF NOT EXISTS (SELECT 1 FROM stg.AnswerKey WHERE EffectiveDateKey="
                         "CONVERT(int,REPLACE(@EffectiveMonth,'-','')+'01')) "
                         "THROW 51022,'Reporting month is absent from the approved demo control.',1; "
                         "DECLARE @Stage varchar(100)=CONCAT('Master report month: ',@EffectiveMonth); "
                         "EXEC mtd.usp_LogRun @RunId=@RunId,@Stage=@Stage,@Status='Succeeded';",
                         "parameters": [
                             {"name": "EffectiveMonth", "type": "String", "direction": "Input",
                              "value": expression("@pipeline().parameters.EffectiveMonth")},
                             {"name": "RunId", "type": "String", "direction": "Input",
                              "value": expression("@pipeline().RunId")},
                         ]}], "scriptBlockExecutionTimeout": "00:05:00",
        },
    }
    stages = [
        validate,
        invoke("Ingest SQL", "PL_Ingest_SQL"),
        {"name": "Ingest approved Excel", "type": "RefreshDataFlow", "policy": POLICY,
         "typeProperties": {"workspaceId": ws, "dataflowId": by_name["DF_Excel_HouseholdsServed"]["id"],
                            "dataflowType": "DataflowFabric"}},
        invoke("Transform production tables", "PL_Transform"),
        {"name": "Spark DQ", "type": "TridentNotebook", "policy": POLICY,
         "typeProperties": {"workspaceId": ws, "notebookId": by_name["NB_DQ_Checks"]["id"]}},
        {"name": "Reconcile and frame Direct Lake", "type": "TridentNotebook", "policy": POLICY,
         "typeProperties": {"workspaceId": ws, "notebookId": reconcile["id"]}},
    ]
    for previous, stage in zip(stages, stages[1:]):
        stage["dependsOn"] = after(previous["name"])
    success = {
        "name": "Log master success", "type": "Script", "policy": POLICY,
        "dependsOn": after(stages[-1]["name"]), "linkedService": linked,
        "typeProperties": {"scripts": [{"type": "NonQuery", "text": expression(
            "@concat('EXEC mtd.usp_LogRun @RunId=''',pipeline().RunId,"
            "''',@Stage=''PL_Master_HouseholdsServed'',@Status=''Succeeded'';')")}],
                           "scriptBlockExecutionTimeout": "00:05:00"},
    }
    failures = []
    for stage in stages:
        name = stage["name"]
        log_name = "Log failure - " + name
        failures += [
            {"name": log_name, "type": "Script", "policy": POLICY,
             "dependsOn": after(name, "Failed"), "linkedService": linked,
             "typeProperties": {"scripts": [{"type": "NonQuery", "text": expression(
                 "@concat('EXEC mtd.usp_LogRun @RunId=''',pipeline().RunId,"
                 f"''',@Stage=''Master: {name}'',@Status=''Failed'',"
                 "@ErrorMessage=''Inspect the failed master activity and linked child run.'';')")}],
                                "scriptBlockExecutionTimeout": "00:05:00"}},
            {"name": "Fail master - " + name, "type": "Fail",
             "dependsOn": after(log_name),
             "typeProperties": {"message": f"{name} failed; see activity details and PipelineRunLog.",
                                "errorCode": "ATL_HS_STAGE_FAILED"}},
        ]
    content = {"properties": {
        "parameters": {"EffectiveMonth": {"type": "String", "defaultValue": "2025-01"}},
        "activities": stages + [success] + failures,
    }}
    path = ROOT / "pipelines" / "PL_Master_HouseholdsServed.json"
    path.write_text(json.dumps(content, indent=2) + "\n")
    master = publish("PL_Master_HouseholdsServed", "dataPipelines",
                     {"parts": [part("pipeline-content.json", json.dumps(content))]}, available)
    save_state("master-pipeline-item.json", master)
    print(json.dumps({"master": master, "reconciliation_notebook": reconcile}, indent=2))


if __name__ == "__main__":
    main()
