"""Run SQL-only transformations now; Excel facts require an explicit successful preflight."""
import argparse
import json
import re
import uuid

from common import ROOT, check_account, publisher_lock, quote, warehouse


def main(include_excel=False):
    check_account()
    run_id = str(uuid.uuid4())
    stages = ["prd.usp_Load_Dimensions", "prd.usp_Load_FactHouseholdSnapshot"]
    if include_excel:
        manifest = json.loads((ROOT / ".state" / "excel-preflight.json").read_text())
        if len(manifest) != 24 or any(r["status"] != "READABLE" for r in manifest):
            raise RuntimeError("Excel preflight has not succeeded for all 24 files.")
        stages.append("prd.usp_Load_FactUnitAvailability")
    with warehouse() as connection:
        manifest = json.loads((ROOT / ".state" / "latest-checkpoint.json").read_text())
        ready = json.loads((ROOT / ".state" / "staging-ready.json").read_text())
        if ready["source_run_id"] != manifest["run_id"]:
            raise RuntimeError("Latest source checkpoint has not been completely loaded.")
        for table, entry in manifest["tables"].items():
            count = connection.cursor().execute(f"SELECT COUNT_BIG(*) FROM stg.{quote(table)}").fetchone()[0]
            if count != entry["rows"]:
                raise RuntimeError(f"Incomplete or competing staging publication: {table}: {count}")
        for stage in stages:
            try:
                connection.cursor().execute(f"EXEC {stage}")
            except Exception:
                connection.cursor().execute("EXEC mtd.usp_LogRun ?,?,'Failed',NULL,?",
                                            run_id, stage, "Inspect CLI error; stage did not complete")
                raise
            connection.cursor().execute("EXEC mtd.usp_LogRun ?,?,'Succeeded'", run_id, stage)
            print(f"Succeeded: {stage}", flush=True)
        for path in (ROOT / "sql" / "views").glob("*.sql"):
            for batch in re.split(r"(?im)^\s*GO\s*$", path.read_text()):
                # The all-metrics view must not represent blocked Excel data as zero.
                if batch.strip() and (include_excel or "CREATE OR ALTER VIEW prd.vw_AllMetrics" not in batch):
                    connection.cursor().execute(batch)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--include-excel", action="store_true")
    args = parser.parse_args()
    with publisher_lock():
        main(args.include_excel)
