"""The scored batches that the results page, STATUS.md and the report read. One place to change when a batch is added.

Four candidates on the 27 frozen tasks (bench/FREEZE.md):
- direct qwen3.8-flash and direct qwen3.8-max, approaches P0-P3, 3 repeats: 324 cells each;
- OpenCode and Claude Code on qwen3.8-flash, 3 repeats: 81 runs each, both in the sandbox of decision 026.
Some rows come from a rerun (RERUNS): the agents' ALN rows (decision 026) and the direct P3 cells (decision 028). The
rows a rerun replaces stay on disk and are listed by superseded_rows() with the rerun's reason. A batch folder that
holds results-r2.jsonl (saved answers re-scored under revision 2 by bench/rescore.py) is read from that file; its
results.jsonl stays as it was run.
Two agent batches of the same morning are discarded and listed in DISCARDED with the reason; the 2026-10-03 matrix
(24 tasks, old rules) is listed in ARCHIVE. Neither is mixed into the numbers above.
"""
from __future__ import annotations

import json
import re
from collections import defaultdict
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ANALYSIS = ROOT / "analysis"
AGENT_RUNS = ROOT / "mvp" / "agent-runs"
TYPES = ["GEN", "MOD", "ALN", "QRY", "AMB", "RT"]
CONFIGS = ["P0", "P1", "P2", "P3"]

COHORTS = {
    "flash": {"label": "Direct · qwen3.8-flash", "short": "flash", "kind": "direct", "model": "qwen3.8-flash",
              "glob": "heldout-qwen3.8-flash-20261006T070150"},
    "max": {"label": "Direct · qwen3.8-max", "short": "max", "kind": "direct", "model": "qwen3.8-max",
            "glob": "heldout-qwen3.8-max-20261006T070151"},
    "opencode": {"label": "OpenCode · qwen3.8-flash", "short": "OpenCode", "kind": "agent", "model": "qwen3.8-flash",
                 "glob": "opencode-jail-qwen3.8-flash-*"},
    "claude": {"label": "Claude Code · qwen3.8-flash", "short": "Claude Code", "kind": "agent", "model": "qwen3.8-flash",
               "glob": "claude-jail-qwen3.8-flash-*"},
}

# The Langflow exam columns (decision 035): the same 27 tasks sat by the agent flows of Langflow projects 2, 3 and 4 on
# qwen3.8-flash, run by bench/langflow_exam.py, scored by the frozen scorer. They are shown next to the four frozen
# candidates on results page 1.3 and are not part of the frozen score, STATUS.md or the report. A cohort without a
# batch folder yet shows "not run yet".
LANGFLOW_COHORTS = {
    "agent-pilot": {"label": "Langflow Agent, Pilot only · qwen3.8-flash", "short": "Langflow Agent, Pilot only", "kind": "agent", "model": "qwen3.8-flash",
                    "glob": "langflow-exam-agent-pilot-qwen3.8-flash-*", "flow": "Langflow Agent, Pilot only exam", "project": "2 · Coding agents without memory"},
    "opencode-memory": {"label": "OpenCode with memory · qwen3.8-flash", "short": "OpenCode with memory", "kind": "agent", "model": "qwen3.8-flash",
                        "glob": "langflow-exam-opencode-memory-qwen3.8-flash-*", "flow": "OpenCode with memory exam", "project": "3 · OpenCode with memory"},
    "agent-memory": {"label": "Langflow Agent with memory · qwen3.8-flash", "short": "Langflow Agent with memory", "kind": "agent", "model": "qwen3.8-flash",
                     "glob": "langflow-exam-agent-memory-qwen3.8-flash-*", "flow": "Langflow Agent with memory exam", "project": "4 · Langflow Agent with memory"},
}
ALL_COHORTS = {**COHORTS, **LANGFLOW_COHORTS}
AGENT_COHORTS = {cohort for cohort, spec in ALL_COHORTS.items() if spec["kind"] == "agent"}

DISCARDED = {
    "opencode-open": {"label": "OpenCode, workspace inside the repository", "model": "qwen3.8-flash",
                      "dir": "opencode-qwen3.8-flash-20261006T070152",
                      "reason": "The agent could read the whole repository and read answer keys in several runs, including the key "
                                "of the task it was solving (GEN-01, GEN-02, GEN-05). Not a clean score."},
    "claude-denied": {"label": "Claude Code, tools denied", "model": "qwen3.8-flash",
                      "dir": "claude-qwen3.8-flash-20261006T070153",
                      "reason": "Every Bash and Write call was denied (43 and 10), so the agent never ran the validator; "
                                "not the same setup as OpenCode."},
}

_ALN_RERUN = {"label": "ALN runs of the first sandboxed batch",
              "reason": "./validate passed the files in the order the agent gave them, and the Pilot's verdict depends on that "
                        "order: with the agent's own file first, 8 alignment packages (OpenCode 3, Claude Code 5) that fail in the "
                        "scorer's order (sources first) passed the agent's check and were submitted. Every ALN run of both agents "
                        "was rerun with ./validate in the scorer's order (decision 026); the rerun replaces these rows."}
_P3_RERUN = {"label": "P3 cells retrieved with cards that lacked documentation text", "configs": ["P3"],
             # The only tasks whose P3 retrieval changed with the new cards; every other P3 prompt was byte-identical.
             "inputs_changed": ["GEN-04", "GEN-05"],
             "reason": "The paper 2 replication (decision 027) showed that the authors' node text carries each element's "
                       "documentation and our retrieval cards did not. The cards now do, and every P3 cell of both direct "
                       "batches was rerun under freeze revision 2 (decision 028); the rerun replaces these rows."}
RERUNS = {"opencode": {"glob": "opencode-jail-aln-qwen3.8-flash-*", **_ALN_RERUN},
          "claude": {"glob": "claude-jail-aln-qwen3.8-flash-*", **_ALN_RERUN},
          "flash": {"glob": "heldout-p3doc-qwen3.8-flash-*", **_P3_RERUN},
          "max": {"glob": "heldout-p3doc-qwen3.8-max-*", **_P3_RERUN}}

ARCHIVE = {"label": "2026-10-03 matrix (24 tasks, old repair loop, old AMB/RT rules)", "pass": 224, "n": 288,
           "dirs": ["heldout-20261003T000045", "heldout-20261003T001321"],
           "note": "qwen3.8-flash, P1 repair with 3 rounds, the first 8 error lines only and a fresh conversation each time, re-scored once on 2026-10-03; "
                   "kept as the record of the old rules, not comparable cell for cell."}


def batch_dir(cohort: str) -> Path | None:
    """The newest result folder of a cohort (by name, which starts with the run stamp)."""
    found = sorted(path for path in ANALYSIS.glob(ALL_COHORTS[cohort]["glob"]) if (path / "results.jsonl").is_file())
    return found[-1] if found else None


def rerun_dir(cohort: str) -> Path | None:
    """The newest rerun folder of a cohort."""
    if cohort not in RERUNS:
        return None
    found = sorted(path for path in ANALYSIS.glob(RERUNS[cohort]["glob"]) if (path / "results.jsonl").is_file())
    return found[-1] if found else None


def rerun_scope(cohort: str) -> dict:
    """What a cohort's rerun replaces: {"configs": [...]} for the direct P3 rerun, {"tasks": [...]} for the agents'
    ALN rerun (the task list is in the rerun's summary.json); {} when there is no rerun."""
    folder = rerun_dir(cohort)
    if not folder:
        return {}
    if RERUNS[cohort].get("configs"):
        return {"configs": list(RERUNS[cohort]["configs"])}
    tasks = json.loads((folder / "summary.json").read_text(encoding="utf-8")).get("tasks")
    return {"tasks": sorted(tasks) if isinstance(tasks, list) else []}


def _replaced(row: dict, scope: dict) -> bool:
    return row.get("configuration") in scope.get("configs", ()) or row["task_id"] in scope.get("tasks", ())


def results_file(folder: Path) -> Path:
    rescored = folder / "results-r2.jsonl"
    return rescored if rescored.is_file() else folder / "results.jsonl"


def _lines(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _start(folder: Path) -> str:
    return json.loads((folder / "summary.json").read_text(encoding="utf-8")).get("started") or folder.name[-15:]


@lru_cache(maxsize=None)
def _direct_folders(model: str, start: str) -> dict[tuple[str, str], list[str]]:
    """Run folders of one direct batch, keyed by (approach, task), oldest first. Two batches ran at the same time,
    so a folder is assigned by the model recorded in its solve.json; repeats are in folder order."""
    pattern = re.compile(r"^(\d{8}T\d{6})(?:-[0-9a-f]{4})?-(P[0-3])-(.+)$")
    groups: dict[tuple[str, str], list[str]] = defaultdict(list)
    for folder in AGENT_RUNS.iterdir():
        match = pattern.match(folder.name)
        if not match or match.group(1) < start:
            continue
        solve = folder / "solve.json"
        if solve.is_file() and json.loads(solve.read_text(encoding="utf-8")).get("provider_model") == model:
            groups[(match.group(2), match.group(3))].append(folder.name)
    return {key: sorted(value) for key, value in groups.items()}


def rows(cohort: str) -> list[dict]:
    """Score rows of one cohort with cohort id and label; direct rows also get their run folder (`_folder`)."""
    spec = ALL_COHORTS[cohort]
    folder = batch_dir(cohort)
    if not folder:
        return []
    out = []
    lines = [(row, folder) for row in _lines(results_file(folder))]
    rerun = rerun_dir(cohort)
    if rerun:
        scope = rerun_scope(cohort)
        lines = [(row, batch) for row, batch in lines if not _replaced(row, scope)]
        lines += [(row, rerun) for row in _lines(results_file(rerun))]
    for row, batch in lines:
        row = {**row, "cohort_id": cohort, "cohort": spec["label"], "model": spec["model"], "batch": batch.name}
        if spec["kind"] == "direct":
            names = _direct_folders(spec["model"], _start(batch)).get((row["configuration"], row["task_id"])) or []
            repeat = int(row.get("repeat") or 0)
            if 1 <= repeat <= len(names):
                row["_folder"] = str(AGENT_RUNS / names[repeat - 1])
        out.append(row)
    return out


def discarded_rows(key: str) -> list[dict]:
    return _lines(ANALYSIS / DISCARDED[key]["dir"] / "results.jsonl")


def superseded_rows(cohort: str) -> list[dict]:
    """Rows of a cohort's first batch that its rerun replaces."""
    folder = batch_dir(cohort)
    scope = rerun_scope(cohort)
    if not folder or not scope:
        return []
    return [row for row in _lines(results_file(folder)) if _replaced(row, scope)]


def usage_of_row(row: dict) -> dict:
    """Tokens of one cell: direct rows carry per-call usage, agent rows one usage block."""
    if row.get("calls") is not None and row.get("usage") is None:
        total = {"input": 0, "cached": 0, "output": 0, "calls": 0}
        for call in row.get("calls") or []:
            usage = call.get("usage") or {}
            total["input"] += usage.get("prompt_tokens") or 0
            total["cached"] += (usage.get("prompt_tokens_details") or {}).get("cached_tokens") or 0
            total["output"] += usage.get("completion_tokens") or 0
            total["calls"] += 1
        return total
    usage = row.get("usage") or {}
    if usage.get("model_usage"):
        # Claude Code's own per-model block; the first runner's "input" left out the cached tokens.
        slots = usage["model_usage"].values()
        return {"input": sum((s.get("inputTokens") or 0) + (s.get("cacheReadInputTokens") or 0) + (s.get("cacheCreationInputTokens") or 0) for s in slots),
                "cached": sum(s.get("cacheReadInputTokens") or 0 for s in slots),
                "output": sum(s.get("outputTokens") or 0 for s in slots), "calls": usage.get("turns") or 0}
    return {"input": usage.get("input") or 0, "cached": usage.get("cached") or 0, "output": usage.get("output") or 0,
            "calls": usage.get("calls") or usage.get("turns") or 0}


def side_results() -> dict:
    """SysEngBench and PURE per candidate: the newest side-<bench>-<candidate>-<model>-* folder of each."""
    out: dict[str, dict] = {"sysengbench": {}, "pure": {}}
    pairs = {"flash": ("direct", "qwen3.8-flash"), "max": ("direct", "qwen3.8-max"),
             "opencode": ("opencode", "qwen3.8-flash"), "claude": ("claude", "qwen3.8-flash")}
    for bench in out:
        for cohort, (candidate, model) in pairs.items():
            found = sorted(ANALYSIS.glob(f"side-{bench}-{candidate}-{model}-*"))
            if not found:
                continue
            folder = found[-1]
            meta = json.loads((folder / "summary.json").read_text(encoding="utf-8"))
            items = _lines(folder / "results.jsonl")
            usage = {"input": 0, "cached": 0, "output": 0, "calls": 0}
            for item in items:
                block = item.get("usage") or {}
                if "by_model" in block:
                    for slot in block["by_model"].values():
                        usage["input"] += slot.get("prompt_tokens") or 0
                        usage["cached"] += slot.get("cached_tokens") or 0
                        usage["output"] += slot.get("completion_tokens") or 0
                        usage["calls"] += slot.get("calls") or 0
                else:
                    usage["input"] += block.get("input") or 0
                    usage["cached"] += block.get("cached") or 0
                    usage["output"] += block.get("output") or 0
                    usage["calls"] += block.get("calls") or block.get("turns") or 0
            entry = {"folder": folder.name, "model": model, "usage": usage, "prompts": len(items),
                     "errors": sum(1 for item in items if item.get("error"))}
            if bench == "sysengbench":
                entry.update({"correct": sum(item.get("correct") or 0 for item in items), "n": sum(item.get("n") or 0 for item in items),
                              "always_b": meta.get("always_B_on_subset"), "questions": meta.get("questions"),
                              "repeats": meta.get("repeats"), "subset": meta.get("subset"), "sha256": meta.get("sha256")})
            else:
                entry.update({"pass": sum(item.get("status") == "PASS" for item in items), "n": len(items)})
            out[bench][cohort] = entry
    return out
