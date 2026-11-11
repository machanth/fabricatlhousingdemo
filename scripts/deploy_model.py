"""Create and configure the explicit Direct Lake model from production tables."""
import base64
import copy
import json
import re
import uuid

from common import CONFIG, ROOT, check_account, fabric, items, save_state
from deploy_items import part


TABLES = (
    "DimDate", "DimProgramType", "DimVoucherType", "DimActionType",
    "DimIncomeSource", "DimProperty", "DimUnit", "FactHouseholdSnapshot",
    "FactUnitAvailability", "FactSupportiveHousing", "DQ_Results",
)


def configure(definition):
    definition = copy.deepcopy(definition)
    model_part = next(p for p in definition["parts"] if p["path"] == "model.bim")
    document = json.loads(base64.b64decode(model_part["payload"]))
    model = document["model"]
    tables = {t["name"]: t for t in model["tables"]}
    source = tables["DimProgramType"]["partitions"][0]["source"]["expressionSource"]
    tables["ProgramScope"] = {
        "name": "ProgramScope", "isHidden": True,
        "columns": [
            {"name": "UserPrincipalName", "dataType": "string",
             "sourceColumn": "UserPrincipalName", "summarizeBy": "none"},
            {"name": "ProgramTypeKey", "dataType": "int64",
             "sourceColumn": "ProgramTypeKey", "summarizeBy": "none"},
        ],
        "partitions": [{"name": "ProgramScope", "mode": "directLake", "source": {
            "type": "entity", "schemaName": "mtd", "entityName": "ProgramScope",
            "expressionSource": source,
        }}],
        "sourceLineageTag": "[mtd].[ProgramScope]",
    }
    # These source identifiers/names are unnecessary for this aggregate report.
    excluded = {"HouseholdID", "MemberKey", "SourceUnitKey", "PropertyManager"}
    for table in tables.values():
        table["columns"] = [c for c in table["columns"] if c["name"] not in excluded]
        for column in table["columns"]:
            column["summarizeBy"] = "none"
            if column["name"].endswith("Key"):
                column["isHidden"] = True
        if table["name"] == "DimDate":
            for column in table["columns"]:
                if column["name"] == "MonthYear":
                    column["sortByColumn"] = "MonthStartDate"
                if column["name"] == "Date":
                    column["formatString"] = "yyyy-MM-dd"
        table["measures"] = []

    text = (ROOT / "semantic-model" / "measures.dax").read_text()
    pattern = r"MEASURE\s+(\w+)\[([^\]]+)\]\s*=\s*(.*?)(?=\s+MEASURE\s|\Z)"
    for table, name, expression in re.findall(pattern, text, re.S):
        tables[table]["measures"].append({
            "name": name, "expression": expression.strip().splitlines(),
            "formatString": "0.0%" if name == "Occupancy %" else "#,0",
            "displayFolder": "Households served",
        })
    tables["DQ_Results"]["measures"] = [{
        "name": "DQ Observations", "expression": "MAX(DQ_Results[ObservedCount])",
        "formatString": "#,0",
    }]
    model["tables"] = list(tables.values())
    relationships = []
    for fact in ("FactHouseholdSnapshot", "FactUnitAvailability", "FactSupportiveHousing"):
        pairs = [("EffectiveDateKey", "DimDate", "DateKey"),
                 ("ProgramTypeKey", "DimProgramType", "ProgramTypeKey")]
        if fact == "FactHouseholdSnapshot":
            pairs += [(key, table, key) for key, table in (
                ("UnitKey", "DimUnit"), ("PropertyKey", "DimProperty"),
                ("VoucherTypeKey", "DimVoucherType"), ("ActionTypeKey", "DimActionType"),
                ("IncomeSourceKey", "DimIncomeSource"),
            )]
        for foreign_key, dimension, key in pairs:
            relationships.append({
                "name": str(uuid.uuid5(uuid.NAMESPACE_URL, f"atl:{fact}:{foreign_key}")),
                "fromTable": fact, "fromColumn": foreign_key, "fromCardinality": "many",
                "toTable": dimension, "toColumn": key, "toCardinality": "one",
                "crossFilteringBehavior": "oneDirection", "isActive": True,
            })
    model["relationships"] = relationships
    model["roles"] = [{
        "name": "ProgramScope", "modelPermission": "read",
        "tablePermissions": [
            {"name": "DimProgramType",
             "filterExpression": (ROOT / "semantic-model" / "ProgramScope.dax").read_text().splitlines()},
            {"name": "ProgramScope",
             "filterExpression": "LOWER(ProgramScope[UserPrincipalName]) = LOWER(USERPRINCIPALNAME())"},
        ],
    }]
    model_part.update(part("model.bim", json.dumps(document, indent=2)))
    definition["parts"] = [p for p in definition["parts"] if p["path"] != ".platform"]
    return definition, document


def main():
    check_account()
    ws = CONFIG["workspace_id"]
    available = items()
    item = next((i for i in available if i["displayName"] == "SM_HouseholdsServed"), None)
    if item is None:
        warehouse = next(i for i in available if i["displayName"] == CONFIG["warehouse"]
                         and i["type"] == "Warehouse")
        urls = [f"https://onelake.dfs.fabric.microsoft.com/{ws}/{warehouse['id']}/Tables/prd/{t}"
                for t in TABLES]
        item = fabric("POST", f"workspaces/{ws}/semanticModels", {
            "displayName": "SM_HouseholdsServed",
            "description": "Explicit Direct Lake model of validated ATL Housing production tables.",
            "creationPayload": {"oneLakeTables": urls},
        })
    if item["type"] != "SemanticModel":
        raise RuntimeError("The semantic model name is used by another item type.")
    path = f"workspaces/{ws}/semanticModels/{item['id']}"
    original = fabric("POST", f"{path}/getDefinition?format=TMSL")["definition"]
    definition, document = configure(original)
    fabric("POST", f"{path}/updateDefinition", {"definition": definition}, has_result=False)
    folder = ROOT / "semantic-model"
    (folder / "model.bim").write_text(json.dumps(document, indent=2) + "\n")
    properties = next(p for p in definition["parts"] if p["path"] == "definition.pbism")
    (folder / "definition.pbism").write_bytes(base64.b64decode(properties["payload"]))
    verified = fabric("POST", f"{path}/getDefinition?format=TMSL")
    save_state("semantic-model-definition.json", verified)
    save_state("semantic-model-item.json", item)
    print(f"Configured Direct Lake model: {item['id']}")


if __name__ == "__main__":
    main()
