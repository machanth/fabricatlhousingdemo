"""Run the deployed DQ notebook on demand and persist its actual terminal outcome."""
import time
import urllib.parse

from common import CONFIG, FABRIC, check_account, items, request, save_state


def main():
    check_account()
    matches = [i for i in items() if i["type"] == "Notebook" and i["displayName"] == "NB_DQ_Checks"]
    if len(matches) != 1:
        raise RuntimeError("Deploy NB_DQ_Checks first.")
    base = f"workspaces/{CONFIG['workspace_id']}/items/{matches[0]['id']}"
    status, headers, _ = request("POST", f"{FABRIC}/{base}/jobs/RunNotebook/instances")
    if status != 202:
        raise RuntimeError(f"Unexpected notebook job response: {status}")
    path = urllib.parse.urlsplit(headers.get("location", "")).path
    expected = f"/v1/{base}/jobs/instances/"
    if not path.startswith(expected):
        raise RuntimeError(f"Unexpected job polling path: {path}")
    url = "https://api.fabric.microsoft.com" + path
    save_state("dq-job.json", {"location": url, "status": "Submitted"})
    deadline = time.monotonic() + 1200
    while time.monotonic() < deadline:
        time.sleep(int(headers.get("retry-after", "15")))
        _, headers, result = request("GET", url)
        if result["status"] in ("Completed", "Failed", "Cancelled", "Deduped"):
            save_state("dq-job.json", result)
            print(result)
            if result["status"] != "Completed":
                raise RuntimeError(f"DQ notebook did not complete successfully: {result}")
            return
    raise TimeoutError(f"DQ job still running; inspect {url} before resubmitting.")


if __name__ == "__main__":
    main()
