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

Tested with VS Code 1.142 and Copilot Chat 0.70 ([session 03](sessions/03-mirpur-vscode-copilot.md)).

1. Copy [`vscode-mcp.example.json`](vscode-mcp.example.json) to `.vscode/mcp.json`.
   VS Code asks for the key the first time and stores it securely.
   **Do not write the key into `mcp.json`:** in our test the Copilot agent read that file by itself and sent its
   contents to the model. If VS Code asks whether the agent may read `mcp.json` or `.env`, deny it.
2. Open Chat (`Ctrl+Alt+I`), switch to **Agent** mode, and send your question, for example:
   `Follow #file:agent/AGENT_INSTRUCTIONS.md and use only the Geoapify tools. I am at Mirpur 10 golchottor. Where is the fastest hospital to reach by car?`
3. Allow the Geoapify tool calls when asked.

If you press **Start** on the server before sending any chat message, VS Code shows an error: *"Cannot start an MCP
server before the session runtime has been created. Send a message first."* This is harmless. The server starts
when you send the first message.

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
