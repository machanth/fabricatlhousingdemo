"""Discover and query the published agent's documented MCP endpoint with Entra auth."""
import argparse
from datetime import datetime, timezone
import json
import urllib.request

from common import CONFIG, ROOT, items, save_state, token


def parse_response(raw):
    if not raw.strip():
        return None
    if raw.lstrip().startswith("{"):
        return json.loads(raw)
    messages = [json.loads(line[5:].strip()) for line in raw.splitlines()
                if line.startswith("data:") and line[5:].strip() != "[DONE]"]
    response = next((message for message in reversed(messages)
                     if "result" in message or "error" in message), None)
    if response is None:
        raise RuntimeError("The MCP response did not contain a result.")
    return response


def connect(agent_id):
    endpoint = (f"https://api.fabric.microsoft.com/v1/mcp/workspaces/{CONFIG['workspace_id']}"
                f"/dataagents/{agent_id}/agent")
    headers = {
        "Authorization": "Bearer " + token("https://api.fabric.microsoft.com"),
        "Content-Type": "application/json", "Accept": "application/json, text/event-stream"
    }

    def send(method, params=None, *, ident=None):
        body = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            body["params"] = params
        if ident is not None:
            body["id"] = ident
        req = urllib.request.Request(endpoint, json.dumps(body).encode(), headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=600) as response:
            session = response.headers.get("mcp-session-id")
            if session:
                headers["Mcp-Session-Id"] = session
            result = parse_response(response.read().decode())
        if result is not None and "error" in result:
            raise RuntimeError(f"MCP {method} failed: {result['error']}")
        return result

    initialize = send("initialize", {
        "protocolVersion": "2025-06-18", "capabilities": {},
        "clientInfo": {"name": "ATLWorkshopValidation", "version": "1.0"}
    }, ident=1)
    headers["MCP-Protocol-Version"] = initialize["result"]["protocolVersion"]
    send("notifications/initialized")
    tools = send("tools/list", {}, ident=2)["result"]["tools"]
    if len(tools) != 1:
        raise RuntimeError(f"Expected one data-agent tool; discovered {len(tools)}.")
    tool = tools[0]
    required = tool["inputSchema"].get("required", [])
    if len(required) != 1 or tool["inputSchema"]["properties"][required[0]]["type"] != "string":
        raise RuntimeError("The discovered question schema needs explicit review.")
    return send, tool["name"], required[0]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("case_ids", nargs="+", help="Question IDs in data-agent/sample-questions.json")
    args = parser.parse_args()
    questions = {q["id"]: q for q in json.loads(
        (ROOT / "data-agent" / "sample-questions.json").read_text())}
    unknown = set(args.case_ids) - questions.keys()
    if unknown:
        raise ValueError(f"Unknown test cases: {sorted(unknown)}")
    agent = next(i for i in items() if i["displayName"] == "DA_ATL_Housing")
    send, tool, question_arg = connect(agent["id"])
    evidence = []
    run_name = "data-agent-runtime-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + ".json"
    for ident, name in enumerate(args.case_ids, start=3):
        question = questions[name]
        result = send("tools/call", {
            "name": tool, "arguments": {question_arg: question["question"]}
        }, ident=ident)["result"]
        record = {"id": name, "question": question["question"], "response": result,
                  "checked_at_utc": datetime.now(timezone.utc).isoformat(),
                  "review_status": "Requires comparison with numeric baseline/behavior rubric"}
        evidence.append(record)
        save_state("data-agent-runtime-tests.json", evidence)
        save_state(run_name, evidence)
        print(json.dumps(record, ensure_ascii=True), flush=True)
        if result.get("isError"):
            raise RuntimeError(f"Agent returned a tool error for {name}; evidence saved.")


if __name__ == "__main__":
    main()
