"""Deploy substantive notebooks, guarded Gen2 authoring definition, and transform pipeline."""
import base64
import json
import uuid

from common import CONFIG, ROOT, check_account, ensure_item, fabric, items, save_state


def part(path, content):
    return {"path": path, "payload": base64.b64encode(content.encode()).decode(),
            "payloadType": "InlineBase64"}


def notebook_definition(path, server, lake):
    notebook = {
        "nbformat": 4, "nbformat_minor": 5,
        "metadata": {
            "kernelspec": {"display_name": "Synapse PySpark", "language": "python", "name": "synapse_pyspark"},
            "language_info": {"name": "python"},
            "dependencies": {"lakehouse": {"default_lakehouse": lake["id"],
                                         "default_lakehouse_name": lake["displayName"],
                                         "default_lakehouse_workspace_id": CONFIG["workspace_id"]}},
        },
        "cells": [
            {"cell_type": "code", "execution_count": None, "outputs": [],
             "metadata": {"tags": ["parameters"]}, "source": [f"warehouse_server = {server!r}\n"]},
            {"cell_type": "code", "execution_count": None, "outputs": [],
             "metadata": {}, "source": path.read_text().splitlines(keepends=True)},
        ],
    }
    return {"format": "ipynb", "parts": [part("notebook-content.ipynb", json.dumps(notebook))]}


def main():
    check_account()
    deployed = {}
    available = items()
    lake = next(i for i in available if i["type"] == "Lakehouse" and i["displayName"] == CONFIG["lakehouse"])
    wh = next(i for i in available if i["type"] == "Warehouse" and i["displayName"] == CONFIG["warehouse"])
    server = fabric("GET", f"workspaces/{CONFIG['workspace_id']}/warehouses/{wh['id']}")["properties"]["connectionString"]
    for name in ("NB_DQ_Checks", "NB_Transform"):
        definition = notebook_definition(ROOT / "notebooks" / f"{name}.py", server, lake)
        deployed[name] = ensure_item(name, "Notebook", "notebooks", definition)
    query_names = ("pApprovedBatch", "WorkbookRows", "CurrentBatch", "UnitAvailability", "SupportiveHousing")
    metadata = {
        "formatVersion": "202502", "name": "DF_Excel_HouseholdsServed",
        "documentLocale": "en-US", "queriesMetadata": {
            n: {"queryId": str(uuid.uuid5(uuid.NAMESPACE_URL, f"atl-demo:{n}")), "queryName": n,
                "loadEnabled": n in ("UnitAvailability", "SupportiveHousing")} for n in query_names
        }, "connections": [], "fastCombine": False,
    }
    definition = {"parts": [
        part("queryMetadata.json", json.dumps(metadata)),
        part("mashup.pq", (ROOT / "dataflow" / "DF_Excel_HouseholdsServed.pq").read_text()),
    ]}
    deployed["DF_Excel_HouseholdsServed"] = ensure_item(
        "DF_Excel_HouseholdsServed", "Dataflow", "dataflows", definition)
    pipeline = {"properties": {"activities": [{
        "name": "Transform", "type": "TridentNotebook",
        "policy": {"timeout": "0.01:00:00", "retry": 0, "retryIntervalInSeconds": 30,
                   "secureInput": True, "secureOutput": False},
        "typeProperties": {"notebookId": deployed["NB_Transform"]["id"], "workspaceId": CONFIG["workspace_id"]},
    }]}}
    (ROOT / "pipelines").mkdir(exist_ok=True)
    (ROOT / "pipelines" / "PL_Transform.json").write_text(json.dumps(pipeline, indent=2) + "\n")
    deployed["PL_Transform"] = ensure_item("PL_Transform", "DataPipeline", "dataPipelines",
                                          {"parts": [part("pipeline-content.json", json.dumps(pipeline))]})
    save_state("fabric-items.json", deployed)
    print(json.dumps({k: v["id"] for k, v in deployed.items()}, indent=2))


if __name__ == "__main__":
    main()
