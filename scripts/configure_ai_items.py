"""Configure already-created ATL AI items through documented definition APIs."""
import base64
import json
from pathlib import Path
import re
import uuid

from common import CONFIG, ROOT, fabric, items, save_state

ONTOLOGY = "ONT_ATL_Housing"
AGENT = "DA_ATL_Housing"


def decode(definition):
    return {p["path"]: base64.b64decode(p["payload"]).decode("utf-8-sig")
            for p in definition["definition"]["parts"]}


def encode(parts):
    return {"definition": {"parts": [
        {"path": path, "payload": base64.b64encode(text.encode()).decode(),
         "payloadType": "InlineBase64"} for path, text in parts.items()
    ]}}


def configure_ontology(parts, context):
    parts = dict(parts)
    if "tables/ProgramScope.tmdl" not in parts:
        if "ProgramScope" in parts["model.tmdl"]:
            raise RuntimeError("Unexpected partial security-map definition.")
    else:
        del parts["tables/ProgramScope.tmdl"]
    parts["model.tmdl"] = re.sub(r"(?m)^ref table ProgramScope\r?\n", "", parts["model.tmdl"])
    for name, description in context["tables"].items():
        path = f"tables/{name}.tmdl"
        text = parts[path]
        text = re.sub(r"\A(?:///.*\r?\n)+", "", text)
        parts[path] = "/// " + description + "\n" + text
    if any("ProgramScope" in text or "UserPrincipalName" in text for text in parts.values()):
        raise RuntimeError("The ontology still exposes a permission map.")
    return parts


def datasource(model, workspace_id, model_id):
    tables = []
    for table in model["tables"]:
        if table["name"] == "ProgramScope":
            continue
        columns = []
        for field in table.get("columns", []) + table.get("measures", []):
            name = field["name"]
            if name in {"HouseholdID", "MemberKey", "SourceUnitKey", "PropertyManager",
                        "UserPrincipalName"}:
                raise RuntimeError(f"Unnecessary identity field in model: {name}")
            kind = "measure" if "expression" in field else "column"
            columns.append({
                "id": str(uuid.uuid5(uuid.NAMESPACE_URL, f"{model_id}/{table['name']}/{kind}/{name}")),
                "display_name": name, "type": f"semantic_model.{kind}",
                "is_selected": True, **({"data_type": field["dataType"]} if "dataType" in field else {})
            })
        tables.append({
            "id": str(uuid.uuid5(uuid.NAMESPACE_URL, f"{model_id}/{table['name']}")),
            "display_name": table["name"], "type": "semantic_model.table",
            "is_selected": True, "children": columns
        })
    return {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/dataAgent/definition/datasource/1.0.0/schema.json",
        "artifactId": model_id, "workspaceId": workspace_id, "displayName": "SM_HouseholdsServed",
        "type": "semantic_model",
        "dataSourceInstructions": (
            "Authoritative metric source. Use existing measures and DimDate month filters. "
            "Do not query ProgramScope or identifiers. DQ is latest-run, not a monthly fact."),
        "elements": tables
    }


def main():
    current = {i["displayName"]: i for i in items()}
    ontology, agent, model = (current[name] for name in (ONTOLOGY, AGENT, "SM_HouseholdsServed"))
    workspace = CONFIG["workspace_id"]
    prefix = f"workspaces/{workspace}"
    exported = fabric("POST", f"{prefix}/ontologies/{ontology['id']}/getDefinition")
    context = json.loads((ROOT / "ontology" / "business-context.json").read_text())
    enriched = configure_ontology(decode(exported), context)
    fabric("POST", f"{prefix}/ontologies/{ontology['id']}/updateDefinition",
           encode(enriched), has_result=False)
    saved = decode(fabric("POST", f"{prefix}/ontologies/{ontology['id']}/getDefinition"))
    if "tables/ProgramScope.tmdl" in saved or "UserPrincipalName" in "".join(saved.values()):
        raise RuntimeError("Published ontology security-map exclusion was not persisted.")
    for path, value in saved.items():
        target = ROOT / "ontology" / "ONT_ATL_Housing.Ontology"
        target = target.joinpath(*path.split("/"))
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(value.replace("\r\n", "\n").rstrip() + "\n",
                          encoding="utf-8", newline="\n")
    original = decode(fabric("POST", f"{prefix}/dataAgents/{agent['id']}/getDefinition"))
    model_definition = json.loads((ROOT / "semantic-model" / "model.bim").read_text())["model"]
    instructions = (ROOT / "data-agent" / "instructions.txt").read_text()
    if len(instructions) > 15000:
        raise RuntimeError("Data-agent instructions exceed the documented character limit.")
    stage = {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/dataAgent/definition/stageConfiguration/1.0.0/schema.json",
        "aiInstructions": instructions
    }
    original["Files/Config/draft/stage_config.json"] = json.dumps(stage, indent=2)
    source = datasource(model_definition, workspace, model["id"])
    original["Files/Config/draft/semantic-model-SM_HouseholdsServed/datasource.json"] = json.dumps(source, indent=2)
    fabric("POST", f"{prefix}/dataAgents/{agent['id']}/updateDefinition",
           encode(original), has_result=False)
    save_state("ai-items.json", {"ontology": ontology, "data_agent": agent, "model": model,
                                "status": "configured draft; runtime/publication validation required"})
    print("Enriched ontology and configured data-agent draft. Publish/test in Fabric before acceptance.")


if __name__ == "__main__":
    main()
