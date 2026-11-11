"""Create only the approved items on the existing capacity; bootstrap Warehouse DDL."""
import re
from common import CONFIG, ROOT, check_account, ensure_item, fabric, save_state, warehouse


def main():
    check_account()
    workspace = fabric("GET", f"workspaces/{CONFIG['workspace_id']}")
    if workspace.get("capacityId") != CONFIG["capacity_id"]:
        raise RuntimeError("Workspace capacity differs from the approved existing capacity.")
    lake = ensure_item(CONFIG["lakehouse"], "Lakehouse", "lakehouses")
    wh = ensure_item(CONFIG["warehouse"], "Warehouse", "warehouses")
    save_state("items.json", {"lakehouse": lake, "warehouse": wh})
    with warehouse() as connection:
        for path in sorted((ROOT / "sql").glob("*.sql")):
            for batch in re.split(r"(?im)^\s*GO\s*$", path.read_text()):
                if batch.strip():
                    connection.cursor().execute(batch)
            print(f"Applied {path.name}", flush=True)


if __name__ == "__main__":
    main()
