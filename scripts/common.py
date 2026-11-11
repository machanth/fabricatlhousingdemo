"""Entra-only clients. Tokens stay in memory; no credentials in state files."""
import json
from contextlib import contextmanager
import os
from pathlib import Path
import shutil
import struct
import subprocess
import time
import urllib.error
import urllib.request
import urllib.parse
import uuid

ROOT = Path(__file__).resolve().parents[1]
CONFIG = json.loads((ROOT / "config" / "demo.json").read_text())
AZ = shutil.which("az")
FABRIC = "https://api.fabric.microsoft.com/v1"
TABLES = (
    "SourceSystem", "ProgramType", "VoucherType", "ActionType", "IncomeSource",
    "Property", "Unit", "UnitLocation", "Member", "FamilyMember",
)


def az(*args):
    if not AZ:
        raise RuntimeError("Azure CLI is required; run az login first.")
    result = subprocess.run([AZ, *args], capture_output=True, text=True, check=True)
    return json.loads(result.stdout) if result.stdout.strip() else None


def check_account():
    account = az("account", "show", "-o", "json")
    if (account["id"] != CONFIG["subscription_id"]
            or account["tenantId"] != CONFIG["tenant_id"]):
        raise RuntimeError("Wrong Azure account. Select the configured subscription and tenant.")


def token(resource):
    return az("account", "get-access-token", "--resource", resource, "-o", "json")["accessToken"]


def request(method, url, body=None, resource="https://api.fabric.microsoft.com", headers=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        url, data=data, method=method,
        headers={"Authorization": f"Bearer {token(resource)}",
                 "Content-Type": "application/json", **(headers or {})},
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as response:
            raw = response.read()
            return response.status, {k.lower(): v for k, v in response.headers.items()}, json.loads(raw) if raw else None
    except urllib.error.HTTPError as error:
        # Do not include request bodies: SQL/connection requests may contain credentials.
        raise RuntimeError(f"{method} failed HTTP {error.code}: {error.read().decode()}") from None


def fabric(method, path, body=None, *, has_result=True):
    status, headers, result = request(method, f"{FABRIC}/{path}", body)
    if status != 202:
        return result
    operation_id = headers.get("x-ms-operation-id")
    if not operation_id:
        location = urllib.parse.urlsplit(headers.get("location", ""))
        if location.path.startswith("/v1/operations/"):
            operation_id = location.path.rsplit("/", 1)[-1]
    if not operation_id:
        raise RuntimeError("Fabric accepted the operation without an operation ID.")
    operation = f"{FABRIC}/operations/{uuid.UUID(operation_id)}"
    deadline = time.monotonic() + 900
    while time.monotonic() < deadline:
        time.sleep(int(headers.get("retry-after", "5")))
        _, headers, progress = request("GET", operation)
        if progress["status"] == "Succeeded":
            return request("GET", operation.rstrip("/") + "/result")[2] if has_result else None
        if progress["status"] in ("Failed", "Cancelled"):
            raise RuntimeError(f"Fabric operation failed: {progress}")
    raise TimeoutError(f"Fabric operation is still pending: {operation}")


def items():
    path = f"workspaces/{CONFIG['workspace_id']}/items"
    result = []
    while path:
        page = fabric("GET", path)
        result.extend(page["value"])
        uri = page.get("continuationUri")
        if uri and not uri.startswith(FABRIC + "/"):
            raise RuntimeError("Unexpected Fabric continuation host.")
        path = uri[len(FABRIC) + 1:] if uri else None
    return result


def ensure_item(name, kind, collection, definition=None):
    matches = [item for item in items() if item["displayName"] == name
               and item["type"] != "SQLEndpoint"]
    if len(matches) > 1 or (matches and matches[0]["type"] != kind):
        raise RuntimeError(f"Conflicting item name: {name}")
    if matches:
        return matches[0]
    body = {"displayName": name}
    if definition:
        body["definition"] = definition
    created = fabric("POST", f"workspaces/{CONFIG['workspace_id']}/{collection}", body)
    print(f"Created {kind}: {name} ({created['id']})", flush=True)
    return created


def connect(server, database, *, autocommit=False):
    import pyodbc
    raw = token("https://database.windows.net/").encode("utf-16-le")
    return pyodbc.connect(
        f"Driver={{ODBC Driver 18 for SQL Server}};Server={server};"
        f"Database={database};Encrypt=yes;TrustServerCertificate=no;",
        attrs_before={1256: struct.pack("<I", len(raw)) + raw},
        autocommit=autocommit, timeout=60,
    )


def source():
    return connect(CONFIG["source_server"], CONFIG["source_database"])


def warehouse():
    candidates = [i for i in items() if i["type"] == "Warehouse"
                  and i["displayName"] == CONFIG["warehouse"]]
    if len(candidates) != 1:
        raise RuntimeError("Deploy the Warehouse foundation first.")
    item = fabric("GET", f"workspaces/{CONFIG['workspace_id']}/warehouses/{candidates[0]['id']}")
    return connect(item["properties"]["connectionString"], CONFIG["warehouse"], autocommit=True)


def quote(name):
    return "[" + name.replace("]", "]]") + "]"


def save_state(name, value):
    state = ROOT / ".state"
    state.mkdir(exist_ok=True)
    path = state / name
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(value, indent=2, default=str) + "\n")
    os.replace(temp, path)


@contextmanager
def publisher_lock():
    """Prevent competing local loaders/transformers, including orphaned processes."""
    state = ROOT / ".state"
    state.mkdir(exist_ok=True)
    with (state / "publisher.lock").open("a+b") as handle:
        handle.seek(0)
        handle.write(b"0")
        handle.flush()
        handle.seek(0)
        if os.name == "nt":
            import msvcrt
            try:
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError:
                raise RuntimeError("Another local publisher is running; wait for it to finish.") from None
        else:
            import fcntl
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError:
                raise RuntimeError("Another local publisher is running; wait for it to finish.") from None
        try:
            yield
        finally:
            if os.name == "nt":
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
