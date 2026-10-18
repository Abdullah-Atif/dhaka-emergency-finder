# Connect an AI client to Geoapify MCP

Geoapify MCP is a remote Streamable HTTP server:

```
https://api.geoapify.com/v1/mcp
```

It authenticates with your Geoapify API key in the `x-api-key` header (or `?apiKey=` in the URL).
Get a free key at <https://myprojects.geoapify.com>. **Never commit a private key.**

## Claude Code

```bash
claude mcp add --transport http geoapify https://api.geoapify.com/v1/mcp --header "x-api-key: YOUR_API_KEY"
```

Then start `claude` inside this repository. To load the agent instructions, either paste
`agent/AGENT_INSTRUCTIONS.md` into the chat or copy it to `CLAUDE.md` for the session.

## VS Code + GitHub Copilot (agent mode)

Copy [`vscode-mcp.example.json`](vscode-mcp.example.json) to `.vscode/mcp.json`.
VS Code asks for the key the first time and stores it securely.

## Claude Desktop / other clients

Any client that supports remote Streamable HTTP MCP servers works. Use the endpoint URL above
and add the header `x-api-key: YOUR_API_KEY`. If the client cannot send headers, use
`https://api.geoapify.com/v1/mcp?apiKey=YOUR_API_KEY` (treat this URL as a secret).

## Quick check without an AI client

```bash
curl -X POST "https://api.geoapify.com/v1/mcp" -H "Content-Type: application/json" -H "x-api-key: YOUR_API_KEY" -d "{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"tools/list\"}"
```

## Example questions

- "I am at Mirpur 10 golchottor. Where is the fastest hospital to reach by car?"
- "আমি ধানমন্ডি ২৭ এ আছি, সবচেয়ে কাছের ফার্মেসি কোনটা?"
- "Nearest fire station to 23.7806, 90.4193 by motorcycle?"
- "Which police station can I reach fastest from Uttara Sector 7?"
- "মিরপুর ১০ এর কাছে কোন কোন মসজিদ আছে?"
- "List the temples and churches near Old Dhaka Sadarghat."
