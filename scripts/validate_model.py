"""Reconcile actual Direct Lake DAX output, preserving nulls and full key coverage."""
import json
import time

import pandas as pd

from common import CONFIG, ROOT, check_account, items, request, save_state, warehouse
from validate import EXCEL_METRICS, HOUSEHOLD_METRICS, read, reconcile


def main():
    check_account()
    model = next(i for i in items() if i["displayName"] == "SM_HouseholdsServed"
                 and i["type"] == "SemanticModel")
    endpoint = (f"https://api.powerbi.com/v1.0/myorg/groups/{CONFIG['workspace_id']}"
                f"/datasets/{model['id']}/executeQueries")
    start = time.monotonic()
    result = request("POST", endpoint, {
        "queries": [{"query": (ROOT / "semantic-model" / "reconcile.dax").read_text()}],
        "serializerSettings": {"includeNulls": True},
    }, resource="https://analysis.windows.net/powerbi/api")[2]
    duration = time.monotonic() - start
    save_state("model-reconciliation-raw.json", result)
    if "error" in result or any("error" in r for r in result.get("results", [])):
        raise RuntimeError(f"Semantic model query failed: {result}")
    rows = result["results"][0]["tables"][0]["rows"]
    actual = pd.DataFrame(rows).rename(columns={
        "DimDate[DateKey]": "EffectiveDateKey",
        "DimProgramType[ProgramTypeCode]": "ProgramTypeCode",
        **{f"[{m}]": m for m in HOUSEHOLD_METRICS + EXCEL_METRICS},
    })
    with warehouse() as connection:
        expected = read(connection, "SELECT * FROM stg.AnswerKey "
                        "WHERE EffectiveDateKey IN (20250101,20250701,20251201)")
    errors = reconcile(actual, expected, HOUSEHOLD_METRICS + EXCEL_METRICS)
    evidence = {
        "model_id": model["id"], "storage_mode": "Direct Lake on OneLake",
        "months": [20250101, 20250701, 20251201], "program_months": len(actual),
        "metrics_checked": HOUSEHOLD_METRICS + EXCEL_METRICS,
        "errors": errors, "dax_roundtrip_including_token_seconds": round(duration, 3),
        "report_render_performance": "Not measured by this API reconciliation",
    }
    save_state("model-validation.json", evidence)
    if errors:
        raise RuntimeError(f"Semantic model reconciliation failed: {errors[:10]}")
    print(json.dumps(evidence, indent=2))


if __name__ == "__main__":
    main()
