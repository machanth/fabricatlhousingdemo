"""Verify the documented expected answers directly against live model measures."""
from datetime import datetime, timezone
import json

from common import CONFIG, ROOT, items, request, save_state


def same_rows(actual, expected):
    canonical = lambda rows: sorted(json.dumps(row, sort_keys=True) for row in rows)
    return canonical(actual) == canonical(expected)


def main():
    model = next(i for i in items() if i["displayName"] == "SM_HouseholdsServed")
    endpoint = (f"https://api.powerbi.com/v1.0/myorg/groups/{CONFIG['workspace_id']}"
                f"/datasets/{model['id']}/executeQueries")
    questions = json.loads((ROOT / "data-agent" / "sample-questions.json").read_text())
    evidence = []
    for question in questions:
        if "dax" not in question:
            continue
        _, _, response = request("POST", endpoint, {
            "queries": [{"query": question["dax"]}],
            "serializerSettings": {"includeNulls": True}
        }, resource="https://analysis.windows.net/powerbi/api")
        if "error" in response or any("error" in result for result in response.get("results", [])):
            raise RuntimeError(f"Failed baseline query {question['id']}: {response}")
        rows = response["results"][0]["tables"][0].get("rows", [])
        if not same_rows(rows, question["expected_rows"]):
            raise RuntimeError(f"Expected-answer mismatch {question['id']}: {rows}")
        evidence.append({"id": question["id"], "rows": rows, "status": "matched"})
        print(f"Matched {question['id']}: {len(rows)} rows")
    result = {
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "source": "Direct execution of documented DAX against SM_HouseholdsServed",
        "not_claimed": "This baseline does not prove that the natural-language agent answers match.",
        "cases": evidence
    }
    save_state("ai-answer-baselines.json", result)


if __name__ == "__main__":
    main()
