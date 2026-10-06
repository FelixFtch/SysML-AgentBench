"""RTRC MOD step: shows one step of a MOD change run (page 2.4) from the case record and passes the record on.
The "Limit check" message starts with "moved" or "unchanged", so an If-Else can stop for a person when a stated limit moved."""
from lfx.custom.custom_component.component import Component
from lfx.io import DataInput, DropdownInput, Output
from lfx.schema.data import Data
from lfx.schema.message import Message

VIEWS = ["Task and baseline", "Model change", "Official syntax", "Task and design verdicts", "Limit check", "Read-back"]


def _record(value) -> dict:
    return dict(getattr(value, "data", None) or (value if isinstance(value, dict) else {}))


class RtrcModStep(Component):
    display_name = "RTRC MOD step"
    description = "One step of the MOD change chain, from the case record."
    icon = "list-checks"
    name = "RtrcModStep"

    inputs = [
        DataInput(name="case", display_name="Case record"),
        DropdownInput(name="view", display_name="Step", options=VIEWS, value=VIEWS[0]),
    ]
    outputs = [
        Output(display_name="Case record", name="case_out", method="pass_on"),
        Output(display_name="This step", name="message", method="show"),
    ]

    def show(self) -> Message:
        case = _record(self.case)
        if self.view == "Task and baseline":
            text = f"{case.get('task_id')}: the task statement and the baseline model the model starts from\n\n{str(case.get('requirements') or '')[:1500]}\n\n{str(case.get('baseline') or '')[:2500]}"
        elif self.view == "Model change":
            text = f"Model {case.get('model')} wrote the changed model\n\n{str(case.get('answer') or '')[:3000]}"
        elif self.view == "Official syntax":
            text = f"Official SysML v2 Pilot: {case.get('sysml_status')}" + "".join(f"\n  {item.get('message')}" for item in case.get("diagnostics") or [])
        elif self.view == "Task and design verdicts":
            checks = case.get("checks") or []
            text = (f"Task verdict {case.get('status')} (the answer key's checklist) · design verdict {case.get('engineering_status')} (the budget)\n"
                    + "".join(f"\n  {item.get('id', '')} {item.get('status', '')} {item.get('actual', '')} / {item.get('limit', '')}" for item in checks))
        elif self.view == "Limit check":
            moved = case.get("limit_in_model") != case.get("limit_in_baseline")
            text = (f"{'moved' if moved else 'unchanged'} · stated limit {case.get('limit_in_baseline')} in the baseline, {case.get('limit_in_model')} in the answer"
                    + (" · a person must decide" if moved else " · no approval needed"))
        else:
            mentions = case.get("round_trip_mentions") or {}
            text = f"Read-back restates {sum(mentions.values())} of {len(mentions)} numbers in the model\n\n{str(case.get('round_trip') or '')[:2000]}"
        self.status = text
        return Message(text=text)

    def pass_on(self) -> Data:
        return Data(data=_record(self.case))
