"""Independent full-outer metric reconciliation, not a row-count-only proxy."""
import argparse
import json
import pandas as pd
from common import check_account, save_state, warehouse

KEYS = ["EffectiveDateKey", "ProgramTypeCode"]
HOUSEHOLD_METRICS = [
    "Households", "HWC", "HWC_Elderly", "HWC_Disabled", "HWC_Workforce",
    "HWOC", "HWOC_Elderly", "HWOC_Disabled", "HWOC_Workforce",
]
EXCEL_METRICS = [
    "VASH_HWC", "VASH_HWOC", "OtherSupportive_HWC", "OtherSupportive_HWOC",
    "TotalUnits", "AvailableUnits", "LIHTCUnits", "VacantUnits",
]


def household_metrics(frame):
    rows = []
    for key, group in frame.groupby(KEYS):
        row = dict(zip(KEYS, key))
        children = group.HouseholdType.eq("With children")
        row.update(Households=len(group), HWC=int(children.sum()), HWOC=int((~children).sum()))
        for prefix, mask in (("HWC", children), ("HWOC", ~children)):
            for category in ("Elderly", "Disabled", "Workforce"):
                row[f"{prefix}_{category}"] = int((mask & group.Category.eq(category)).sum())
        rows.append(row)
    return pd.DataFrame(rows, columns=KEYS + HOUSEHOLD_METRICS)


def reconcile(actual, expected, metrics):
    if actual.duplicated(KEYS).any() or expected.duplicated(KEYS).any():
        raise ValueError("Reconciliation requires unique program-month keys.")
    merged = actual.merge(expected, on=KEYS, how="outer", suffixes=("_actual", "_expected"), indicator=True)
    errors = []
    for _, row in merged.iterrows():
        key = {k: row[k] for k in KEYS}
        if row["_merge"] != "both":
            errors.append({**key, "metric": "_key", "result": row["_merge"]})
            continue
        for metric in metrics:
            left, right = row[f"{metric}_actual"], row[f"{metric}_expected"]
            if not ((pd.isna(left) and pd.isna(right)) or (pd.notna(left) and pd.notna(right) and left == right)):
                errors.append({**key, "metric": metric, "actual": left, "expected": right})
    return errors


def read(connection, query):
    cursor = connection.cursor().execute(query)
    return pd.DataFrame.from_records([tuple(r) for r in cursor.fetchall()], columns=[c[0] for c in cursor.description])


def main(include_excel=False):
    check_account()
    with warehouse() as connection:
        expected = read(connection, "SELECT * FROM stg.AnswerKey")
        frame = read(connection, "SELECT f.*,p.ProgramTypeCode FROM prd.FactHouseholdSnapshot f "
                     "JOIN prd.DimProgramType p ON p.ProgramTypeKey=f.ProgramTypeKey")
        actual = household_metrics(frame)
        metrics = HOUSEHOLD_METRICS
        if include_excel:
            actual = read(connection, "SELECT * FROM prd.vw_AllMetrics")
            metrics = HOUSEHOLD_METRICS + EXCEL_METRICS
        errors = reconcile(actual, expected, metrics)
        result = {"program_months": len(actual), "observations": len(frame),
                  "metrics_checked": metrics, "errors": errors,
                  "excel_metrics": "checked" if include_excel else "BLOCKED until readable workbooks are ingested"}
        save_state("validation.json", result)
        if errors:
            raise RuntimeError(f"Reconciliation failed: {errors[:10]}")
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--include-excel", action="store_true")
    main(parser.parse_args().include_excel)
