"""Immutable OneLake SQL checkpoints and non-destructive workbook preflight."""
import argparse
from io import BytesIO
import hashlib
import json
import re
import uuid
import zipfile

from azure.identity import AzureCliCredential
from azure.core import MatchConditions
from azure.storage.blob import BlobServiceClient
from azure.storage.filedatalake import DataLakeServiceClient
import pandas as pd

from common import CONFIG, ROOT, check_account, items, save_state, warehouse

EXPECTED_COLUMNS = {
    "UnitAvailability": {"ReportMonth", "Program", "TotalUnits", "AvailableUnits", "LIHTCUnits"},
    "SupportiveHousing": {"ReportMonth", "HouseholdID", "Program", "SupportType"},
}


def inspect_workbook(name, content):
    match = re.fullmatch(r"(UnitAvailability|SupportiveHousing)_(2025(?:0[1-9]|1[0-2]))\.xlsx", name)
    if not match:
        raise ValueError(f"Unexpected workbook name: {name}")
    if content.startswith(bytes.fromhex("D0CF11E0A1B11AE1")):
        return {"file": name, "status": "BLOCKED", "reason": "OLE/encrypted container; unencrypted XLSX required"}
    if not zipfile.is_zipfile(BytesIO(content)):
        raise ValueError(f"Not an XLSX ZIP package: {name}")
    kind, month = match.groups()
    frame = pd.read_excel(BytesIO(content), sheet_name="UnitAvailability" if kind == "UnitAvailability" else "Roster")
    if set(frame.columns) != EXPECTED_COLUMNS[kind]:
        raise ValueError(f"Unexpected columns in {name}: {list(frame.columns)}; inspect replacement before mapping")
    expected_date = pd.Timestamp(f"{month[:4]}-{month[4:]}-01")
    if not pd.to_datetime(frame.ReportMonth, errors="raise").eq(expected_date).all():
        raise ValueError(f"ReportMonth disagrees with file name: {name}")
    if frame.isna().any().any():
        raise ValueError(f"Null required values: {name}")
    key = ["Program"] if kind == "UnitAvailability" else ["HouseholdID", "Program"]
    if frame.duplicated(key).any():
        raise ValueError(f"Duplicate grain in {name}")
    if kind == "SupportiveHousing" and not frame.SupportType.isin(["VASH", "Other"]).all():
        raise ValueError(f"Unexpected SupportType in {name}")
    return {"file": name, "status": "READABLE", "rows": len(frame),
            "sha256": hashlib.sha256(content).hexdigest(), "effective_date_key": int(month + "01")}


def preflight():
    credential = AzureCliCredential(tenant_id=CONFIG["tenant_id"])
    service = BlobServiceClient(f"https://{CONFIG['storage_account']}.blob.core.windows.net", credential=credential)
    container = service.get_container_client(CONFIG["container"])
    blobs = [b for b in container.list_blobs(name_starts_with=CONFIG["excel_prefix"]) if b.name.endswith(".xlsx")]
    expected = {f"{kind}_{202500 + month}.xlsx" for kind in EXPECTED_COLUMNS for month in range(1, 13)}
    if {b.name.rsplit("/", 1)[-1] for b in blobs} != expected:
        raise RuntimeError("Workbook inventory must have exactly the 24 expected monthly files.")
    results = []
    for blob in blobs:
        data = container.download_blob(blob.name, etag=blob.etag, match_condition=MatchConditions.IfNotModified).readall()
        results.append(inspect_workbook(blob.name.rsplit("/", 1)[-1], data))
    save_state("excel-preflight.json", results)
    print(json.dumps(results, indent=2))
    if any(r["status"] == "BLOCKED" for r in results):
        raise RuntimeError("BLOCKED: provide unencrypted copies of the existing workbooks; no sources were modified.")
    return results


def filesystem():
    candidates = [i for i in items() if i["type"] == "Lakehouse" and i["displayName"] == CONFIG["lakehouse"]]
    if len(candidates) != 1:
        raise RuntimeError("Deploy the Lakehouse first.")
    lake = candidates[0]
    service = DataLakeServiceClient("https://onelake.dfs.fabric.microsoft.com",
                                   credential=AzureCliCredential(tenant_id=CONFIG["tenant_id"]))
    return service.get_file_system_client(CONFIG["workspace_id"]), lake


def create_directories(fs, lake, category, run_id):
    prefix = f"{lake['id']}/Files/landing/{category}/{run_id}"
    for path in (f"{lake['id']}/Files/landing", f"{lake['id']}/Files/landing/{category}", prefix):
        directory_client = fs.get_directory_client(path)
        if not directory_client.exists():
            directory_client.create_directory()
    return prefix


def put_immutable(fs, path, content):
    file = fs.get_file_client(path)
    if not file.exists():
        file.upload_data(content, overwrite=True, match_condition=MatchConditions.IfMissing)
    if file.get_file_properties().size != len(content):
        raise RuntimeError(f"OneLake size mismatch: {path}")
    if hashlib.sha256(file.download_file().readall()).digest() != hashlib.sha256(content).digest():
        raise RuntimeError(f"Immutable OneLake file hash differs: {path}")


def land_checkpoint():
    manifest = json.loads((ROOT / ".state" / "latest-checkpoint.json").read_text())
    directory = ROOT / ".state" / "runs" / manifest["run_id"]
    fs, lake = filesystem()
    prefix = create_directories(fs, lake, "sql", manifest["run_id"])
    for table, entry in manifest["tables"].items():
        content = (directory / f"{table}.json").read_bytes()
        if hashlib.sha256(content).hexdigest() != entry["sha256"]:
            raise RuntimeError(f"Checkpoint integrity failure: {table}")
        put_immutable(fs, f"{prefix}/{table}.json", content)
        print(f"Landed {table}: {entry['rows']} rows", flush=True)
    content = (directory / "manifest.json").read_bytes()
    put_immutable(fs, f"{prefix}/manifest.json", content)
    save_state("landing.json", {"run_id": manifest["run_id"], "path": prefix, "status": "verified"})


def land_excel():
    validated = preflight()
    # No destination writes occur until every workbook has passed.
    run_id = str(uuid.uuid4())
    credential = AzureCliCredential(tenant_id=CONFIG["tenant_id"])
    container = BlobServiceClient(
        f"https://{CONFIG['storage_account']}.blob.core.windows.net", credential=credential
    ).get_container_client(CONFIG["container"])
    fs, lake = filesystem()
    prefix = create_directories(fs, lake, "excel", run_id)
    for entry in validated:
        content = container.download_blob(CONFIG["excel_prefix"] + entry["file"]).readall()
        if hashlib.sha256(content).hexdigest() != entry["sha256"]:
            raise RuntimeError(f"Workbook changed after preflight: {entry['file']}")
        put_immutable(fs, f"{prefix}/{entry['file']}", content)
    with warehouse() as connection:
        cursor = connection.cursor()
        cursor.execute("BEGIN TRANSACTION")
        try:
            for entry in validated:
                target = "UnitAvailability" if entry["file"].startswith("UnitAvailability_") else "SupportiveHousing"
                cursor.execute("INSERT INTO mtd.FilesToLoad VALUES (?,?,?,?,?,'Landed')",
                               run_id, entry["file"], entry["effective_date_key"], target, entry["sha256"])
            cursor.execute("COMMIT")
        except Exception:
            cursor.execute("IF @@TRANCOUNT>0 ROLLBACK")
            raise
    put_immutable(fs, f"{prefix}/manifest.json", json.dumps(validated, indent=2).encode())
    save_state("excel-landing.json", {"run_id": run_id, "path": prefix, "files": validated})
    print(f"Set Dataflow pApprovedBatch to {run_id}; configure replace destinations before refresh.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--sql-checkpoint", action="store_true")
    parser.add_argument("--excel-preflight", action="store_true")
    parser.add_argument("--land-excel", action="store_true")
    args = parser.parse_args()
    if not args.sql_checkpoint and not args.excel_preflight and not args.land_excel:
        parser.error("Choose --sql-checkpoint, --excel-preflight or --land-excel")
    check_account()
    if args.sql_checkpoint:
        land_checkpoint()
    if args.land_excel:
        land_excel()
    elif args.excel_preflight:
        preflight()
