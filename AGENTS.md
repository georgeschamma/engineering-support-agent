# Engineering Support Agent

- Keep the design small: one agent, four read tools, thin CLI and MCP wrappers.
- Use fictional data only. Preserve tests alongside behavior changes.
- Read README.md for commands and limitations.
- Install: uv sync --frozen
- Verify: uv run --frozen pytest -q
- Offline graph demo: uv run --frozen python -m support_agent --offline
- Expected failure demo: uv run --frozen python -m support_agent --offline --raw --unsupported
- Never commit keys, .env, caches, or local task records.
