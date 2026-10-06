"""RTRC Exam step: shows one step of an exam cell (page 1.1 / 1.4) from the cell record, and passes the record on.
No service call: the cell record comes from RTRC Exam cell."""
from lfx.custom.custom_component.component import Component
from lfx.io import DataInput, DropdownInput, Output
from lfx.schema.data import Data
from lfx.schema.message import Message

STEPS = ["Issue task", "Retrieve notes", "Outline", "Write answer", "Official syntax", "Repair from errors",
         "Read values", "Check against key", "Approval gate", "Archive", "Tool calls (agents)"]


def _record(value) -> dict:
    return dict(getattr(value, "data", None) or (value if isinstance(value, dict) else {}))


class RtrcExamStep(Component):
    display_name = "RTRC Exam step"
    description = "One step of the exam cell, from the cell record: its state, the official errors, the verdict or the agent's tool calls."
    icon = "list-checks"
    name = "RtrcExamStep"

    inputs = [
        DataInput(name="cell", display_name="Cell record"),
        DropdownInput(name="step", display_name="Step", options=STEPS, value=STEPS[0]),
    ]
    outputs = [
        Output(display_name="Cell record", name="cell_out", method="pass_on"),
        Output(display_name="This step", name="message", method="show"),
    ]

    def show(self) -> Message:
        record = _record(self.cell)
        if self.step == "Tool calls (agents)":
            trace = record.get("tool_trace") or []
            text = (f"{len(trace)} tool call(s) in the sandbox\n" + "\n".join(f"  {item.get('tool')}: {item.get('target')}" for item in trace[:60])
                    if trace else "No tool calls: this cell was not written by a sandboxed agent, or its log has none.")
        else:
            steps = [item for item in record.get("steps") or [] if item.get("title") == self.step]
            if not steps:
                text = f"{self.step}: not part of this cell (for example Outline in P0 or P1, Retrieve notes outside P3)."
            else:
                text = "\n".join(f"{self.step}: {item.get('state')}\n{item.get('detail') or ''}" for item in steps)
            if self.step in {"Official syntax", "Repair from errors"}:
                for attempt in record.get("attempts") or []:
                    first = (attempt.get("diagnostics") or [{}])[0].get("message", "") if attempt.get("status") != "PASS" else ""
                    text += f"\n  attempt {attempt.get('attempt')}: {attempt.get('status')}{' · ' + str(first)[:160] if first else ''}"
            if self.step == "Write answer":
                text += "\n\n" + str(record.get("answer") or "")[:3000]
            if self.step == "Check against key":
                verdict = record.get("verdict") or {}
                for key in ("must_exist", "must_connect", "must_preserve"):
                    missing = (verdict.get(key) or {}).get("missing")
                    if missing:
                        text += f"\n  {key.replace('_', ' ')}: missing {missing}"
                if verdict.get("reason"):
                    text += f"\n  {verdict['reason']}"
        self.status = text
        return Message(text=text)

    def pass_on(self) -> Data:
        return Data(data=_record(self.cell))
