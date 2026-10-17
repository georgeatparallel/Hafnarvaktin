# Optional harbour research with Parallel Search MCP

[Parallel Search MCP](https://docs.parallel.ai/integrations/mcp/search-mcp) adds
`web_search` and `web_fetch` for public harbour notices, port information and
vessel background. Anonymous search uses Fast mode and needs no Parallel account
or API key. The free endpoint has rate limits and is intended for light use.

Web results supplement Hafnarvaktin's domain tools. They do not establish a
vessel's current position or identify a boat in a camera frame. Keep the
[two-tool corroboration rule](README.md#the-case) for vessel identification and
cite the original sources, including their dates when available.

## Add it to a NanoClaw v2 agent group

Start with a working deployment of the NanoClaw v2 fork in [`nanoclaw/`](nanoclaw/).
Its agent container includes Node.js and `pnpm`. The host's approvals and self-mod
modules must be enabled; both are imported by the checked-in
[`src/modules/index.ts`](nanoclaw/src/modules/index.ts).

The current runner accepts command-based MCP servers. Use
[`mcp-remote`](https://github.com/geelen/mcp-remote) to bridge stdio to Parallel's
Streamable HTTP endpoint. This setup uses the existing `add_mcp_server` tool;
it does not require the older `/add-parallel` skill's API-key or source edits.

In the chat for the intended agent group, ask the assistant to call
`mcp__nanoclaw__add_mcp_server` with this payload. Check that `parallel-search` is
an unused server name first: adding an existing name replaces that entry.

```json
{
  "name": "parallel-search",
  "command": "pnpm",
  "args": [
    "dlx",
    "mcp-remote@0.1.38",
    "https://search.parallel.ai/mcp",
    "--transport",
    "http-only",
    "--enable-proxy",
    "--header",
    "User-Agent:Hafnarvaktin/parallel-search"
  ],
  "env": {}
}
```

An administrator must approve the Add MCP request. On approval, NanoClaw stores
the entry in that group's `container.json` and stops the active session container.
Send another message to start a container with the new configuration. The first
connection downloads the pinned adapter with `pnpm dlx`, so the container needs
outbound access to the npm registry and `https://search.parallel.ai`.
The adapter's `--enable-proxy` flag honors the container's proxy environment,
including NanoClaw's OneCLI routing.

Other MCP entries and the selected model/provider stay in place. No Parallel
credential is added, and the Task API is not configured.

## Check the research path

Send a focused request such as:

> Use the parallel-search MCP tools to find official visitor information for
> Ísafjörður harbour. Fetch the most relevant official page, then summarize it
> with its source URL and publication date if available. Keep visitor information
> separate from live vessel positions.

Confirm that the assistant uses `mcp__parallel-search__web_search` followed by
`mcp__parallel-search__web_fetch` and includes the fetched source in its answer.
For live positions or camera identification, continue using Hafnarvaktin's
existing domain tools. Search snippets alone are not corroborating AIS evidence.

If the tools do not appear, check the agent container's startup output for
`Additional MCP server: parallel-search (pnpm)` and confirm the Add MCP request
was approved for the correct group. If the chat setup produces no approval
request, check that the host self-mod and approvals modules are enabled. A
`pnpm dlx` startup error usually needs inspection of registry access and adapter
output. If Parallel reports a rate limit, wait for the indicated retry time;
do not treat the response as a successful search.

## Remove it

On the NanoClaw host, remove only `mcpServers["parallel-search"]` from
`groups/<folder>/container.json` for the group you configured. Preserve all other
keys. Stop that group's active session containers so the next message reloads
the configuration. No API key or source changes need to be undone.
