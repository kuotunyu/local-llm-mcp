# Security and privacy boundaries

`local-llm-mcp` is a local-first MCP server, not a general-purpose security sandbox. Its guarantees depend on the selected transport and tool.

## Transport boundary

- **stdio** uses process-level trust. There is no application-layer API-key challenge because the MCP client launches the server process directly.
- **Streamable HTTP** requires `LOCAL_LLM_MCP_API_KEY`. The server uses the MCP Python SDK `TokenVerifier` / `AuthSettings` path and compares the configured pre-shared key with `secrets.compare_digest`.
- HTTP binds to `127.0.0.1` by default. `LOCAL_LLM_MCP_EXTRA_ALLOWED_HOSTS` widens accepted Host/Origin values for an explicit tunnel/proxy setup; it does not change the bind address by itself.

## Data-routing boundary

The private execution path is explicit:

- `ask_local`
- `summarize_private`
- `translate_private`
- `extract_json`
- `list_local_models`
- `pull_model`
- `models://local`

These operations use the configured Ollama endpoint. With the default `OLLAMA_HOST=http://127.0.0.1:11434`, their model traffic stays on the local machine. If an operator changes `OLLAMA_HOST` to a remote endpoint, that operator has changed the privacy boundary and must treat the endpoint accordingly.

`web_search` is intentionally different: it is an **opt-in external tool** and sends its query to the configured Felo API. Do not pass private document content to it.

## Model-output boundary

Model output is returned as data. The server does not execute model-generated shell commands, Python, URLs, or tool calls merely because they appear in model text. This is a non-execution boundary; it is **not** a claim that prompt injection is solved in general.

## Secrets

- Do not commit `.env`, API keys, tunnel credentials, or model-provider secrets.
- Use a high-entropy `LOCAL_LLM_MCP_API_KEY` for HTTP transport.
- Treat any tunnel or reverse proxy as an additional trust boundary outside this repository.

## Reporting

If you find a security issue, avoid posting credentials or sensitive payloads in a public issue. Report the minimal reproducible details needed to demonstrate the problem and rotate any secret that may have been exposed.
