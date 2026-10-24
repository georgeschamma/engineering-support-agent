import json
from pathlib import Path

from langchain.tools import ToolRuntime, tool

from support_agent.domain import Session

CATALOG = json.loads(Path(__file__).with_name("fixtures.json").read_text())
SEVERITY = {"info": 0, "warning": 1, "error": 2}


def search(records: dict[str, str], query: str) -> str:
    terms = query.casefold().split()
    matches = [f"{key}: {text}" for key, text in records.items()
               if any(term in f"{key} {text}".casefold() for term in terms)]
    return "\n".join(matches) if matches else "No matches."


@tool
def find_runbooks(query: str, runtime: ToolRuntime[Session]) -> str:
    """Find tenant runbooks containing any query word, ignoring letter case."""
    return search(CATALOG.get(runtime.context.tenant, {}).get("runbooks", {}), query)


@tool
def inspect_config(path: str, runtime: ToolRuntime[Session]) -> str:
    """Read an exact configuration fixture path; missing paths include available alternatives."""
    configs = CATALOG.get(runtime.context.tenant, {}).get("config", {})
    if path in configs:
        return configs[path]
    return f"ERROR: configuration not found: {path}; available: {', '.join(sorted(configs)) or 'none'}"


@tool
def read_events(service: str, runtime: ToolRuntime[Session], minimum: str = "error") -> str:
    """Read service events at or above minimum severity: info, warning, or error."""
    if minimum not in SEVERITY:
        return "ERROR: invalid severity; choose info, warning, or error"
    rows = CATALOG.get(runtime.context.tenant, {}).get("events", [])
    available = {row["service"] for row in rows}
    if service not in available:
        return f"ERROR: unknown service {service}; available: {', '.join(sorted(available)) or 'none'}"
    events = [row["text"] for row in rows if row["service"] == service
              and SEVERITY[row["severity"]] >= SEVERITY[minimum]]
    return "\n".join(events) if events else "No events at that severity."


@tool
def lookup_incidents(query: str, runtime: ToolRuntime[Session]) -> str:
    """Find previous incidents for the current tenant by keyword."""
    return search(CATALOG.get(runtime.context.tenant, {}).get("incidents", {}), query)


READERS = [find_runbooks, inspect_config, read_events, lookup_incidents]
