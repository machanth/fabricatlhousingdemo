"""Bulk-copy the SQL-derived immutable checkpoint, not a second CSV source feed."""
import argparse
from datetime import date
from decimal import Decimal
import hashlib
import json
import uuid

import pyarrow as pa
import pyarrow.parquet as pq

from common import CONFIG, ROOT, TABLES, check_account, publisher_lock, quote, save_state, warehouse
from landing import create_directories, filesystem, put_immutable


def arrow_column(values, sql_type):
    base = sql_type.split("(")[0]
    if base in ("varchar", "char"):
        return pa.array(values, type=pa.string())
    if base == "date":
        return pa.array([date.fromisoformat(v) if v is not None else None for v in values], type=pa.date32())
    if base == "decimal":
        precision, scale = map(int, sql_type.removeprefix("decimal(").removesuffix(")").split(","))
        return pa.array([Decimal(v) if v is not None else None for v in values],
                        type=pa.decimal128(precision, scale))
    types = {"int": pa.int32(), "bigint": pa.int64(), "smallint": pa.int16(), "bit": pa.bool_()}
    if base not in types:
        raise ValueError(f"Unmapped checkpoint type {sql_type}")
    return pa.array(values, type=types[base])


def prepare():
    manifest = json.loads((ROOT / ".state" / "latest-checkpoint.json").read_text())
    if set(manifest["tables"]) != set((*TABLES, "AnswerKey")):
        raise RuntimeError("Checkpoint does not contain exactly the allowlisted source and control tables.")
    directory = ROOT / ".state" / "runs" / manifest["run_id"]
    fs, lake = filesystem()
    prefix = create_directories(fs, lake, "sql_parquet", manifest["run_id"])
    for table, entry in manifest["tables"].items():
        path = directory / f"{table}.json"
        if hashlib.sha256(path.read_bytes()).hexdigest() != entry["sha256"]:
            raise RuntimeError(f"Checkpoint hash mismatch: {table}")
        rows = json.loads(path.read_text())
        data = pa.Table.from_arrays(
            [arrow_column([r[index] for r in rows], c["type"]) for index, c in enumerate(entry["columns"])],
            names=[c["name"] for c in entry["columns"]],
        )
        buffer = pa.BufferOutputStream()
        pq.write_table(data, buffer, compression="snappy")
        content = buffer.getvalue().to_pybytes()
        put_immutable(fs, f"{prefix}/{table}.parquet", content)
        entry["parquet_sha256"] = hashlib.sha256(content).hexdigest()
        entry["url"] = f"https://onelake.dfs.fabric.microsoft.com/{CONFIG['workspace_id']}/{prefix}/{table}.parquet"
        print(f"Prepared SQL-derived Parquet {table}: {data.num_rows}", flush=True)
    put_immutable(fs, f"{prefix}/manifest.json", json.dumps(manifest, indent=2).encode())
    save_state("bulk-checkpoint.json", manifest)
    return manifest


def copy_table(cursor, table, entry):
    ddl = ",".join(f"{quote(c['name'])} {c['type']} NULL" for c in entry["columns"])
    cursor.execute(f"IF OBJECT_ID('stg.{table}') IS NULL CREATE TABLE stg.{quote(table)} ({ddl})")
    cursor.execute("BEGIN TRANSACTION")
    try:
        cursor.execute(f"DELETE FROM stg.{quote(table)}")
        cursor.execute(f"COPY INTO stg.{quote(table)} FROM '{entry['url']}' WITH (FILE_TYPE='PARQUET')")
        count = cursor.execute(f"SELECT COUNT_BIG(*) FROM stg.{quote(table)}").fetchone()[0]
        if count != entry["rows"]:
            raise RuntimeError(f"Bulk-copy count mismatch for {table}: {count}")
        cursor.execute("COMMIT")
        return count
    except Exception:
        cursor.execute("IF @@TRANCOUNT>0 ROLLBACK")
        raise


def run(probe=False):
    check_account()
    manifest = prepare()
    attempt = str(uuid.uuid4())
    with warehouse() as connection:
        cursor = connection.cursor()
        if probe:
            # A separate throwaway table cannot interfere with an active staging load.
            probe_table = "CheckpointCopyProbe_" + uuid.uuid4().hex
            try:
                count = copy_table(cursor, probe_table, manifest["tables"]["SourceSystem"])
                print(f"Verified native OneLake COPY INTO: {count} rows")
            finally:
                cursor.execute(f"DROP TABLE IF EXISTS stg.{quote(probe_table)}")
            return
        for table, entry in manifest["tables"].items():
            stage = f"COPY:{table}"
            cursor.execute("INSERT INTO mtd.PipelineRunLog (RunId,Stage,StartedAt,Status) "
                           "VALUES (?,?,SYSUTCDATETIME(),'Running')", attempt, stage)
            try:
                count = copy_table(cursor, table, entry)
            except Exception:
                cursor.execute("UPDATE mtd.PipelineRunLog SET Status='Failed',FinishedAt=SYSUTCDATETIME(),"
                               "ErrorMessage='COPY failed; inspect CLI exception' WHERE RunId=? AND Stage=?",
                               attempt, stage)
                raise
            cursor.execute("UPDATE mtd.PipelineRunLog SET Status='Succeeded',FinishedAt=SYSUTCDATETIME(),"
                           "[RowCount]=? WHERE RunId=? AND Stage=?", count, attempt, stage)
            print(f"Bulk loaded stg.{table}: {count}", flush=True)
        # A committed read after all table transactions catches competing publications.
        for table, entry in manifest["tables"].items():
            count = cursor.execute(f"SELECT COUNT_BIG(*) FROM stg.{quote(table)}").fetchone()[0]
            if count != entry["rows"]:
                raise RuntimeError(f"Post-publication count mismatch for {table}: {count}")
        save_state("staging-ready.json", {"attempt_id": attempt, "source_run_id": manifest["run_id"],
                                         "status": "verified"})


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--probe", action="store_true")
    args = parser.parse_args()
    with publisher_lock():
        run(args.probe)
