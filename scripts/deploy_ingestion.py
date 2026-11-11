"""Native metadata-driven SQL -> immutable OneLake Parquet -> Warehouse ingestion."""
import json

from common import CONFIG, ROOT, check_account, fabric, items, save_state
from deploy_items import part


POLICY = {"timeout": "0.01:00:00", "retry": 0, "retryIntervalInSeconds": 30,
          "secureInput": True, "secureOutput": False}


def expression(text):
    return {"value": text, "type": "Expression"}


def after(name, condition="Succeeded"):
    return [{"activity": name, "dependencyConditions": [condition]}]


def build(warehouse, lake, sql_connection, server):
    ws = CONFIG["workspace_id"]
    linked = {"name": CONFIG["warehouse"], "properties": {
        "annotations": [], "type": "DataWarehouse", "typeProperties": {
            "endpoint": server, "artifactId": warehouse["id"], "workspaceId": ws,
        }}}
    lake_linked = {"name": CONFIG["lakehouse"], "properties": {
        "annotations": [], "type": "Lakehouse", "typeProperties": {
            "workspaceId": ws, "artifactId": lake["id"], "rootFolder": "Files",
        }}}
    dataset = {"annotations": [], "type": "DataWarehouseTable", "schema": [],
               "linkedService": linked}
    allowed = ",".join(f"'{name}'" for name in (
        "SourceSystem", "ProgramType", "VoucherType", "ActionType", "IncomeSource",
        "Property", "Unit", "UnitLocation", "Member", "FamilyMember",
    ))
    lookup = {
        "name": "Lookup active full-load tables", "type": "Lookup", "policy": POLICY,
        "typeProperties": {
            "firstRowOnly": False,
            "source": {"type": "DataWarehouseSource", "sqlReaderQuery":
                       "SELECT SourceSchema,SourceTable,TargetTable FROM mtd.TablesToCopy "
                       "WHERE IsActive=1 AND LoadType='Full' AND SourceSchema='hs' "
                       f"AND SourceTable IN ({allowed}) AND TargetTable=SourceTable",
                       "queryTimeout": "00:10:00", "partitionOption": "None"},
            "datasetSettings": dataset,
        },
    }

    def copy_and_publish(control=False):
        land_name = "Land AnswerKey control" if control else "Land SQL table"
        publish_name = "Publish AnswerKey control" if control else "Publish SQL table"
        table = "'AnswerKey'" if control else "item().TargetTable"
        select = "SELECT * FROM [hs].[AnswerKey]" if control else expression(
            "@concat('SELECT * FROM [hs].[',item().SourceTable,']')")
        copy = {
            "name": land_name, "type": "Copy", "policy": POLICY,
            "typeProperties": {
                "source": {
                    "type": "AzureSqlSource", "sqlReaderQuery": select,
                    "queryTimeout": "00:30:00", "partitionOption": "None",
                    "datasetSettings": {"annotations": [], "type": "AzureSqlTable", "schema": [],
                                        "externalReferences": {"connection": sql_connection}},
                },
                "sink": {
                    "type": "ParquetSink", "storeSettings": {"type": "LakehouseWriteSettings"},
                    "formatSettings": {"type": "ParquetWriteSettings"},
                    "datasetSettings": {
                        "annotations": [], "linkedService": lake_linked, "type": "Parquet",
                        "typeProperties": {
                            "location": {"type": "LakehouseLocation",
                                         "folderPath": expression(
                                             "@concat('landing/native_sql/',pipeline().RunId)"),
                                         "fileName": expression(f"@concat({table},'.parquet')")},
                            "compressionCodec": "snappy",
                        }, "schema": [],
                    },
                },
                "enableStaging": False,
                "translator": {"type": "TabularTranslator", "typeConversion": True,
                               "typeConversionSettings": {"allowDataTruncation": False,
                                                          "treatBooleanAsNumber": False}},
            },
        }
        prefix = f"https://onelake.dfs.fabric.microsoft.com/{ws}/{lake['id']}/Files/landing/native_sql/"
        sql = (
            "@concat('BEGIN TRY BEGIN TRANSACTION; DELETE FROM stg.[',"
            f"{table},']; COPY INTO stg.[',{table},'] FROM ''{prefix}',"
            f"pipeline().RunId,'/',{table},'.parquet'' WITH (FILE_TYPE=''PARQUET''); "
            f"IF (SELECT COUNT_BIG(*) FROM stg.[',{table},']) <> ',"
            f"string(activity('{land_name}').output.rowsRead),"
            "' THROW 51020, ''Native copy row-count mismatch'', 1; COMMIT; "
            "END TRY BEGIN CATCH IF @@TRANCOUNT>0 ROLLBACK; THROW; END CATCH; "
            "EXEC mtd.usp_LogRun @RunId=''',pipeline().RunId,''',@Stage=''Native SQL: ',"
            f"{table},''',@Status=''Succeeded'',@Rows=',"
            f"string(activity('{land_name}').output.rowsRead),';')"
        )
        publish = {
            "name": publish_name, "type": "Script", "policy": POLICY,
            "dependsOn": after(land_name), "linkedService": linked,
            "typeProperties": {"scripts": [{"type": "NonQuery", "text": expression(sql)}],
                               "scriptBlockExecutionTimeout": "00:30:00"},
        }
        return copy, publish

    land, publish = copy_and_publish()
    loop = {
        "name": "ForEach SQL table", "type": "ForEach",
        "dependsOn": after(lookup["name"]),
        "typeProperties": {
            "items": expression("@activity('Lookup active full-load tables').output.value"),
            "isSequential": False, "batchCount": 4, "activities": [land, publish],
        },
    }
    control, control_publish = copy_and_publish(control=True)
    control["dependsOn"] = after(loop["name"])
    return {"properties": {"activities": [lookup, loop, control, control_publish]}}


def main():
    check_account()
    available = items()
    warehouse = next(i for i in available if i["type"] == "Warehouse"
                     and i["displayName"] == CONFIG["warehouse"])
    lake = next(i for i in available if i["type"] == "Lakehouse"
                and i["displayName"] == CONFIG["lakehouse"])
    connections = fabric("GET", "connections")["value"]
    matches = [c for c in connections if c.get("displayName") == "ATL_HS_SQL_Source"
               and c["connectionDetails"]["path"] ==
               f"{CONFIG['source_server']};{CONFIG['source_database']}"]
    if len(matches) != 1:
        raise RuntimeError("Create the dedicated OAuth ATL_HS_SQL_Source connection first.")
    ws = CONFIG["workspace_id"]
    server = fabric("GET", f"workspaces/{ws}/warehouses/{warehouse['id']}")["properties"]["connectionString"]
    content = build(warehouse, lake, matches[0]["id"], server)
    path = ROOT / "pipelines" / "PL_Ingest_SQL.json"
    path.write_text(json.dumps(content, indent=2) + "\n")
    definition = {"parts": [part("pipeline-content.json", json.dumps(content))]}
    item = next((i for i in available if i["displayName"] == "PL_Ingest_SQL"), None)
    endpoint = f"workspaces/{ws}/dataPipelines"
    if item:
        if item["type"] != "DataPipeline":
            raise RuntimeError("Pipeline name is occupied by a different item type.")
        fabric("POST", f"{endpoint}/{item['id']}/updateDefinition",
               {"definition": definition}, has_result=False)
    else:
        item = fabric("POST", endpoint, {"displayName": "PL_Ingest_SQL",
                                         "definition": definition})
    save_state("ingestion-pipeline-item.json", item)
    print(json.dumps(item, indent=2))


if __name__ == "__main__":
    main()
