"""Read SQL once, checkpoint locally, then atomically replace destination staging.

Never writes source SQL or storage. The checkpoint is private local data, not Git.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import uuid

from common import ROOT, TABLES, check_account, publisher_lock, quote, save_state, source


def target_type(column):
    _, datatype, length, precision, scale = column
    if datatype in ("varchar", "char"):
        return f"{datatype}({length if length != -1 else 'max'})"
    if datatype in ("nvarchar", "nchar"):
        return f"varchar({length * 4 if length != -1 else 'max'})"
    if datatype == "decimal":
        return f"decimal({precision},{scale})"
    if datatype == "tinyint":
        return "smallint"
    if datatype in ("int", "bigint", "smallint", "bit", "date"):
        return datatype
    raise ValueError(f"Unmapped source SQL type: {datatype}")


def snapshot():
    run_id = str(uuid.uuid4())
    directory = ROOT / ".state" / "runs" / run_id
    directory.mkdir(parents=True)
    manifest = {"run_id": run_id, "created_at": datetime.now(timezone.utc).isoformat(), "tables": {}}
    with source() as connection:
        # A stable cross-table read; source is static synthetic demo data.
        connection.cursor().execute("SET TRANSACTION ISOLATION LEVEL SERIALIZABLE")
        for table in (*TABLES, "AnswerKey"):
            columns = list(connection.cursor().execute(
                "SELECT COLUMN_NAME,DATA_TYPE,CHARACTER_MAXIMUM_LENGTH,NUMERIC_PRECISION,NUMERIC_SCALE "
                "FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA='hs' AND TABLE_NAME=? "
                "ORDER BY ORDINAL_POSITION", table))
            if not columns:
                raise RuntimeError(f"Missing source hs.{table}")
            names = [c[0] for c in columns]
            cursor = connection.cursor().execute(
                f"SELECT {','.join(map(quote, names))} FROM hs.{quote(table)}")
            rows = []
            while batch := cursor.fetchmany(10000):
                rows.extend(tuple(r) for r in batch)
            path = directory / f"{table}.json"
            path.write_text(json.dumps(rows, default=str, separators=(",", ":")))
            manifest["tables"][table] = {
                "rows": len(rows), "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "columns": [{"name": c[0], "type": target_type(c)} for c in columns],
            }
            print(f"Checkpoint hs.{table}: {len(rows)}", flush=True)
        connection.rollback()
    (directory / "manifest.json").write_text(json.dumps(manifest, indent=2))
    save_state("latest-checkpoint.json", manifest)
    return directory, manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--load", action="store_true", help="Replace Fabric staging from the new checkpoint")
    args = parser.parse_args()
    check_account()
    with publisher_lock():
        directory, manifest = snapshot()
        if args.load:
            from bulk_load import run
            run()
