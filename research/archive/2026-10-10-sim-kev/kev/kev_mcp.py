"""MCP tool for the Kev requirement classifier: one tool, classify_requirement, mounted by the OpenCode-with-memory
Kev flows of langflow/flows/7-kev-tools/ as their `kev` MCP server, next to the `rtrc` server of tools/assistant_mcp.py.

    python3 tools/kev_mcp.py            # streamable HTTP on 127.0.0.1:8793/mcp

The sentences go to the Kev decision service (the laptop-scale Jev clone of tools/jev-arena/kev, 127.0.0.1:8009,
POST /v1/systemone) as one noul question per sentence in batches of 40 — the same wording the jev-arena pilot used —
and the tool returns one verdict per sentence: requirement yes or no with the probability. Kev is a decision model,
not a chat model: milliseconds per batch, one attempt, no retries; when the service is not running the tool raises a
clear error that says how to start it (scripts/kev_up.sh starts both). The tool decides nothing and writes nothing.
"""
from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.request

from mcp.server.mcpserver import MCPServer

KEV_URL = os.environ.get("KEV_URL", "http://127.0.0.1:8009")
BATCH = 40  # sentences per request, the chunk size of the jev-arena pilot
YES = 0.5  # a sentence is a requirement when Kev's probability of yes reaches this
CRIT_TRUE = "A testable statement of what the software system shall, must, should, or will do, or a constraint on its quality or environment"
CRIT_FALSE = "Headings, background, explanation, rationale, definitions, plans, or any other non-requirement sentence"

server = MCPServer(
    "kev",
    instructions=("The Kev requirement classifier: judge whether sentences are software requirement statements, in one "
                  "batch, with a probability per sentence. Needs the Kev decision service on 127.0.0.1:8009 "
                  "(scripts/kev_up.sh)."),
)


def _sentences(text: str) -> list[str]:
    """One sentence per line, a JSON array, or pasted running text split on the sentence ends."""
    lines = None
    stripped = (text or "").strip()
    if stripped.startswith("["):
        try:
            parsed = json.loads(stripped)
            if isinstance(parsed, list):
                lines = [str(item).strip() for item in parsed]
        except ValueError:
            lines = None
    if lines is None:
        lines = stripped.splitlines()
    lines = [line for line in lines if line]
    if len(lines) == 1:
        pieces = [piece.strip() for piece in re.split(r"(?<=[.!?;])\s+", lines[0]) if piece.strip()]
        if len(pieces) > 1:
            return pieces
    return lines


def _judge(sentences: list[str]) -> list[dict]:
    verdicts: list[dict] = []
    for start in range(0, len(sentences), BATCH):
        batch = sentences[start:start + BATCH]
        state = ("Excerpt of a software requirements specification document. Each line is one sentence with its identifier in brackets:\n"
                 + "\n".join(f"[{start + i}] {sentence}" for i, sentence in enumerate(batch, 1)))
        questions = {str(start + i): {"type": "noul",
                                      "instructions": f'Is sentence [{start + i}] a software requirement statement? Sentence [{start + i}]: "{sentence}"',
                                      "criteria": {"true": CRIT_TRUE, "false": CRIT_FALSE}}
                     for i, sentence in enumerate(batch, 1)}
        request = urllib.request.Request(KEV_URL + "/v1/systemone", data=json.dumps({"model": "kev-latest", "state": state,
                                                                                     "questions": questions}).encode(),
                                         method="POST", headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                body = json.loads(response.read() or b"{}")
        except urllib.error.HTTPError as exc:
            raise RuntimeError(f"The Kev service at {KEV_URL} refused the request (HTTP {exc.code}): "
                               f"{exc.read()[:300].decode('utf-8', 'replace')}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"The Kev service is not reachable at {KEV_URL} ({exc.reason}); start it with scripts/kev_up.sh") from exc
        for number, sentence in enumerate(batch, 1):
            answer = (body.get("answers") or {}).get(str(start + number)) or {}
            probability = answer.get("noul")
            if not isinstance(probability, (int, float)):
                raise RuntimeError(f"The Kev service returned no verdict for sentence {start + number}")
            verdicts.append({"sentence": sentence, "requirement": bool(float(probability) >= YES),
                             "probability": round(float(probability), 4)})
    return verdicts


@server.tool(description=(
    "Judge whether sentences are software requirement statements, in one batch. sentences: the sentences to judge, "
    "one per line (a JSON array or pasted running text work too). Returns one verdict per sentence — requirement yes "
    "or no with the probability — from the Kev decision service, a small classifier that answers in milliseconds, "
    "not a chat model; it never writes anything. Call it whenever the engineer asks whether a sentence or a line is "
    "a requirement."))
def classify_requirement(sentences: str) -> str:
    lines = _sentences(sentences)
    if not lines:
        raise ValueError("No sentences to judge; give one sentence per line")
    verdicts = _judge(lines)
    return json.dumps({"verdicts": verdicts, "counts": {"requirement": sum(1 for v in verdicts if v["requirement"]),
                                                        "not": sum(1 for v in verdicts if not v["requirement"])}},
                      ensure_ascii=False, indent=1)


if __name__ == "__main__":
    port = int(os.environ.get("KEV_MCP_PORT", "8793"))
    print(f"kev MCP on http://127.0.0.1:{port}/mcp", file=sys.stderr, flush=True)
    server.run(transport="streamable-http", host="127.0.0.1", port=port)
