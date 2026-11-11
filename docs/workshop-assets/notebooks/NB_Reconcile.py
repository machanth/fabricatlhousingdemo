import json
import struct
import time
import uuid

import notebookutils
import pandas as pd
import pyodbc
import requests

run_id = str(uuid.uuid4())
token = notebookutils.credentials.getToken("pbi")
raw_token = token.encode("utf-16-le")
metrics = [
    "Households", "HWC", "HWC_Elderly", "HWC_Disabled", "HWC_Workforce",
    "HWOC", "HWOC_Elderly", "HWOC_Disabled", "HWOC_Workforce",
    "VASH_HWC", "VASH_HWOC", "OtherSupportive_HWC", "OtherSupportive_HWOC",
    "TotalUnits", "AvailableUnits", "LIHTCUnits", "VacantUnits",
]
keys = ["EffectiveDateKey", "ProgramTypeCode"]


def frame(cursor, query):
    cursor.execute(query)
    return pd.DataFrame.from_records([tuple(r) for r in cursor.fetchall()],
                                     columns=[c[0] for c in cursor.description])


def compare(actual, expected):
    if actual.duplicated(keys).any() or expected.duplicated(keys).any():
        raise RuntimeError("Duplicate program-month keys in reconciliation.")
    merged = actual.merge(expected, on=keys, how="outer",
                          suffixes=("_actual", "_expected"), indicator=True)
    if not merged["_merge"].eq("both").all():
        raise RuntimeError("Full-outer reconciliation found missing/extra program-month keys.")
    for metric in metrics:
        left, right = merged[f"{metric}_actual"], merged[f"{metric}_expected"]
        if not (left.eq(right) | (left.isna() & right.isna())).all():
            raise RuntimeError(f"Metric reconciliation failed: {metric}")
    return len(merged)


with pyodbc.connect(
    f"Driver={{ODBC Driver 18 for SQL Server}};Server={warehouse_server};"
    "Database=WH_ATL_HS;Encrypt=yes;TrustServerCertificate=no;",
    attrs_before={1256: struct.pack("<I", len(raw_token)) + raw_token},
    autocommit=True,
) as connection:
    cursor = connection.cursor()
    try:
        expected = frame(cursor, "SELECT * FROM stg.AnswerKey")
        actual = frame(cursor, "SELECT * FROM prd.vw_AllMetrics")
        program_months = compare(actual, expected)
        if program_months != 108:
            raise RuntimeError(f"Expected 108 demo program-months; found {program_months}.")
        headers = {"Authorization": f"Bearer {token}"}
        endpoint = (f"https://api.powerbi.com/v1.0/myorg/groups/{workspace_id}"
                    f"/datasets/{semantic_model_id}")
        response = requests.post(endpoint + "/refreshes", headers=headers,
                                 json={"type": "automatic"}, timeout=120)
        response.raise_for_status()
        if response.status_code != 202:
            raise RuntimeError(f"Unexpected model framing response: {response.status_code}")
        refresh_id = response.headers["Location"].rstrip("/").rsplit("/", 1)[-1]
        deadline = time.monotonic() + 900
        while time.monotonic() < deadline:
            time.sleep(10)
            refresh = requests.get(endpoint + f"/refreshes/{refresh_id}",
                                    headers=headers, timeout=120)
            refresh.raise_for_status()
            status = refresh.json()["status"]
            if status == "Completed":
                break
            if status in ("Failed", "Cancelled", "Disabled"):
                raise RuntimeError(f"Model framing failed: {refresh.json()}")
        else:
            raise TimeoutError(f"Model framing did not finish: {refresh_id}")
        response = requests.post(endpoint + "/executeQueries", headers=headers, json={
            "queries": [{"query": reconciliation_dax}],
            "serializerSettings": {"includeNulls": True},
        }, timeout=120)
        response.raise_for_status()
        result = response.json()
        if "error" in result or any("error" in r for r in result.get("results", [])):
            raise RuntimeError(f"Model DAX query failed: {result}")
        model_actual = pd.DataFrame(result["results"][0]["tables"][0]["rows"]).rename(
            columns={"DimDate[DateKey]": "EffectiveDateKey",
                     "DimProgramType[ProgramTypeCode]": "ProgramTypeCode",
                     **{f"[{m}]": m for m in metrics}})
        selected = expected[expected.EffectiveDateKey.isin([20250101, 20250701, 20251201])]
        model_keys = compare(model_actual, selected)
        cursor.execute("EXEC mtd.usp_LogRun ?,?,'Succeeded',?,NULL",
                       run_id, "Warehouse and Direct Lake reconciliation", program_months)
        evidence = {"warehouse_program_months": program_months, "model_program_months": model_keys,
                    "metrics": len(metrics), "refresh_id": refresh_id, "run_id": run_id}
        print(json.dumps(evidence))
    except Exception:
        cursor.execute("EXEC mtd.usp_LogRun ?,?,'Failed',NULL,?",
                       run_id, "Warehouse and Direct Lake reconciliation",
                       "Inspect reconciliation notebook exception.")
        raise
notebookutils.notebook.exit(json.dumps(evidence))
