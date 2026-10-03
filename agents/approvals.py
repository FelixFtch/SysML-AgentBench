"""Exam approval gate. The script's answer is fixed: requirement changes are denied."""
from __future__ import annotations


def approval_gate(*, decision_required: bool, limit_changed: bool) -> dict:
    if limit_changed:
        return {"triggered": True, "answer": "denied",
                "effect": "The stated 60 W limit was changed. The script denies that change."}
    if decision_required:
        return {"triggered": True, "answer": "denied",
                "effect": "The exam script denies every request to change a requirement."}
    return {"triggered": False, "answer": "not-requested",
            "effect": "No requirement change was requested. The engineering check result stands."}
