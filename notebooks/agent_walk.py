"""Langflow Agent with memory chat, run one step per notebook cell.

The card unboxed here is langflow/flows/4-langflow-agent-with-memory/langflow-agent-memory-chat-local.json: its system
prompt, its local model through Ollama, and its tools. Each tool runs where the Langflow card sends it. The five MCP
cards call the RTRC MCP server (tools/assistant_mcp.py on 127.0.0.1:8782). The four Run Flow cards run the cards of
their flow, in canvas order, against the RTRC shell service (bench/shell_service.py on 127.0.0.1:8781). The
knowledge-base card is left out: it searches Langflow's own vector store, which has no search outside Langflow.
Memory-search_tool reads the same cards.

The model call goes to Ollama's /api/chat without a thinking switch, as Langflow's ChatOllama sends it, so the model
thinks and Ollama returns that text; it is printed. Nothing here lights the Langflow canvas. Colab cannot run this:
the model, the shell, the MCP server and the official Pilot are on this machine.
"""
from __future__ import annotations

import ast
import hashlib
import html
import json
import os
import re
import shutil
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FLOW_FILE = ROOT / "langflow" / "flows" / "4-langflow-agent-with-memory" / "langflow-agent-memory-chat-local.json"
SHARED_FLOWS = ROOT / "langflow" / "flows" / "5-shared-tools"
SHELL = os.environ.get("RTRC_SHELL_URL", "http://127.0.0.1:8781")
MCP_URL = os.environ.get("RTRC_ASSISTANT_MCP_URL", "http://127.0.0.1:8782/mcp")
OLLAMA = os.environ.get("RTRC_OLLAMA_URL", "http://127.0.0.1:11434")
SECRETS = ROOT / ".langflow" / "secrets.env"
AGENT_RUNS = ROOT / "mvp" / "agent-runs"
INBOX = ROOT / "mvp" / "exam-inbox"
PILOT_JAR = ROOT / "mvp" / "toolchain" / "kernel" / "sysml" / "jupyter-sysml-kernel-0.62.0-all.jar"
OPENCODE = ROOT / "tools" / "opencode" / "opencode"
START_AGENTS = {"Qwen direct": "direct", "Claude Code on Qwen (sandbox)": "claude-code", "OpenCode on Qwen (sandbox)": "opencode"}
SHOWN = 8000  # characters of a receipt printed here; the model always receives the whole text

# The cards of each Run Flow tool, in the order their flow runs them: (shell endpoint, card title on the canvas).
SUBFLOW_CARDS = {
    "Memory search": [("/tool/memory/library", "Memory library: MaritimeISR + approved designs as cards"),
                      ("/tool/memory/seeds", "MiniLM + FAISS seeds: cosine >= 0.30 + exact-name bonus"),
                      ("/tool/memory/hop", "One hop of neighbours -> cards for the assistant")],
    "Validate SysML with the official Pilot": [("/tool/validate/save", "Save the pasted SysML as a file"),
                                               ("/tool/validate/pilot", "Official SysML v2 Pilot on that file")],
    "Write to memory": [("/tool/gate", "Gate: Pilot PASS and all four checks PASS?"),
                        ("/tool/write", "Write the design into memory"),
                        ("/tool/record-approval", "Record the approval on the run")],
}
SHELL_FUNCTION = {
    "/run/start": "run_start", "/run/retrieve": "run_retrieve", "/run/requirements": "run_requirements",
    "/run/design": "_designs", "/run/adapt": "_designs", "/run/validate": "run_validate", "/run/align": "run_align",
    "/run/checks": "run_checks", "/run/tradeoffs": "run_tradeoffs", "/run/review": "run_review",
    "/tool/memory/library": "tool_memory_library", "/tool/memory/seeds": "tool_memory_seeds", "/tool/memory/hop": "tool_memory_hop",
    "/tool/gate": "tool_gate", "/tool/write": "tool_write", "/tool/record-approval": "tool_record_approval",
    "/tool/validate/save": "tool_validate_save", "/tool/validate/pilot": "tool_validate_pilot", "/tool/prompt-part": "tool_prompt_part",
}


class ToolError(RuntimeError):
    """A tool failed. As in Langflow (handle_parsing_errors), the message goes back to the model."""


# ---------------------------------------------------------------- display

def _html(markup: str) -> None:
    try:
        from IPython.display import HTML, display
    except ImportError:
        print(re.sub(r"<[^>]+>", "", markup))
        return
    display(HTML(markup))


def rule(title: str) -> None:
    print(f"\n━━ {title} " + "━" * max(4, 96 - len(title)))


def show_text(text: str, limit: int = SHOWN) -> None:
    text = str(text or "")
    if len(text) > limit:
        print(text[:limit] + f"\n… {len(text) - limit} more characters (the model received the whole text)")
    else:
        print(text)


def fold(title: str, text: str) -> None:
    """A collapsed block: click its title to open it."""
    _html(f"<details><summary><code>{html.escape(title)}</code></summary>"
          f"<pre style='font-size:11.5px;line-height:1.35;white-space:pre-wrap'>{html.escape(text)}</pre></details>")


def source_of(relpath: str, name: str) -> str:
    """The text of one function, class or assignment in a repository file, read from disk (not imported)."""
    path = ROOT / relpath
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    for node in ast.walk(ast.parse(text)):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.name == name:
            start = min([d.lineno for d in node.decorator_list] + [node.lineno])
            return f"# {relpath}, lines {start}-{node.end_lineno}\n" + "\n".join(lines[start - 1:node.end_lineno])
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == name for t in node.targets):
            return f"# {relpath}, lines {node.lineno}-{node.end_lineno}\n" + "\n".join(lines[node.lineno - 1:node.end_lineno])
    return f"# {name} was not found in {relpath}"


def code(relpath: str, *names: str) -> None:
    for name in names:
        fold(f"code that ran · {relpath} · {name}", source_of(relpath, name))


# ---------------------------------------------------------------- services

def _token() -> str:
    for line in SECRETS.read_text(encoding="utf-8").splitlines():
        if line.startswith("RTRC_SHELL_TOKEN="):
            return line.split("=", 1)[1].strip().strip("'\"")
    raise RuntimeError("RTRC_SHELL_TOKEN is missing from .langflow/secrets.env (run python3 scripts/up.py --import once)")


def shell(path: str, payload: dict, *, timeout: int = 7200, announce: bool = True) -> dict:
    """One POST to the RTRC shell service, the call every RTRC card makes."""
    if announce:
        brief = {key: (value if len(str(value)) <= 140 else str(value)[:137] + "…") for key, value in payload.items()}
        print(f"→ POST {SHELL}{path} {json.dumps(brief, ensure_ascii=False)}")
    started = time.monotonic()
    request = urllib.request.Request(SHELL + path, data=json.dumps(payload).encode(), method="POST",
                                     headers={"Content-Type": "application/json", "X-RTRC-Token": _token()})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = json.loads(response.read() or b"{}")
    except urllib.error.HTTPError as exc:
        body = json.loads(exc.read() or b"{}")
    except urllib.error.URLError as exc:
        raise ToolError(f"The RTRC shell service is not running at {SHELL} ({exc.reason}). Start it with python3 scripts/up.py --bg") from exc
    seconds = time.monotonic() - started
    if not body.get("ok"):
        if announce:
            print(f"← error after {seconds:.1f} s: {body.get('error')}")
        raise ToolError(body.get("error") or f"{path} failed")
    if announce:
        print(f"← ok in {seconds:.1f} s")
    body["_seconds"] = round(seconds, 1)
    return body


class MCP:
    """A minimal client of the RTRC MCP server (streamable HTTP), the server Langflow's MCP cards call."""

    def __init__(self, url: str = MCP_URL):
        self.url, self.session, self.count = url, None, 0

    def _post(self, body: dict, timeout: int = 1800) -> dict:
        headers = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
        if self.session:
            headers["mcp-session-id"] = self.session
        request = urllib.request.Request(self.url, data=json.dumps(body).encode(), headers=headers, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                raw = response.read().decode("utf-8", "replace")
                self.session = response.headers.get("mcp-session-id") or self.session
                kind = response.headers.get("content-type", "")
        except urllib.error.URLError as exc:
            raise ToolError(f"The RTRC MCP server is not running at {self.url} ({getattr(exc, 'reason', exc)}). Start it with python3 scripts/up.py --bg") from exc
        if "event-stream" in kind:
            data = [line[5:].strip() for line in raw.splitlines() if line.startswith("data:")]
            raw = data[-1] if data else ""
        return json.loads(raw) if raw.strip() else {}

    def _request(self, method: str, params: dict | None = None) -> dict:
        self.count += 1
        reply = self._post({"jsonrpc": "2.0", "id": self.count, "method": method, "params": params or {}})
        if "error" in reply:
            raise ToolError(f"MCP {method}: {reply['error'].get('message')}")
        return reply.get("result") or {}

    def open(self) -> None:
        self._request("initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                                     "clientInfo": {"name": "rtrc-notebook", "version": "1"}})
        self._post({"jsonrpc": "2.0", "method": "notifications/initialized"})

    def tools(self) -> list[dict]:
        return self._request("tools/list").get("tools", [])

    def call(self, name: str, arguments: dict) -> tuple[str, bool]:
        result = self._request("tools/call", {"name": name, "arguments": arguments})
        text = "\n".join(item.get("text", "") for item in result.get("content", []) if item.get("type") == "text")
        return text, bool(result.get("isError"))


def _get(url: str, timeout: int = 5):
    with urllib.request.urlopen(url, timeout=timeout) as response:
        return json.loads(response.read() or b"{}")


def check_services() -> bool:
    """What the agent needs on this machine; a missing piece is named with the command that starts it."""
    card = load_card()
    rows, ok = [], True

    def line(name: str, good: bool, detail: str) -> None:
        nonlocal ok
        ok = ok and good
        rows.append(f"  {'ok ' if good else 'NO '} {name:<34} {detail}")

    try:
        health = _get(SHELL + "/health")
        line("RTRC shell service", bool(health.get("ok")), f"{SHELL} · results page open: {health.get('page_running')}")
    except (urllib.error.URLError, OSError, ValueError) as exc:
        line("RTRC shell service", False, f"{SHELL} not answering ({exc}); python3 scripts/up.py --bg")
    try:
        client = MCP()
        client.open()
        line("RTRC MCP server", True, f"{MCP_URL} · {len(client.tools())} tools")
    except (ToolError, OSError, ValueError) as exc:
        line("RTRC MCP server", False, f"{exc}")
    try:
        tags = [item.get("name") for item in _get(OLLAMA + "/api/tags").get("models", [])]
        loaded = [item.get("name") for item in _get(OLLAMA + "/api/ps").get("models", [])]
        have = card["model"] in tags
        line("Ollama and the card's model", have, f"{card['model']} {'installed' if have else 'missing: scripts/qwen38.sh --serve'}"
                                                   f" · {'in GPU memory now' if card['model'] in loaded else 'loads on the first call'}")
    except (urllib.error.URLError, OSError, ValueError) as exc:
        line("Ollama", False, f"{OLLAMA} not answering ({exc}); python3 scripts/up.py --bg")
    line("Official Pilot 0.62 (jar)", PILOT_JAR.is_file(), str(PILOT_JAR.relative_to(ROOT)))
    line("OpenCode (pinned binary)", OPENCODE.is_file(), str(OPENCODE.relative_to(ROOT)))
    line("Sandbox: bubblewrap", bool(shutil.which("bwrap")), shutil.which("bwrap") or "missing")
    line("Sandbox network: slirp4netns", bool(shutil.which("slirp4netns")), shutil.which("slirp4netns") or "missing: the results page must be closed")
    print("\n".join(rows))
    print("\nEverything the agent needs is up." if ok else "\nStart what is marked NO, then run this cell again.")
    return ok


# ---------------------------------------------------------------- the card

def tool_name(flow_name: str) -> str:
    """Run Flow's tool name (lfx component_tool._format_tool_name)."""
    return re.sub(r"[^a-zA-Z0-9_-]", "-", f"{flow_name}_tool")


def load_card() -> dict:
    """The Agent card and its tool cards, read from the flow file Langflow imported."""
    flow = json.loads(FLOW_FILE.read_text(encoding="utf-8"))
    nodes = {node["id"]: node["data"]["node"] for node in flow["data"]["nodes"] if node.get("type") == "genericNode"}
    agent = nodes["Agent-rtrc"]["template"]
    model = agent["model"]["value"][0]
    shared = {}
    for path in sorted(SHARED_FLOWS.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        shared[data["name"]] = (path, data)
    cards, left_out = [], []
    for node_id, node in nodes.items():
        template = node["template"]
        if node_id.startswith("RunFlow-"):
            flow_name = template["flow_name_selected"]["value"]
            path, data = shared[flow_name]
            chat_input = next(item["id"] for item in data["data"]["nodes"] if item["id"].startswith("ChatInput-"))
            approval = any(row.get("approval_actions") for row in (template.get("tools_metadata") or {}).get("value") or [])
            cards.append({"node": node_id, "card": node["display_name"], "kind": "flow", "flow": flow_name,
                          "flow_file": str(path.relative_to(ROOT)), "name": tool_name(flow_name),
                          "key": f"{chat_input}~input_value", "approval": approval,
                          "description": f"Tool designed to execute the flow '{flow_name}'. Flow details: {data['description']}."})
        elif node_id.startswith("MCPTools-"):
            row = next(item for item in template["tools_metadata"]["value"] if item.get("status"))
            cards.append({"node": node_id, "card": node["display_name"], "kind": "mcp", "name": row["name"],
                          "description": row.get("description") or "", "approval": bool(row.get("approval_actions"))})
        elif node_id.startswith("Knowledge-"):
            left_out.append(node["display_name"])
    return {"flow": flow["name"], "agent_title": nodes["Agent-rtrc"]["display_name"], "model": model["name"],
            "provider": model["provider"], "system_prompt": agent["system_prompt"]["value"],
            "n_messages": agent["n_messages"]["value"], "max_iterations": agent["max_iterations"]["value"],
            "handle_parsing_errors": agent.get("handle_parsing_errors", {}).get("value"), "cards": cards, "left_out": left_out}


def pipeline_preset() -> dict:
    """What the Design pipeline flow's RTRC Start card is set to (agent, model, refuse an empty brief)."""
    data = json.loads((SHARED_FLOWS / "tool-design-pipeline.json").read_text(encoding="utf-8"))
    start = next(node for node in data["data"]["nodes"] if node["id"] == "RtrcStart-start")["data"]["node"]["template"]
    return {"agent": START_AGENTS.get(start["agent"]["value"], "direct"), "model": start["model"]["value"],
            "require_brief": bool(start.get("require_brief", {}).get("value"))}


def ollama_chat(model: str, messages: list[dict], tools: list[dict], think: bool | None) -> tuple[dict, dict]:
    """One streamed call to Ollama's /api/chat with a tool list: prints the thinking and the answer as they arrive,
    returns the message (content, thinking, tool_calls) and the final chunk (token counts, stop reason)."""
    payload = {"model": model, "messages": messages, "tools": tools, "stream": True}
    if think is not None:
        payload["think"] = think
    request = urllib.request.Request(f"{OLLAMA}/api/chat", data=json.dumps(payload).encode(),
                                     headers={"Content-Type": "application/json"}, method="POST")
    thinking, content, calls, final, mode = [], [], [], {}, ""
    started = time.monotonic()
    try:
        with urllib.request.urlopen(request, timeout=1800) as response:
            for raw in response:
                if not raw.strip():
                    continue
                chunk = json.loads(raw)
                part = chunk.get("message") or {}
                if part.get("thinking"):
                    if mode != "thinking":
                        print("\nthinking ›", end=" ")
                        mode = "thinking"
                    print(part["thinking"], end="", flush=True)
                    thinking.append(part["thinking"])
                if part.get("content"):
                    if mode != "content":
                        print("\nanswer ›", end=" ")
                        mode = "content"
                    print(part["content"], end="", flush=True)
                    content.append(part["content"])
                calls.extend(part.get("tool_calls") or [])
                if chunk.get("done"):
                    final = chunk
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Ollama did not answer at {OLLAMA} ({exc}). Start it with scripts/qwen38.sh --serve") from exc
    seconds = time.monotonic() - started
    print(f"\n← {seconds:.1f} s · read {final.get('prompt_eval_count', '?')} tokens · wrote {final.get('eval_count', '?')} tokens"
          f" · stop: {final.get('done_reason', '?')}")
    return {"content": "".join(content), "thinking": "".join(thinking), "tool_calls": calls}, final


def _arguments(call: dict) -> dict:
    raw = (call.get("function") or {}).get("arguments") or {}
    if isinstance(raw, str):
        try:
            raw = json.loads(raw) if raw.strip() else {}
        except json.JSONDecodeError:
            return {"_unparsed": raw}
    return raw if isinstance(raw, dict) else {}


def _call_line(call: dict) -> str:
    return f"{(call.get('function') or {}).get('name')}({json.dumps(_arguments(call), ensure_ascii=False)})"


# ---------------------------------------------------------------- the agent

class Agent:
    """Langflow's Agent card, one step per call: decide() asks the model, act() runs the tool it named."""

    def __init__(self, *, think: bool | None = None):
        self.card = load_card()
        self.model = self.card["model"]
        self.think = think  # None sends no switch, as Langflow's ChatOllama does; the model then thinks
        self.mcp = MCP()
        self.mcp.open()
        served = {tool["name"]: tool for tool in self.mcp.tools()}
        self.tools = []
        for card in self.card["cards"]:
            if card["kind"] == "mcp":
                spec = served[card["name"]]
                parameters = spec.get("inputSchema") or {"type": "object", "properties": {}}
                description = spec.get("description") or card["description"]
            else:
                parameters = {"type": "object", "required": ["flow_tweak_data"], "properties": {"flow_tweak_data": {
                    "type": "object", "title": "Flow Tweak Data", "required": [card["key"]],
                    "properties": {card["key"]: {"type": "string", "title": card["key"]}}}}}
                description = card["description"]
            card["parameters"] = parameters
            self.tools.append({"type": "function", "function": {"name": card["name"], "description": description, "parameters": parameters}})
        self.by_name = {card["name"]: card for card in self.card["cards"]}
        self.messages: list[dict] = [{"role": "system", "content": self.card["system_prompt"]}]
        self.pending: list[dict] = []
        self.waiting: dict | None = None
        self.pipeline: Pipeline | None = None
        self.turn_calls = 0
        self.step = 0
        self.log: list[dict] = []

    # -- what the card is
    def show_card(self) -> None:
        card = self.card
        rule(f"The Agent card · {card['agent_title']}")
        print(f"Flow file        {FLOW_FILE.relative_to(ROOT)}")
        print(f"Model            {card['model']} · provider {card['provider']} · {OLLAMA}")
        print(f"Messages kept    {card['n_messages']} · model calls per turn at most {card['max_iterations']}"
              f" · a failing tool's error goes back to the model: {card['handle_parsing_errors']}")
        print(f"System prompt    {len(card['system_prompt']):,} characters (open it below)")
        print(f"\nTools the model is given ({len(self.tools)}), as the canvas wires them to the Agent's Tools port:")
        for index, item in enumerate(card["cards"], 1):
            if item["kind"] == "flow":
                chain = " → ".join(title.split(":")[0] for _, title in SUBFLOW_CARDS.get(item["flow"], [])) or \
                    "start → ① memory → ② requirements → new | adapt → ③ OpenCode designs → ④ Pilot → ⑤ align → ⑥ checks → trade-offs? → ⑦ review"
                where = f"Run Flow · flow \"{item['flow']}\" · {chain}"
            else:
                where = f"MCP card · {MCP_URL} · tools/assistant_mcp.py {item['name']}()"
            print(f"  {index:>2}. {item['name']:<46} {'(asks the person first) ' if item['approval'] else ''}{where}")
        for title in card["left_out"]:
            print(f"\nLeft out here: “{title}”. It searches Langflow's own vector store, which has no search outside Langflow."
                  " Memory-search_tool reads the same cards.")
        fold("the system prompt, exactly as the Agent card holds it", card["system_prompt"])
        fold("the tool list sent to the model with every call (names, descriptions, argument schemas)",
             json.dumps(self.tools, indent=1, ensure_ascii=False))

    # -- one engineer message
    def say(self, text: str) -> None:
        if self.pending or self.waiting or self.pipeline:
            print("A tool call is still open. Finish it first (agent.act(), the pipeline cells, or agent.approve()).")
            return
        self.messages.append({"role": "user", "content": text})
        self.log.append({"who": "Engineer", "text": text})
        self.turn_calls = 0
        rule("Engineer")
        print(text)

    # -- one model call
    def decide(self) -> dict | None:
        if self.pending or self.waiting or self.pipeline:
            print("The model's last tool call has not run yet. Run agent.act() first"
                  + (" (or the pipeline cells)" if self.pipeline else "") + (" (or agent.approve())" if self.waiting else "") + ".")
            return None
        last = self.messages[-1]
        if last["role"] == "assistant" and not last.get("tool_calls"):
            print("The agent has already answered. Write the next message with agent.say(...).")
            return None
        if self.turn_calls >= self.card["max_iterations"]:
            print(f"Stopped: {self.card['max_iterations']} model calls in this turn, the card's limit.")
            return None
        self.turn_calls += 1
        self.step += 1
        rule(f"Step {self.step} · the model reads {len(self.messages)} messages and the {len(self.tools)} tools, then chooses")
        print(f"→ POST {OLLAMA}/api/chat · model {self.model} · thinking switch: {'not sent (Ollama default)' if self.think is None else self.think}")
        message, final = self._stream()
        calls = message["tool_calls"]
        self.messages.append({"role": "assistant", "content": message["content"], **({"tool_calls": calls} if calls else {})})
        if calls:
            self.pending = list(calls)
            print("\nThe model chose (nothing has run yet; agent.act() runs it):")
            for call in calls:
                print("  " + _call_line(call))
            self.log.append({"who": "Agent", "text": message["content"], "calls": [_call_line(c) for c in calls]})
        else:
            print("\nNo tool call: the text after “answer ›” is the agent's reply, as the Playground shows it.")
            self.log.append({"who": "Agent", "text": message["content"], "calls": []})
        return message

    def _stream(self) -> tuple[dict, dict]:
        return ollama_chat(self.model, self.messages, self.tools, self.think)

    # -- one tool
    def act(self):
        if self.waiting:
            print("A tool is waiting for the person: agent.approve(True) runs it, agent.approve(False) refuses it.")
            return None
        if self.pipeline:
            print("The design pipeline is open. Run its cells, then agent.give_back(pipe).")
            return None
        if not self.pending:
            print("Nothing to run: the model has not chosen a tool. Run agent.decide().")
            return None
        call = self.pending.pop(0)
        name, args = (call.get("function") or {}).get("name"), _arguments(call)
        self.step += 1
        card = self.by_name.get(name)
        if card is None:
            rule(f"Step {self.step} · the model named a tool that does not exist: {name}")
            self._result(name, f"Error: there is no tool named {name}.")
            return None
        rule(f"Step {self.step} · tool {name} · canvas card “{card['card']}”")
        print(f"arguments: {json.dumps(args, ensure_ascii=False)}")
        if card["approval"]:
            self.waiting = call
            print("\nLangflow stops here and shows “Tool execution requires approval” with Approve and Reject.\n"
                  "Nothing runs until agent.approve(True) (run it) or agent.approve(False) (refuse; the model is told).")
            return None
        if card["kind"] == "flow" and card["flow"] == "Design pipeline":
            self.pipeline = Pipeline(self, call, card)
            self.pipeline.show_plan()
            return self.pipeline
        text = self._run(card, args)
        self._result(name, text)
        return text

    def approve(self, yes: bool) -> None:
        call, self.waiting = self.waiting, None
        if call is None:
            print("No tool is waiting for approval.")
            return
        name, args = call["function"]["name"], _arguments(call)
        self.step += 1
        if not yes:
            rule(f"Step {self.step} · the person refused {name}")
            print("Nothing ran. The model is told the person rejected the call.")
            self._result(name, "The person rejected this tool call; it was not run.")
            return
        rule(f"Step {self.step} · the person approved {name}; it runs now")
        self._result(name, self._run(self.by_name[name], args))

    def give_back(self, pipe: "Pipeline") -> None:
        """The Design pipeline flow's last card (the review) is the tool's result."""
        if pipe is None or self.pipeline is not pipe:
            print("No open design pipeline to hand back.")
            return
        if pipe.result is None:
            print("The pipeline has not reached ⑦ Review yet.")
            return
        self.step += 1
        rule(f"Step {self.step} · the Design pipeline flow hands its last card's text back to the Agent")
        self.pipeline = None
        self._result(pipe.card["name"], pipe.result, quiet=True)
        print(f"{len(pipe.result):,} characters (the review shown in ⑦) go back to the model as the tool's result.")

    def _result(self, name: str, text: str, quiet: bool = False) -> None:
        self.messages.append({"role": "tool", "content": text, "tool_name": name})
        self.log.append({"who": "Tool", "name": name, "text": text})
        if not quiet:
            print(f"\nReturned to the model as {name}'s result: {len(text):,} characters.")

    def _run(self, card: dict, args: dict) -> str:
        try:
            if card["kind"] == "mcp":
                return self._mcp(card, args)
            value = (args.get("flow_tweak_data") or {}).get(card["key"])
            if not str(value or "").strip():
                raise ToolError(f"The tool's argument is flow_tweak_data {{\"{card['key']}\": ...}}; it arrived empty.")
            return self._subflow(card, str(value))
        except ToolError as exc:
            print(f"\nThe tool failed: {exc}\nAs in Langflow, the error text goes back to the model.")
            return f"Error: {exc}"

    def _mcp(self, card: dict, args: dict) -> str:
        print(f"→ MCP tools/call {card['name']} {json.dumps(args, ensure_ascii=False)} · {MCP_URL}")
        started = time.monotonic()
        text, failed = self.mcp.call(card["name"], args)
        print(f"← {'error' if failed else 'ok'} in {time.monotonic() - started:.1f} s\n")
        show_text(text)
        code("tools/assistant_mcp.py", card["name"])
        if failed:
            raise ToolError(text)
        return text

    def _subflow(self, card: dict, text: str) -> str:
        cards = SUBFLOW_CARDS[card["flow"]]
        print(f"The flow “{card['flow']}” ({card['flow_file']}) runs its {len(cards)} cards in order:")
        upstream = ""
        for index, (endpoint, title) in enumerate(cards, 1):
            print(f"\n[{index}/{len(cards)}] {title}")
            if endpoint == "/tool/memory/library":
                payload = {}
            elif endpoint == "/tool/validate/pilot":
                payload = {"saved": upstream}
            else:
                field = {"/tool/memory/seeds": "query", "/tool/memory/hop": "query", "/tool/validate/save": "sysml"}.get(endpoint, "request")
                payload = {field: text, "upstream": upstream}
            body = shell(endpoint, payload)
            show_text(body.get("summary", ""))
            code("bench/shell_service.py", SHELL_FUNCTION[endpoint])
            upstream = body.get("summary", "")
        if card["flow"] == "Write to memory":
            print("\nOn the canvas the flow then refreshes Langflow's knowledge base with the new cards; that card is Langflow's own and is not run here.")
        return upstream

    # -- helpers for a whole turn
    def run_until_reply(self, *, max_steps: int = 30):
        """decide() and act() in turn until the agent answers; stops at the design pipeline or at an approval."""
        for _ in range(max_steps):
            if self.waiting:
                return None
            if self.pipeline:
                return self.pipeline
            if self.pending:
                self.act()
                continue
            last = self.messages[-1]
            if last["role"] == "assistant" and not last.get("tool_calls"):
                return None
            if self.decide() is None:
                return None
        print(f"Stopped after {max_steps} steps.")
        return None

    def until_pipeline(self, *, max_steps: int = 30):
        """Like run_until_reply, and returns the Design pipeline when the model calls it."""
        pipe = self.run_until_reply(max_steps=max_steps)
        if pipe is None and self.pipeline is None:
            print("\nThe model answered without calling the design pipeline. Read its answer above; reply with agent.say(...).")
        return self.pipeline

    def transcript(self) -> None:
        """The conversation as the Playground shows it: each message, and under each answer the tools it called."""
        rule("The conversation, as the Playground lists it")
        for item in self.log:
            if item["who"] == "Engineer":
                print(f"\nEngineer › {item['text']}")
            elif item["who"] == "Agent":
                if item["calls"]:
                    for call in item["calls"]:
                        print(f"  Agent called {call}")
                if item["text"].strip():
                    print(f"\nAgent › {item['text'].strip()}")
            else:
                first = item["text"].strip().splitlines()[0] if item["text"].strip() else ""
                print(f"    ↳ {item['name']} returned {len(item['text']):,} characters · {first[:110]}")


# ---------------------------------------------------------------- the design pipeline

def _sha(text: str) -> str:
    return hashlib.sha256((text.strip() + "\n").encode()).hexdigest()[:12]


def validate_calls(workspace: str | Path) -> list[dict]:
    """Every ./validate OpenCode ran: one folder each under validation/, written by the official Pilot."""
    rows = []
    folder = Path(workspace) / "validation"
    for item in sorted(folder.iterdir()) if folder.is_dir() else []:
        result, request = item / "validation.json", item / "request.json"
        if not result.is_file():
            continue
        data = json.loads(result.read_text(encoding="utf-8"))
        asked = json.loads(request.read_text(encoding="utf-8")) if request.is_file() else {}
        rows.append({"folder": item.name, "package": asked.get("package_name"), "files": asked.get("model_files", []),
                     "status": data.get("status"), "seconds": data.get("wall_seconds"),
                     "errors": [d for d in data.get("diagnostics", []) if d.get("severity") == "ERROR"],
                     "warnings": data.get("warning_count", 0), "hashes": data.get("input_hashes", {})})
    return rows


def _validate_line(index: int, row: dict) -> str:
    files = " ".join(Path(name).name for name in row["files"])
    head = f"./validate #{index} {row['package']} {files} → official Pilot {row['status']} ({row['seconds']} s)"
    errors = [f"      line {e.get('line')}: {e.get('message')}" for e in row["errors"][:4]]
    more = [f"      … {len(row['errors']) - 4} more errors"] if len(row["errors"]) > 4 else []
    return "\n".join([head, *errors, *more])


class Pipeline:
    """The Design pipeline flow (project 5), one card per method, in the order the canvas runs them."""

    def __init__(self, agent: Agent, call: dict, card: dict):
        self.agent, self.call, self.card = agent, call, card
        self.brief = str(((_arguments(call).get("flow_tweak_data") or {}).get(card["key"])) or "").strip()
        self.preset = pipeline_preset()
        self.run: str | None = None
        self.out: dict[str, dict] = {}
        self.branch: str | None = None
        self.passed: bool | None = None
        self.workspaces: dict[str, str] = {}
        self.writers: dict[str, "Writer"] = {}
        self.result: str | None = None

    def show_plan(self) -> None:
        print(f"\nThis tool is a flow of its own: {self.card['flow_file']}. Its cards run in this order; the next cells run them one by one.")
        for line in ("RTRC Start (model " + self.preset["model"] + ")",
                     "① Search memory · Paper 2", "② Requirements", "Router: similar project found?",
                     "③ New design, or ③ Adapt the similar project · the writer of A and B. On the canvas: OpenCode in the sandbox. "
                     "In this notebook: the Langflow Agent, Pilot only card, one Pilot round per cell (pipe.writer)",
                     "Three read-only cards: the rules, the attribute template, the examples the writer was given",
                     "④ Official SysML v2 Pilot ⇄ repair (the pipeline's own check of what the writer handed in)",
                     "⑤ Align with memory · Paper 1", "⑥ Checks + read-back", "Router: all checks pass?",
                     "Trade-offs (only when a check failed)", "⑦ Review: diagram, Cameo export, the text handed back"):
            print(f"   · {line}")
        print(f"\nThe brief in the call ({len(self.brief)} characters):\n{self.brief}")

    def writer(self, key: str, *, think="inherit") -> "Writer":
        """③ for one design, written by the Langflow Agent, Pilot only card, driven here one turn per cell.
        think: "inherit" follows the outer agent; None sends no switch (Ollama's default, thinking on); False or True sets it."""
        if self.branch is None:
            raise ToolError("Run the router cell first.")
        key = key.upper()
        if key in self.writers:
            print(f"Design {key} already has a writer; it is returned again.")
            return self.writers[key]
        self.writers[key] = Writer(self, key, think=think)
        return self.writers[key]

    def _handed_in(self, key: str, writer: "Writer") -> None:
        slot = self.out.setdefault("design", {})
        slot[key] = {"rounds": writer.rounds, "model_calls": writer.model_calls}

    def pilot_rounds(self) -> None:
        """Every Pilot call the writer made for A and B, in order: the model's own checks before it handed in."""
        for key, writer in sorted(self.writers.items()):
            own = [row for row in writer.rounds if row.get("package") == f"Design{key}"]
            rule(f"Design {key} · every Pilot call by the writer ({len(writer.rounds)}: {len(own)} on Design{key}, {len(writer.rounds) - len(own)} on test packages), before the pipeline's own check")
            for row in writer.rounds:
                print(_round_line(row))
            if not writer.rounds:
                print("The writer handed in without calling the Pilot.")
            if getattr(writer, "stopped_at_cap", False):
                print(f"stopped at the card's limit of {writer.card['max_iterations']} model calls")
            if writer.final is not None:
                print(f"handed in: {len(writer.final)} characters · sha256 of its sysml block {writer.final_sha or '(no sysml block)'}")

    def _need(self, *keys: str) -> bool:
        missing = [key for key in keys if key not in self.out]
        if missing:
            print(f"Run the earlier card first: {', '.join(missing)}.")
            return False
        return True

    def _step(self, title: str, endpoint: str, *more_code: tuple[str, str]) -> dict:
        rule(f"Design pipeline · {title}")
        body = shell(endpoint, {"run": self.run})
        print()
        show_text(body.get("summary", ""))
        code("bench/shell_service.py", SHELL_FUNCTION[endpoint])
        for relpath, name in more_code:
            code(relpath, name)
        return body

    def start(self) -> dict:
        rule("Design pipeline · RTRC Start")
        if self.preset["require_brief"] and not self.brief:
            raise ToolError("No brief reached the pipeline; the card refuses an empty brief and nothing runs.")
        body = shell("/run/start", {"brief": self.brief, "agent": self.preset["agent"], "model": self.preset["model"], "replay": ""})
        self.run = body["run"]
        print()
        show_text(body["summary"])
        code("langflow/components/rtrc/rtrc_start.py", "RtrcStart")
        code("bench/shell_service.py", "run_start")
        self.out["start"] = body
        return body

    def retrieve(self) -> dict:
        if not self._need("start"):
            return {}
        self.out["retrieve"] = self._step("① Search memory · Paper 2", "/run/retrieve", ("bench/discover.py", "retrieve_existing"))
        return self.out["retrieve"]

    def requirements(self) -> dict:
        if not self._need("retrieve"):
            return {}
        self.out["requirements"] = self._step("② Requirements", "/run/requirements", ("bench/discover.py", "write_requirements"))
        return self.out["requirements"]

    def route_similar(self) -> str | None:
        if not self._need("requirements"):
            return None
        rule("Design pipeline · Router “Similar project found?”")
        first = self.out["requirements"]["summary"].split()[0]
        self.branch = "reuse" if first == "reuse" else "new"
        print("The router reads the requirements card's text and asks: does it start with “reuse”?")
        print(f"It starts with “{first}” → {'True: ③ Adapt the similar project' if self.branch == 'reuse' else 'False: ③ New design'}.")
        fold("the router's settings on the canvas (langflow/scripts/build_flows.py)", source_of("langflow/scripts/build_flows.py", "main_flow"))
        return self.branch

    def design(self) -> dict:
        """③ OpenCode writes design A, then design B, in the sandbox; this cell prints what it does as it does it."""
        if self.branch is None:
            print("Run the router cell first.")
            return {}
        endpoint = "/run/adapt" if self.branch == "reuse" else "/run/design"
        title = "③ Adapt the similar project" if self.branch == "reuse" else "③ New design"
        rule(f"Design pipeline · {title} · OpenCode in the sandbox, {self.preset['model']}")
        print(f"→ POST {SHELL}{endpoint} {json.dumps({'run': self.run})}")
        print("Design A first, then design B. OpenCode on the local model usually needs several minutes for each."
              " Below: every file it writes and every ./validate it runs, as they happen.\n")
        box: dict = {}

        def work() -> None:
            try:
                box["body"] = shell(endpoint, {"run": self.run}, announce=False)
            except Exception as exc:  # shown below, after the watch stops
                box["error"] = exc

        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")  # run_opencode names its folders in UTC
        started = time.monotonic()
        thread = threading.Thread(target=work, daemon=True)
        thread.start()
        dirs: dict[str, Path] = {}
        files: dict[str, float] = {}
        checked: set[str] = set()
        quiet_since = time.monotonic()
        while True:
            alive = thread.is_alive()
            for entry in os.scandir(AGENT_RUNS):
                match = re.match(r"(\d{8}T\d{6})-[0-9a-f]{4}-P-CODE-agent-([AB])$", entry.name)
                if match and match.group(1) >= stamp and entry.name not in dirs:
                    dirs[entry.name] = Path(entry.path)
                    print(f"{time.strftime('%H:%M:%S')}  OpenCode starts design {match.group(2)} · workspace mvp/agent-runs/{entry.name}/workspace")
                    quiet_since = time.monotonic()
            for name, folder in dirs.items():
                key = name[-1]
                workspace = folder / "workspace"
                for path in sorted(workspace.glob("*.sysml")) + [workspace / "answer.md"]:
                    if path.is_file() and files.get(str(path)) != path.stat().st_mtime:
                        files[str(path)] = path.stat().st_mtime
                        lines = len(path.read_text(encoding="utf-8", errors="replace").splitlines())
                        print(f"{time.strftime('%H:%M:%S')}  design {key} · OpenCode wrote {path.name} ({lines} lines)")
                        quiet_since = time.monotonic()
                for index, row in enumerate(validate_calls(workspace), 1):
                    if row["folder"] in checked:
                        continue
                    checked.add(row["folder"])
                    print(f"{time.strftime('%H:%M:%S')}  design {key} · {_validate_line(index, row)}")
                    quiet_since = time.monotonic()
            if not alive:
                break
            if time.monotonic() - quiet_since > 45:
                print(f"{time.strftime('%H:%M:%S')}  … OpenCode is still working ({time.monotonic() - started:.0f} s so far)")
                quiet_since = time.monotonic()
            time.sleep(2)
        print(f"\n← the shell answered after {time.monotonic() - started:.0f} s")
        if "error" in box:
            raise box["error"]
        body = box["body"]
        print()
        show_text(body.get("summary", ""))
        for key, item in sorted((body.get("data") or {}).items()):
            if isinstance(item, dict) and item.get("agent_workspace"):
                self.workspaces[key] = item["agent_workspace"]
        for key, workspace in sorted(self.workspaces.items()):
            calls = validate_calls(workspace)
            print(f"design {key}: OpenCode ran ./validate {len(calls)} time(s); last result "
                  f"{calls[-1]['status'] if calls else 'none'} · workspace {Path(workspace).relative_to(ROOT)}")
        code("bench/shell_service.py", "_designs", "_write", "_agent_design")
        code("agents/external/opencode_run.py", "run_opencode")
        code("agents/external/jail.py", "VALIDATE", "PROMPT_SUFFIX")
        self.out["design"] = body
        return body

    def prompt_cards(self) -> None:
        """The three read-only cards hanging off ③: what OpenCode was given to write from."""
        if not self._need("design"):
            return
        for part, title in (("rules", "Rules · Paper 3"), ("contract", "Attribute template · Paper 3"),
                            ("examples", "Retrieved examples or the similar project · Paper 2")):
            rule(f"Design pipeline · ③ shown · {title}")
            body = shell("/tool/prompt-part", {"run": self.run, "part": part})
            text = body.get("summary", "")
            show_text(text, limit=1500)
            if len(text) > 1500:
                fold(f"the whole {part} card", text)
        code("bench/shell_service.py", "tool_prompt_part")

    def opencode(self, key: str) -> None:
        """Inside OpenCode for one design: every step from its event log, then every ./validate it ran."""
        workspace = self.workspaces.get(key)
        if not workspace:
            print(f"No OpenCode workspace for design {key}; run the ③ cell first.")
            return
        workspace = Path(workspace)
        log = workspace.parent / "stdout.jsonl"
        rule(f"Inside OpenCode · design {key} · {log.relative_to(ROOT)}")
        events = []
        for line in log.read_text(encoding="utf-8", errors="replace").splitlines() if log.is_file() else []:
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        steps = sum(1 for event in events if event.get("type") == "step_start")
        tools = [event for event in events if event.get("type") == "tool_use"]
        commands = [str((((t.get("part") or {}).get("state") or {}).get("input") or {}).get("command", "")) for t in tools]
        print(f"{steps} model turns · {len(tools)} tool uses · {sum('./validate' in c for c in commands)} of them ./validate\n")
        for event in events:
            part = event.get("part") or {}
            when = datetime.fromtimestamp(event["timestamp"] / 1000).strftime("%H:%M:%S") if event.get("timestamp") else "        "
            if event.get("type") == "text" and (part.get("text") or "").strip():
                print(f"{when}  OpenCode › {part['text'].strip()[:600]}")
            elif event.get("type") == "tool_use":
                state = part.get("state") or {}
                given = state.get("input") or {}
                output = str(state.get("output") or "")
                tool = part.get("tool")
                if tool == "bash":
                    command = str(given.get("command", ""))
                    mark = "★ " if "./validate" in command else ""
                    print(f"{when}  {mark}$ {command[:400]}")
                    shown = output if mark else output[:300]
                    for out_line in shown.strip().splitlines()[: 40 if mark else 6]:
                        print(f"            {out_line[:200]}")
                elif tool in {"write", "edit"}:
                    path = str(given.get("filePath", ""))
                    body = str(given.get("content") or given.get("newString") or "")
                    print(f"{when}  {tool} {Path(path).name} ({len(body.splitlines())} lines)")
                elif tool == "read":
                    print(f"{when}  read {Path(str(given.get('filePath', ''))).name}")
                else:
                    print(f"{when}  {tool} {json.dumps(given, ensure_ascii=False)[:200]}")
        rows = validate_calls(workspace)
        rule(f"Every ./validate of design {key}: the official Pilot, one folder each under {workspace.relative_to(ROOT)}/validation")
        for index, row in enumerate(rows, 1):
            print(_validate_line(index, row))
        if not rows:
            print("OpenCode did not run ./validate for this design.")
        answer = workspace / "answer.md"
        if answer.is_file():
            fold(f"answer.md that OpenCode handed in for design {key}", answer.read_text(encoding="utf-8", errors="replace"))

    def validate(self) -> dict:
        """④ The pipeline does not take the writer's word: it parses what was handed in with the official Pilot again."""
        if not self._need("design"):
            return {}
        if self.writers and len(self.out.get("design") or {}) < 2:
            print("Hand in both designs first (writer A and writer B, each with hand_in()).")
            return {}
        rule("Design pipeline · ④ Official SysML v2 Pilot ⇄ repair (the pipeline's own check)")
        body = shell("/run/validate", {"run": self.run})
        print()
        show_text(body.get("summary", ""))
        session = INBOX / f"discover-{self.run}"
        for design in body.get("data") or []:
            key = design.get("key")
            who = "the writer's reply" if key in self.writers else "answer.md"
            print(f"\nDesign {key}: the pipeline took the ```sysml block of {who} and ran the official Pilot on it.")
            for attempt in design.get("attempts", []):
                print(f"  attempt {attempt['attempt']}: {attempt['status']} · Pilot run {attempt.get('run_id')}")
                for item in [d for d in attempt.get("diagnostics", []) if d.get("severity") == "ERROR"][:6]:
                    print(f"      line {item.get('line')}: {item.get('message')}")
            repairs = design.get("repair_rounds", 0)
            print(f"  repairs after hand-in: {repairs}" + (" (each one sends the complete error list back to the pipeline's model in one conversation; the writer is not called again)" if repairs else ""))
            handed = session / f"attempts-{key}" / "attempt-01.sysml"
            if key in self.writers:
                writer = self.writers[key]
                own = [row for row in writer.rounds if row.get("package") == f"Design{key}"]
                other = len(writer.rounds) - len(own)
                passes = [row for row in own if row["status"] == "PASS"]
                if not writer.rounds:
                    print("  The writer never called the Pilot; this is the first official parse of this text.")
                elif not own:
                    print(f"  The writer's {len(writer.rounds)} Pilot call(s) were all on other packages (experiments); Design{key} itself was never checked by the writer.")
                elif handed.is_file():
                    handed_sha = _sha(handed.read_text(encoding="utf-8", errors="replace"))
                    last = own[-1]
                    same = last["sha"] == handed_sha
                    print(f"  The writer's last Pilot call on Design{key} ({len(own)} on this design, {len(passes)} PASS"
                          f"{f'; {other} more on test packages' if other else ''}) said {last['status']} on text sha256 {last['sha']}."
                          f" The text the pipeline parsed (sha256 {handed_sha}) is {'that same text' if same else 'a different text: the model changed it after that check'}.")
                continue
            rows = validate_calls(self.workspaces.get(key, "")) if self.workspaces.get(key) else []
            if rows and handed.is_file():
                own = [row for row in rows if any(Path(name).name.startswith(f"Design{key}") for name in row["files"])]
                last = (own or rows)[-1]
                validated = [Path(name) for name in last["files"] if Path(name).name.startswith(f"Design{key}")] or [Path(name) for name in last["files"]][-1:]
                same = None
                if validated and validated[-1].is_file():
                    now = validated[-1].read_text(encoding="utf-8", errors="replace")
                    unchanged = hashlib.sha256(now.encode()).hexdigest() == last["hashes"].get(str(validated[-1]))
                    same = unchanged and _sha(now) == _sha(handed.read_text(encoding="utf-8", errors="replace"))
                print(f"  OpenCode's last ./validate said {last['status']} on {validated[-1].name if validated else '?'}."
                      f" The text the pipeline parsed is {'the same text' if same else 'not the same text' if same is False else 'not comparable'}"
                      f" (sha256 {_sha(handed.read_text(encoding='utf-8', errors='replace'))}).")
            elif not rows:
                print("  OpenCode ran no ./validate for this design; this is the first official parse.")
        code("bench/shell_service.py", "run_validate")
        code("bench/discover.py", "_validate_design", "repair_design")
        code("mvp/toolchain/validate.py", "validate_package")
        self.out["validate"] = body
        return body

    def align(self) -> dict:
        if not self._need("validate"):
            return {}
        self.out["align"] = self._step("⑤ Align with memory · Paper 1", "/run/align", ("bench/discover.py", "align"))
        return self.out["align"]

    def checks(self) -> dict:
        if not self._need("align"):
            return {}
        body = self._step("⑥ Checks + read-back", "/run/checks", ("bench/discover.py", "simulate"), ("bench/discover.py", "read_back"))
        for design in (body.get("data") or {}).get("designs", []):
            said = design.get("read_back_numbers") or {}
            if design.get("read_back"):
                fold(f"design {design.get('key')} · the model's read-back of its parsed file "
                     f"({sum(said.values())}/{len(said)} brief numbers restated)", design["read_back"])
        self.out["checks"] = body
        return body

    def route_checks(self) -> bool | None:
        if not self._need("checks"):
            return None
        rule("Design pipeline · Router “All four checks pass?”")
        first = self.out["checks"]["summary"].split()[0]
        self.passed = first == "pass"
        print("The router reads the checks card's text and asks: does it start with “pass”?")
        print(f"It starts with “{first}” → {'True: straight to ⑦ Review' if self.passed else 'False: Trade-offs, then ⑦ Review'}.")
        return self.passed

    def tradeoffs(self) -> dict:
        if self.passed is None:
            print("Run the router cell first.")
            return {}
        if self.passed:
            rule("Design pipeline · Trade-offs")
            print("Skipped: the router sent the run straight to ⑦ Review because the checks passed.")
            self.out["tradeoffs"] = {}
            return {}
        self.out["tradeoffs"] = self._step("Trade-offs (catalog parts only; code recomputes each)", "/run/tradeoffs",
                                           ("bench/discover.py", "propose_tradeoffs"))
        return self.out["tradeoffs"]

    def review(self) -> str | None:
        if not self._need("checks"):
            return None
        body = self._step("⑦ Diagram · Cameo export · review text", "/run/review", ("bench/discover.py", "gate_for"))
        self.result = body.get("summary", "")
        print(f"\nThis text is the flow's output (ChatOutput-review): Langflow hands it to the Agent as {self.card['name']}'s result.")
        self.out["review"] = body
        return self.result

    def recheck(self) -> None:
        """Run the official Pilot once more on the designs this run stored, through the Validate SysML flow's two cards."""
        if not self.run:
            print("No run yet.")
            return
        session = INBOX / f"discover-{self.run}"
        for key in ("A", "B"):
            path = session / f"Design{key}.sysml"
            rule(f"Check it yourself · official Pilot on {path.relative_to(ROOT)}")
            if not path.is_file():
                print("No such file: the design did not pass, or the run did not reach ④.")
                continue
            saved = shell("/tool/validate/save", {"sysml": path.read_text(encoding="utf-8"), "upstream": ""})
            print(saved["summary"])
            verdict = shell("/tool/validate/pilot", {"saved": saved["summary"]})
            print(verdict["summary"])

    def files(self) -> None:
        rule(f"Where run {self.run} left its files")
        if not self.run:
            print("No run yet.")
            return
        session = INBOX / f"discover-{self.run}"
        for path in (ROOT / "analysis" / f"discover-{self.run}.json", session, ROOT / "analysis" / "cameo-exports" / self.run):
            print(f"  {path.relative_to(ROOT)}{'' if path.exists() else '  (not written)'}")
        for key, workspace in sorted(self.workspaces.items()):
            print(f"  design {key} · OpenCode workspace {Path(workspace).relative_to(ROOT)} (event log ../stdout.jsonl)")
        for key, writer in sorted(self.writers.items()):
            print(f"  design {key} · written by the notebook-driven Langflow Agent · {len(writer.rounds)} Pilot call(s) · session file analysis/langflow-runs/{self.run}.json")
        print("Results page 2.3 shows the same run: http://127.0.0.1:8770/#s23")


# ---------------------------------------------------------------- the writer: the Pilot-only Langflow Agent, one turn per cell

PILOT_CARD_FILE = ROOT / "langflow" / "flows" / "2-coding-agents" / "langflow-agent-pilot-chat.json"
VALIDATE_FLOW_FILE = SHARED_FLOWS / "tool-validate-sysml.json"
SYSML_BLOCK = re.compile(r"```sysml\s*\n(.*?)```", re.S | re.I)


def load_pilot_card() -> dict:
    """The Agent card of “Langflow Agent, Pilot only chat” (project 2): its system prompt and limits, and the Validate flow
    its one Run Flow card points at, read from the flow files Langflow imported."""
    flow = json.loads(PILOT_CARD_FILE.read_text(encoding="utf-8"))
    nodes = {node["id"]: node["data"]["node"] for node in flow["data"]["nodes"] if node.get("type") == "genericNode"}
    agent = nodes["Agent-rtrc"]["template"]
    validate = json.loads(VALIDATE_FLOW_FILE.read_text(encoding="utf-8"))
    chat_input = next(item["id"] for item in validate["data"]["nodes"] if item["id"].startswith("ChatInput-"))
    flow_name = nodes["RunFlow-validate"]["template"]["flow_name_selected"]["value"]
    return {"flow": flow["name"], "agent_title": nodes["Agent-rtrc"]["display_name"], "system_prompt": agent["system_prompt"]["value"],
            "canvas_model": agent["model"]["value"][0]["name"], "max_iterations": agent["max_iterations"]["value"],
            "tool": {"name": tool_name(flow_name), "flow": flow_name, "flow_file": str(VALIDATE_FLOW_FILE.relative_to(ROOT)),
                     "key": f"{chat_input}~input_value",
                     "description": f"Tool designed to execute the flow '{flow_name}'. Flow details: {validate['description']}."}}


def _core(text: str) -> str:
    """The SysML inside the last ```sysml fence, or the text itself: what the Pilot and the pipeline's ④ actually parse."""
    blocks = SYSML_BLOCK.findall(text or "")
    return blocks[-1] if blocks else (text or "")


def _round_line(row: dict) -> str:
    head = f"Pilot call #{row['n']}: package {row.get('package') or '?'} · {row['status']} · sha256 {row['sha']}" + (f" · Pilot run {row['run_id']}" if row.get("run_id") else "")
    return "\n".join([head, *[f"      {line}" for line in row.get("errors", [])[:6]]])


class Writer:
    """Design A or B written by the Langflow Agent, Pilot only card, driven here one turn per cell.

    The same job the pipeline gives a Langflow writer (agent "langflow"): the card's own system prompt, the official
    Pilot as its one tool (the Validate flow's two cards), the model the Design pipeline's Start card presets, and the
    task text /run/prompt hands every writer. decide() is one model call; act() is one Pilot call. When the model stops
    calling the tool, its reply is the design, and hand_in() gives it to the pipeline through /run/written. The model
    is told nothing about the pipeline's later re-check; that check is ④, in its own cell."""

    def __init__(self, pipe: "Pipeline", key: str, *, think="inherit"):
        from agents.llm_local import local_tag
        self.pipe, self.key = pipe, key
        self.card = load_pilot_card()
        self.model = local_tag(pipe.preset["model"]) or pipe.preset["model"]
        self.think = pipe.agent.think if think == "inherit" else think
        self.stopped_at_cap = False
        tool = self.card["tool"]
        self.tool_key = tool["key"]
        self.tools = [{"type": "function", "function": {"name": tool["name"], "description": tool["description"], "parameters": {
            "type": "object", "required": ["flow_tweak_data"], "properties": {"flow_tweak_data": {
                "type": "object", "title": "Flow Tweak Data", "required": [tool["key"]],
                "properties": {tool["key"]: {"type": "string", "title": tool["key"]}}}}}}}]
        rule(f"Design pipeline · ③ design {key} · writer: {self.card['agent_title']}")
        body = shell("/run/prompt", {"run": pipe.run, "key": key, "adapt": pipe.branch == "reuse"})
        data = body["data"]
        self.task = data["message"]
        print()
        show_text(body["summary"])
        print(f"\nCard file        {PILOT_CARD_FILE.relative_to(ROOT)} (on the canvas this card runs {self.card['canvas_model']}; "
              f"the pipeline sets the writer's model at run time, here {self.model})")
        print(f"Model calls      at most {self.card['max_iterations']} for this design (the card's limit)")
        print(f"Its one tool     {tool['name']} → flow “{tool['flow']}” ({tool['flow_file']}): save the text as a file → official Pilot")
        print(f"Branch           {'adapt ' + data['baseline'] if data.get('adapt') and key == 'A' else 'written new'}")
        fold("the system prompt, exactly as the Pilot-only Agent card holds it", self.card["system_prompt"])
        fold(f"the task the pipeline hands the writer of design {key} (from /run/prompt)", self.task)
        code("bench/shell_service.py", "run_prompt", "_design_prompt")
        self.messages: list[dict] = [{"role": "system", "content": self.card["system_prompt"]}, {"role": "user", "content": self.task}]
        self.pending: list[dict] = []
        self.rounds: list[dict] = []
        self.model_calls = 0
        self.final: str | None = None
        self.final_sha: str | None = None
        self.handed = False
        self.started = time.monotonic()
        self.step = 0

    def decide(self) -> dict | None:
        """One model call: the model writes SysML and either calls the Pilot tool or hands in."""
        if self.handed:
            print(f"Design {self.key} is already handed in.")
            return None
        if self.pending:
            print("The writer's last Pilot call has not run yet. Run act() first.")
            return None
        if self.final is not None:
            print("The writer has finished; run hand_in().")
            return None
        if self.model_calls >= self.card["max_iterations"]:
            self.stopped_at_cap = True
            draft = self._last_draft()
            print(f"Stopped: {self.card['max_iterations']} model calls, the card's limit (Langflow's ModelCallLimitMiddleware would stop the card here too).")
            if draft:
                print(f"hand_in() hands in the model's last draft of Design{self.key} ({len(draft)} characters); ④ parses it and repairs on its errors.")
            else:
                print(f"The model never wrote a package named Design{self.key}; hand_in() has nothing to hand in.")
            self._finish(f"```sysml\n{draft.rstrip()}\n```" if draft else "")
            return None
        self.model_calls += 1
        self.step += 1
        rule(f"Design {self.key} · writer turn {self.step} · the model reads {len(self.messages)} messages and its one tool, then writes")
        print(f"→ POST {OLLAMA}/api/chat · model {self.model} · thinking switch: {'not sent (Ollama default)' if self.think is None else self.think}")
        message, _ = ollama_chat(self.model, self.messages, self.tools, self.think)
        calls = message["tool_calls"]
        self.messages.append({"role": "assistant", "content": message["content"], **({"tool_calls": calls} if calls else {})})
        if calls:
            self.pending = list(calls)
            print(f"\nThe model asks for {len(calls)} Pilot call(s) (nothing has run yet; act() runs the first):")
            for call in calls:
                text = str(((_arguments(call).get("flow_tweak_data") or {}).get(self.tool_key)) or "")
                print(f"  {self.card['tool']['name']} on {len(text)} characters · sha256 {_sha(_core(text)) if text.strip() else '(empty)'}")
        else:
            print("\nNo tool call: this reply is the design the writer hands in. Run hand_in().")
            self._finish(message["content"])
        return message

    def act(self) -> str | None:
        """One Pilot call: the Validate flow's two cards on the text the model passed; the verdict goes back to the model."""
        if not self.pending:
            print("Nothing to run: the model has not asked for a Pilot call. Run decide().")
            return None
        call = self.pending.pop(0)
        args = _arguments(call)
        text = str(((args.get("flow_tweak_data") or {}).get(self.tool_key)) or "")
        self.step += 1
        rule(f"Design {self.key} · writer turn {self.step} · tool {self.card['tool']['name']}")
        if not text.strip():
            receipt = f"Error: the tool's argument is flow_tweak_data {{\"{self.tool_key}\": <the SysML text>}}; it arrived empty."
            print(receipt)
            self.messages.append({"role": "tool", "content": receipt, "tool_name": self.card["tool"]["name"]})
            return receipt
        row = {"n": len(self.rounds) + 1, "sha": _sha(_core(text)), "text": _core(text), "status": "?", "errors": [], "package": None, "run_id": None}
        try:
            print(f"The flow “{self.card['tool']['flow']}” runs its 2 cards:\n\n[1/2] Save the pasted SysML as a file")
            saved = shell("/tool/validate/save", {"sysml": text, "upstream": ""})
            print(saved["summary"])
            print("\n[2/2] Official SysML v2 Pilot on that file")
            verdict = shell("/tool/validate/pilot", {"saved": saved["summary"]})
            receipt = verdict["summary"]
            print(receipt)
            data = verdict.get("data") or {}
            row["status"] = data.get("sysml_status") or "?"
            row["errors"] = [f"line {d.get('line')}: {d.get('message')}" for d in data.get("diagnostics", []) if d.get("severity", "ERROR") == "ERROR"]
            match = re.search(r"package (\w+) · run (\S+)", receipt)
            if match:
                row["package"], row["run_id"] = match.group(1), match.group(2)
        except ToolError as exc:
            receipt = f"Error: {exc}"
            row["status"], row["errors"] = "ERROR", [str(exc)]
            print(receipt)
        self.rounds.append(row)
        self.messages.append({"role": "tool", "content": receipt, "tool_name": self.card["tool"]["name"]})
        print(f"\nReturned to the model as the tool's result: {len(receipt)} characters. "
              + ("The model's next turn decides whether to fix and check again, or hand in." if row["status"] != "PASS" else "The model's next turn decides whether to hand in."))
        code("bench/shell_service.py", "tool_validate_save", "tool_validate_pilot")
        code("mvp/engine.py", "run_submitted_model")
        return receipt

    def run_until_reply(self, *, max_turns: int = 40) -> None:
        """decide() and act() in turn until the model hands in or the card's limit stops it."""
        for _ in range(max_turns):
            if self.final is not None or self.handed:
                return
            if self.pending:
                self.act()
            else:
                self.decide()
        print(f"Stopped after {max_turns} turns.")

    def _finish(self, text: str) -> None:
        self.final = text or ""
        block = SYSML_BLOCK.findall(self.final)
        self.final_sha = _sha(block[-1]) if block else None

    def _own(self, text: str) -> bool:
        return bool(re.search(rf"\bpackage\s+Design{self.key}\b", text or ""))

    def _last_draft(self) -> str:
        """The most recent text the model wrote that declares package Design<key>: in a reply, or passed to the Pilot tool."""
        for message in reversed(self.messages):
            if message.get("role") != "assistant":
                continue
            for call in reversed(message.get("tool_calls") or []):
                text = str(((_arguments(call).get("flow_tweak_data") or {}).get(self.tool_key)) or "")
                if self._own(text):
                    return _core(text)
            if self._own(message.get("content") or ""):
                return _core(message["content"])
        return ""

    def hand_in(self, *, fallback: bool = False) -> dict | None:
        """③ ends: the writer's reply goes to the pipeline through /run/written, as a Langflow writer's reply would; ④ parses it.
        A reply without a ```sysml block is handed in as it is, and ④ fails and repairs it, exactly as for a Langflow
        writer. fallback=True instead hands in the last text the writer's own Pilot call passed, and says so."""
        if self.handed:
            print(f"Design {self.key} was already handed in.")
            return None
        if self.final is None:
            print("The writer has not finished. Run decide()/act() or run_until_reply() first.")
            return None
        rule(f"Design {self.key} · hand in")
        text, writer = self.final, "notebook: Langflow Agent, Pilot only"
        passes = [row for row in self.rounds if row["status"] == "PASS"]
        own_passes = [row for row in passes if row.get("package") == f"Design{self.key}"]
        if getattr(self, "stopped_at_cap", False) and text:
            writer += " (stopped at the card's 20-call limit; its last draft is handed in)"
        if not SYSML_BLOCK.search(text):
            if fallback and own_passes:
                text = "```sysml\n" + own_passes[-1]["text"].rstrip() + "\n```"
                writer += " (reply had no sysml block; the last Design text its Pilot call passed is handed in)"
                print(f"The reply had no ```sysml block. fallback=True: handing in the last Design{self.key} text the writer's Pilot call passed instead.")
            elif text.strip():
                print("The reply has no ```sysml block. It is handed in as it is; ④ will report that and repair, as for any Langflow writer.")
            else:
                print("The reply is empty and the model never wrote a package named Design" + self.key + "; there is nothing to hand in."
                      + (" hand_in(fallback=True) would hand in its last Design text that passed the Pilot." if own_passes else ""))
                return None
        seconds = round(time.monotonic() - self.started, 1)
        tool_calls = [{"n": r["n"], "status": r["status"], "sha": r["sha"], "run_id": r["run_id"]} for r in self.rounds]
        try:
            body = shell("/run/written", {"run": self.pipe.run, "key": self.key, "text": text, "writer": writer,
                                          "model": self.pipe.preset["model"], "tool_calls": tool_calls, "seconds": seconds, "model_calls": self.model_calls})
        except ToolError as exc:
            print(f"The pipeline refused the hand-in: {exc}")
            return None
        self.handed = True
        self.final = text
        self.final_sha = _sha(_core(text)) if SYSML_BLOCK.search(text) else None
        self.pipe._handed_in(self.key, self)
        print()
        show_text(body["summary"])
        print(f"\n{self.model_calls} model call(s), {len(self.rounds)} Pilot call(s) by the writer ({len(passes)} PASS), {seconds} s."
              f" Handed-in sysml block sha256 {self.final_sha or '(none)'}"
              + (f"; the writer's last Pilot call was on sha256 {self.rounds[-1]['sha']} ({'the same text' if self.rounds[-1]['sha'] == self.final_sha else 'a different text'})" if self.rounds else ""))
        fold(f"the reply handed in for design {self.key}", text)
        code("bench/shell_service.py", "run_written")
        return body
