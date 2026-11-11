"""Export or explicitly reapply the real, bound Gen2 definition in this workspace."""
import argparse
import base64
import json

from common import CONFIG, ROOT, check_account, fabric, items
from deploy_items import part


FILES = ("queryMetadata.json", "mashup.pq")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--export", action="store_true")
    mode.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    check_account()
    item = next(i for i in items() if i["displayName"] == "DF_Excel_HouseholdsServed"
                and i["type"] == "Dataflow")
    endpoint = f"workspaces/{CONFIG['workspace_id']}/dataflows/{item['id']}"
    folder = ROOT / "dataflow" / "DF_Excel_HouseholdsServed.Dataflow"
    if args.export:
        definition = fabric("POST", endpoint + "/getDefinition")["definition"]
        parts = {p["path"]: p for p in definition["parts"]}
        folder.mkdir(exist_ok=True)
        for name in FILES:
            (folder / name).write_bytes(base64.b64decode(parts[name]["payload"]))
        print("Exported bound Gen2 M and connection/destination metadata; no credentials.")
    else:
        metadata = json.loads((folder / "queryMetadata.json").read_text())
        if metadata["name"] != item["displayName"] or not metadata.get("connections"):
            raise RuntimeError("The reviewed bound Gen2 definition is missing or incompatible.")
        fabric("POST", endpoint + "/updateDefinition", {"definition": {"parts": [
            part(name, (folder / name).read_text()) for name in FILES
        ]}}, has_result=False)
        print("Applied the reviewed Gen2 definition. Run and verify its refresh separately.")


if __name__ == "__main__":
    main()
