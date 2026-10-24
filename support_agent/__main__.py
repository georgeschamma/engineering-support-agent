import argparse
import asyncio

from support_agent.demo import investigation_model, remote_model, unsupported_model
from support_agent.domain import Session
from support_agent.engine import build, investigate, live_model, trace_options


def show_message(message):
    calls = getattr(message, "tool_calls", [])
    label = getattr(message, "name", None) or message.type
    print(f"[{label}] {message.text or ', '.join(call['name'] for call in calls)}")


def show_update(node, values):
    for message in values.get("messages", []):
        show_message(message)
    if report := values.get("structured_response"):
        print(report.model_dump_json(indent=2))


def main():
    parser = argparse.ArgumentParser(description="Investigate fictional message-delivery incidents.")
    parser.add_argument("question", nargs="?", default="Why are messages delayed?")
    parser.add_argument("--offline", action="store_true", help="Use a predetermined model transcript")
    parser.add_argument("--raw", action="store_true", help="Use the manual loop instead of LangGraph")
    parser.add_argument("--unsupported", action="store_true", help="Reproduce a known unsupported answer")
    parser.add_argument("--mcp", metavar="URL", help="Discover additional tools from a local MCP server")
    args = parser.parse_args()
    if args.unsupported and not (args.offline and args.raw):
        parser.error("--unsupported requires --offline --raw")
    if args.mcp and args.raw:
        parser.error("MCP tools require the asynchronous graph path; omit --raw")

    session = Session("harbor")
    if args.unsupported:
        print("KNOWN FAILURE — NOT VERIFIED: the model will ignore a missing resource.")
    if args.offline:
        if args.mcp:
            model = remote_model()
        elif args.unsupported:
            model = unsupported_model()
        else:
            model = investigation_model(structured=not args.raw)
    else:
        model = live_model()

    if args.raw:
        investigate(model, args.question, session, observe=show_message)
    elif args.mcp:
        from support_agent.remote import investigate_remote
        result = asyncio.run(investigate_remote(model, args.mcp, args.question, session, show_update))
        if "structured_response" not in result:
            raise SystemExit("No structured report returned.")
    else:
        report = None
        for update in build(model).stream({"messages": [("user", args.question)]}, context=session,
                                          config=trace_options(session), stream_mode="updates"):
            for node, values in update.items():
                if values:
                    show_update(node, values)
                    report = values.get("structured_response", report)
        if report is None:
            raise SystemExit("No structured report returned.")


if __name__ == "__main__":
    main()
