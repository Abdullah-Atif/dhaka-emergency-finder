"""Call one Geoapify MCP tool over JSON-RPC and append it to a transcript.

Lets any AI agent that can run shell commands (or a human) use Geoapify MCP without a
built-in MCP client, and records every call for review.

    python agent/mcp_call.py TRANSCRIPT.jsonl TOOL_NAME '{"arg": "value"}'
    python agent/mcp_call.py TRANSCRIPT.jsonl --list
"""

import json
import os
import sys
import time
import urllib.request

ENDPOINT = "https://api.geoapify.com/v1/mcp"


def rpc(method, params=None):
    key = os.environ.get("GEOAPIFY_API_KEY")
    if not key:
        sys.exit("Set GEOAPIFY_API_KEY first.")
    body = {"jsonrpc": "2.0", "id": int(time.time() * 1000), "method": method}
    if params is not None:
        body["params"] = params
    req = urllib.request.Request(
        ENDPOINT, data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json", "Accept": "application/json, text/event-stream",
                 "x-api-key": key})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    transcript = sys.argv[1]
    if sys.argv[2] == "--list":
        for t in rpc("tools/list")["result"]["tools"]:
            print(f"{t['name']}: {t.get('description', '')[:100]}")
        return
    name = sys.argv[2]
    args = json.loads(sys.argv[3]) if len(sys.argv) > 3 else {}
    reply = rpc("tools/call", {"name": name, "arguments": args})
    result = reply.get("result", {})
    text = "".join(c.get("text", "") for c in result.get("content", []))
    try:
        data = json.loads(text)
    except ValueError:
        data = text
    with open(transcript, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"tool": name, "arguments": args, "is_error": result.get("isError", False),
                             "result": data}, ensure_ascii=False) + "\n")
    print(json.dumps(data, ensure_ascii=False, indent=1)[:6000])


if __name__ == "__main__":
    main()
