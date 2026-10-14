"""RTRC Kev classify: the requirement-sentence judge of the Kev flows (project 7).

One card, stateless: the sentences from the sub-flow's Chat Input go to the Kev decision service (the laptop-scale
Jev clone of tools/jev-arena/kev, 127.0.0.1:8009, POST /v1/systemone) as one noul question per sentence, in batches of
40 — the same wording the jev-arena pilot used — and the card returns one verdict per sentence: requirement yes or no
with the probability. Kev is a decision model, not a chat model: milliseconds per batch, one attempt, no retries; when
the service is not running the card raises a clear error that says how to start it, so a flow fails fast instead of
hanging or retrying in a loop.
"""
import json
import os
import re
import urllib.error
import urllib.request

from lfx.custom.custom_component.component import Component
from lfx.io import MessageInput, Output
from lfx.schema.data import Data
from lfx.schema.message import Message

KEV_URL = os.environ.get("KEV_URL", "http://127.0.0.1:8009")
BATCH = 40  # sentences per request, the chunk size of the jev-arena pilot
YES = 0.5  # a sentence is a requirement when Kev's probability of yes reaches this
CRIT_TRUE = "A testable statement of what the software system shall, must, should, or will do, or a constraint on its quality or environment"
CRIT_FALSE = "Headings, background, explanation, rationale, definitions, plans, or any other non-requirement sentence"


def _sentences(value) -> list[str]:
    """The tool's argument: a JSON list of sentences, one sentence per line, or pasted running text."""
    if isinstance(value, list):
        lines = [str(getattr(item, "text", item) or "").strip() for item in value]
    else:
        text = str(getattr(value, "text", value) or "").strip()
        if text.startswith("["):
            try:
                parsed = json.loads(text)
                lines = [str(item).strip() for item in parsed] if isinstance(parsed, list) else text.splitlines()
            except ValueError:
                lines = text.splitlines()
        else:
            lines = text.splitlines()
    lines = [line for line in lines if line]
    if len(lines) == 1:  # one line holding several sentences: split on the sentence ends
        pieces = [piece.strip() for piece in re.split(r"(?<=[.!?;])\s+", lines[0]) if piece.strip()]
        if len(pieces) > 1:
            return pieces
    return lines


def _judge(sentences: list[str]) -> list[dict]:
    """One verdict per sentence from the Kev service: yes/no on being a requirement statement, with the probability."""
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
            raise ValueError(f"The Kev service at {KEV_URL} refused the request (HTTP {exc.code}): "
                             f"{exc.read()[:300].decode('utf-8', 'replace')}") from exc
        except urllib.error.URLError as exc:
            raise ValueError(f"The Kev service is not reachable at {KEV_URL} ({exc.reason}); start it with scripts/kev_up.sh") from exc
        for number, sentence in enumerate(batch, 1):
            answer = (body.get("answers") or {}).get(str(start + number)) or {}
            probability = answer.get("noul")
            if not isinstance(probability, (int, float)):
                raise ValueError(f"The Kev service returned no verdict for sentence {start + number}")
            verdicts.append({"sentence": sentence, "requirement": bool(float(probability) >= YES),
                             "probability": round(float(probability), 4)})
    return verdicts


class RtrcKevClassify(Component):
    display_name = "RTRC Kev classify"
    description = ("Judge whether sentences are software requirement statements with the Kev decision service: one "
                   "yes/no question per sentence, in batches of 40, milliseconds per batch.")
    icon = "wand"
    name = "RtrcKevClassify"

    inputs = [
        MessageInput(name="text", display_name="Sentences",
                     info="From the sub-flow's Chat Input: the sentences to judge, one per line (a JSON list or pasted running text work too)."),
    ]
    outputs = [
        Output(display_name="Message", name="message", method="as_message"),
        Output(display_name="Data", name="data", method="as_data"),
    ]

    def _result(self) -> list[dict]:
        if getattr(self, "_cached", None) is None:
            sentences = _sentences(self.text)
            if not sentences:
                raise ValueError("No sentences to judge; give one sentence per line")
            verdicts = _judge(sentences)
            yes = sum(1 for item in verdicts if item["requirement"])
            self._cached = verdicts
            self.status = f"Kev · {len(verdicts)} sentence(s): {yes} requirement, {len(verdicts) - yes} not"
        return self._cached

    def as_message(self) -> Message:
        return Message(text="\n".join(f"{'yes' if item['requirement'] else 'no'} ({item['probability']:.2f}) — {item['sentence']}"
                                      for item in self._result()))

    def as_data(self) -> Data:
        return Data(data={"verdicts": self._result()})
