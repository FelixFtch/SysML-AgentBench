"""Exam board. Saved cells can be replayed. A run calls the model to write a new answer."""
from __future__ import annotations

import hashlib
import json
import re
import sys
import threading
import uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
HELD = ROOT / "bench" / "tasks" / "t4_maritime_isr" / "heldout"
PAGE = Path(__file__).with_name("exam_board.html")
NUM = re.compile(r"(\w+)\s*:\s*Real\s*=\s*([0-9]+(?:\.[0-9]+)?)")
STATIC = {
    "/board.css": ("board.css", "text/css; charset=utf-8"),
    "/board.js": ("board.js", "text/javascript; charset=utf-8"),
    "/scenes.js": ("scenes.js", "text/javascript; charset=utf-8"),
}
AGENT_RUNS = ROOT / "mvp" / "agent-runs"


def _read(path: Path, limit: int = 20000) -> str:
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")[:limit]


def _lines(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _task_dir(task_id: str) -> Path:
    return HELD / task_id


def _gold(task_id: str) -> str:
    gold = _task_dir(task_id) / "gold"
    parts = []
    for path in sorted(gold.rglob("*")):
        if path.is_file() and path.suffix in {".yaml", ".json", ".sysml", ".md"}:
            parts.append(f"# {path.relative_to(gold)}\n{_read(path)}")
    return "\n\n".join(parts) or "这道题的标准答案文件没有找到。"


def _requirements(task_id: str) -> str:
    return _read(_task_dir(task_id) / "input" / "requirements.md") or "题面文件没有找到。"


def _agent_dir(config: str, task_id: str, repeat: int) -> Path | None:
    found = sorted(path for path in (ROOT / "mvp" / "agent-runs").glob(f"*-{config}-{task_id}") if path.is_dir())
    if 1 <= repeat <= len(found):
        return found[repeat - 1]
    return None


def _model_text(row: dict) -> str:
    run = row.get("engine_run")
    if run:
        model = ROOT / "mvp" / "runs" / run / "model"
        if model.is_dir():
            files = sorted(model.glob("*.sysml"))
            if files:
                return "\n\n".join(f"# {path.name}\n{_read(path)}" for path in files)
    workspace = row.get("workspace")
    if workspace:
        root = Path(workspace)
        files = sorted(root.rglob("*.sysml"))
        answer = root / "answer.md"
        chunks = []
        if answer.is_file():
            chunks.append(_read(answer))
        chunks.extend(f"# {path.name}\n{_read(path)}" for path in files[:3])
        if chunks:
            return "\n\n".join(chunks)
    text_file = row.get("text_file")
    if text_file:
        return _read(Path(text_file))
    folder = row.get("_folder")
    if folder:
        response = Path(folder) / "response.txt"
        if response.is_file():
            return _read(response)
    return "这一格的答卷正文没有和成绩行连在一起。判定仍然来自当时保存的状态。"


def _watts(text: str) -> list[tuple[str, float]]:
    return [(name, float(value)) for name, value in NUM.findall(text)]


def _step(title: str, state: str, detail: str) -> dict:
    return {"title": title, "state": state, "detail": detail}


def _flow(row: dict, answer: str) -> list[dict]:
    kind = row.get("type")
    status = row.get("status")
    syntax = row.get("sysml_status")
    repairs = int(row.get("repair_rounds") or 0)
    calls = row.get("calls") or []
    call_line = "、".join(item.get("step", "") for item in calls) or "成绩行没有逐步调用记录"
    steps = [_step("发题面", "pass", "题面已发出。标准答案不在考生提示里。")]
    if status == "TIMEOUT":
        steps.append(_step("考生写模型", "fail", "到时限时没有交卷。这一格不计失败。"))
        steps.append(_step("官方语法", "skip", "没有答卷，语法没有判。"))
        steps.append(_step("按报错再改", "skip", "没有进入返工。"))
        steps.append(_step("读瓦数", "skip", "没有答卷。"))
        steps.append(_step("对照清单", "skip", "没有答卷，不计通过或失败。"))
        steps.append(_step("审批门", "skip", "没有答卷。"))
        steps.append(_step("存档", "pass", "超时记录已保存。"))
        return steps
    if kind in {"GEN", "MOD"}:
        steps.append(_step("考生写模型", "pass" if answer else "fail", f"记录的调用：{call_line}"))
        if syntax == "PASS":
            steps.append(_step("官方语法", "pass", "官方 Pilot 通过。这只表示语法通过。"))
        elif syntax == "FAIL":
            steps.append(_step("官方语法", "fail", "官方 Pilot 没有通过。清单不再往下判功率。"))
        else:
            steps.append(_step("官方语法", "fail", "没有得到官方语法结果。"))
        if repairs:
            end = "最后一次语法通过。" if syntax == "PASS" else "三次之后语法仍未通过。"
            steps.append(_step("按报错再改", "pass" if syntax == "PASS" else "fail", f"返工 {repairs} 次。{end}"))
        else:
            steps.append(_step("按报错再改", "skip", "这次没有返工。"))
    else:
        steps.append(_step("考生写模型", "pass", f"这道题交的是文字或 JSON，不交 SysML。调用：{call_line}"))
        steps.append(_step("官方语法", "skip", "读模型、提问和回读不跑官方语法。"))
        steps.append(_step("按报错再改", "skip", "这道题没有语法返工。"))
    numbers = _watts(answer)
    if numbers:
        shown = "，".join(f"{name} {value:g}" for name, value in numbers)
        steps.append(_step("读瓦数", "pass", f"从交卷里读到：{shown}。"))
    else:
        steps.append(_step("读瓦数", "skip", "这格交卷里没有 Real 瓦数，或正文没有连上。"))
    if status == "PASS":
        note = "和标准答案一致。"
        if row.get("engineering_status") == "FAIL":
            note = ("设计判定 FAIL：功率 41+25+12=78 W，上限 60 W，和标准答案预期的 FAIL 一致；必须保留的数都在，上限没改。题目判定通过。"
                    if row.get("task_id") == "MOD-05" else "设计判定 FAIL，和标准答案预期一致。题目判定通过。")
        if row.get("archived_status") and row["archived_status"] != status:
            note += f"（原判 {row['archived_status']}，按现行判分规则重算。）"
        steps.append(_step("对照清单", "pass", note))
    elif status == "FAIL":
        steps.append(_step("对照清单", "fail", "和标准答案不一致。"))
    else:
        steps.append(_step("对照清单", "skip", f"状态是 {status}。"))
    steps.append(_step("审批门", "skip", "这一格的成绩文件没有单独的审批记录。"))
    steps.append(_step("存档", "pass", "成绩行已在分析文件里。"))
    return steps


def _attach_folder(row: dict) -> dict:
    config = row.get("configuration")
    repeat = int(row.get("repeat") or 0)
    if config in {"P0", "P1", "P2", "P3"} and repeat:
        folder = _agent_dir(config, row["task_id"], repeat)
        if folder:
            row = dict(row)
            row["_folder"] = str(folder)
    return row


def _cells() -> list[dict]:
    from bench.board_facts import fill_calls
    from bench.rescore import apply, load
    table = load()
    rows = []
    flash = _lines(ROOT / "analysis/heldout-20261003T000045/results.jsonl")
    flash += _lines(ROOT / "analysis/heldout-20261003T001321/results.jsonl")
    for row in fill_calls(flash):
        rows.append({**apply("flash", row, table), "cohort": "主力矩阵", "cohort_id": "flash"})
    for row in _lines(ROOT / "analysis/opencode-20261003T001321/results.jsonl"):
        rows.append({**apply("opencode", row, table), "cohort": "OpenCode", "cohort_id": "opencode", "repeat": 1})
    for row in _lines(ROOT / "analysis/claude-qwen-20261003T014507/results.jsonl"):
        path = ROOT / "analysis/claude-qwen-20261003T014507" / f"{row['task_id']}.txt"
        rows.append({**apply("claude1", row, table), "cohort": "Claude 第一次", "cohort_id": "claude1", "repeat": 1, "text_file": str(path)})
    for row in _lines(ROOT / "analysis/claude-qwen-20261003T034819/results.jsonl"):
        path = ROOT / "analysis/claude-qwen-20261003T034819" / f"{row['task_id']}.txt"
        rows.append({**apply("claude2", row, table), "cohort": "Claude 重跑", "cohort_id": "claude2", "repeat": 1, "text_file": str(path)})
    for index, row in enumerate(rows):
        row["id"] = f"{row['cohort_id']}:{row.get('repeat')}:{row['task_id']}:{row.get('configuration')}:{index}"
    return rows


CELLS = _cells()
BY_ID = {row["id"]: row for row in CELLS}


def _rescored() -> dict:
    from bench.rescore import load
    return load()


RESCORED = _rescored()


def _jev_lookup() -> dict:
    path = ROOT / "analysis" / "jev-heldout-20261003.json"
    if not path.is_file():
        return {}
    table = {}
    for item in json.loads(path.read_text(encoding="utf-8")).get("cells") or []:
        table[(item["task_id"], item["configuration"], int(item["repeat"]))] = item
    return table


def _qwen_lookup() -> dict:
    table = {}
    for item in _lines(ROOT / "analysis" / "validator-all-max.jsonl"):
        table[(item["task_id"], item["configuration"], int(item["repeat"]))] = item
    return table


JEV = _jev_lookup()
QWEN = _qwen_lookup()


def _run_index() -> dict[str, list[tuple[datetime, Path]]]:
    index: dict[str, list[tuple[datetime, Path]]] = {}
    runs = ROOT / "mvp" / "runs"
    if not runs.is_dir():
        return index
    for path in runs.iterdir():
        result = path / "result.json"
        if not result.is_file():
            continue
        try:
            data = json.loads(result.read_text(encoding="utf-8"))
            created = datetime.fromisoformat(data["created_at"])
        except (ValueError, KeyError, TypeError):
            continue
        if data.get("case_name"):
            index.setdefault(data["case_name"], []).append((created, path))
    for items in index.values():
        items.sort()
    return index


RUNS_BY_LABEL = _run_index()


def _judges(row: dict) -> tuple[dict | None, dict | None]:
    if row.get("cohort_id") != "flash":
        return None, None
    key = (row["task_id"], row.get("configuration"), int(row.get("repeat") or 0))
    jev = JEV.get(key)
    qwen = QWEN.get(key)
    return (
        {"p_pass": jev.get("jev_p_pass"), "agree": jev.get("agree"), "false_pass": jev.get("false_pass")} if jev else None,
        {"verdict": qwen.get("validator_overall"), "agree": qwen.get("agree"), "false_pass": qwen.get("false_pass")} if qwen else None,
    )


def _attempt(path: Path, number: int, previous: str | None) -> dict:
    validation = path / "sysml" / "validation.json"
    data = json.loads(validation.read_text(encoding="utf-8")) if validation.is_file() else {}
    files = sorted((path / "model").glob("*.sysml"))
    text = _read(files[0], 4000) if files else ""
    sha = hashlib.sha256(text.encode()).hexdigest()[:12]
    return {
        "attempt": number, "run_id": path.name, "status": data.get("status") or "?",
        "diagnostics": [{"line": item.get("line"), "message": item.get("message", "")} for item in (data.get("diagnostics") or [])[:6]],
        "sha": sha, "same_as_previous": previous == sha, "text": text,
    }


def _attempt_paths(row: dict) -> list[Path]:
    """Run directories of every official parse behind one archived cell, oldest first. P1 cells have up to four."""
    if row.get("type") not in {"GEN", "MOD"}:
        return []
    config, task = row.get("configuration"), row["task_id"]
    paths: list[Path] = []
    if row.get("cohort_id") == "flash":
        folders = sorted(path for path in AGENT_RUNS.glob(f"*-{config}-{task}") if path.is_dir())
        repeat = int(row.get("repeat") or 0)
        if 1 <= repeat <= len(folders):
            start = datetime.strptime(folders[repeat - 1].name[:15], "%Y%m%dT%H%M%S").replace(tzinfo=timezone.utc)
            end = (datetime.strptime(folders[repeat].name[:15], "%Y%m%dT%H%M%S").replace(tzinfo=timezone.utc)
                   if repeat < len(folders) else None)
            paths = [path for created, path in RUNS_BY_LABEL.get(f"{config}-{task}", [])
                     if created >= start and (end is None or created < end)]
    if not paths and row.get("engine_run"):
        candidate = ROOT / "mvp" / "runs" / row["engine_run"]
        if candidate.is_dir():
            paths = [candidate]
    if not paths:
        item = RESCORED.get((row.get("cohort_id"), task, config, int(row.get("repeat") or 1))) or {}
        candidate = ROOT / "mvp" / "runs" / item["run"] if item.get("run") else None
        if candidate and candidate.is_dir():
            paths = [candidate]
    return paths


VERDICT_KEYS = ("status", "sysml_status", "engineering_status", "must_exist", "must_connect", "must_preserve",
                "checks", "checks_match", "invented_numbers", "reason")


def _verdict(row: dict, answer: str) -> dict:
    """What the scorer found in this cell's final answer: missing names and links, changed values, answer fields."""
    from bench.score_answer import score_answer
    from bench.score_task import score_run
    task_dir = HELD / row["task_id"]
    if not (task_dir / "case.yaml").is_file():
        return {}
    try:
        if row.get("type") in {"GEN", "MOD"}:
            paths = _attempt_paths(row)
            if not paths:
                return {"reason": "没有找到官方运行目录。"}
            scored = score_run(paths[-1], task_dir / "gold" / "assertions.yaml")
            return {key: scored[key] for key in VERDICT_KEYS if key in scored}
        return score_answer(task_dir, answer or "")
    except Exception as exc:  # a broken saved answer must not break the page
        return {"reason": f"{type(exc).__name__}: {exc}"}


def _repair_rounds(row: dict) -> int | None:
    """Score rows from the first batch did not record repair rounds; the P1 parse count still shows them."""
    if row.get("repair_rounds") is not None or row.get("cohort_id") != "flash" or row.get("configuration") != "P1":
        return row.get("repair_rounds")
    return max(len(_attempt_paths(row)) - 1, 0)


def _attempts(row: dict) -> list[dict]:
    attempts, previous = [], None
    for number, path in enumerate(_attempt_paths(row), 1):
        item = _attempt(path, number, previous)
        previous = item["sha"]
        attempts.append(item)
    return attempts


def _public(row: dict) -> dict:
    jev, qwen = _judges(row)
    return {
        "id": row["id"],
        "cohort": row["cohort"],
        "cohort_id": row.get("cohort_id"),
        "task_id": row["task_id"],
        "type": row.get("type"),
        "configuration": row.get("configuration"),
        "repeat": row.get("repeat"),
        "status": row.get("status"),
        "archived_status": row.get("archived_status"),
        "engineering_status": row.get("engineering_status"),
        "sysml_status": row.get("sysml_status"),
        "repair_rounds": _repair_rounds(row),
        "jev": {"agree": jev["agree"], "false_pass": jev["false_pass"]} if jev else None,
        "qwen": {"agree": qwen["agree"], "false_pass": qwen["false_pass"]} if qwen else None,
    }


def _detail(row: dict) -> dict:
    linked = _attach_folder(row)
    if linked.get("repair_rounds") is None and _repair_rounds(row):
        linked = {**linked, "repair_rounds": _repair_rounds(row)}
    answer = _model_text(linked)
    outline = ""
    retrieved = []
    folder = linked.get("_folder")
    if folder:
        outline = _read(Path(folder) / "outline.txt", 4000)
        notes = Path(folder) / "retrieved.json"
        if notes.is_file():
            retrieved = json.loads(notes.read_text(encoding="utf-8"))
    jev, qwen = _judges(row)
    calls = row.get("calls") or []
    return {
        **_public(row),
        "engineering_status": row.get("engineering_status"),
        "requirements": _requirements(row["task_id"]),
        "answer": answer,
        "gold": _gold(row["task_id"]),
        "outline": outline,
        "retrieved": retrieved,
        "attempts": _attempts(row),
        "tokens": sum((call.get("usage") or {}).get("total_tokens") or 0 for call in calls),
        "usage": {"input": sum((call.get("usage") or {}).get("prompt_tokens") or 0 for call in calls),
                  "output": sum((call.get("usage") or {}).get("completion_tokens") or 0 for call in calls)},
        "calls": [call.get("step") for call in calls],
        "steps": _flow(linked, answer),
        "verdict": _verdict(row, answer),
        "jev": jev,
        "qwen": qwen,
    }


JOBS: dict[str, dict] = {}
JOB_LOCK = threading.Lock()
BUSY = False
STYLE = ROOT / "mvp" / "app" / "style.css"


def _tasks() -> list[dict]:
    rows = []
    for line in (HELD / "index.jsonl").read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        item = json.loads(line)
        case_path = ROOT / item["path"] / "case.yaml"
        package = ""
        if case_path.is_file():
            for raw in case_path.read_text(encoding="utf-8").splitlines():
                if raw.startswith("package:"):
                    package = raw.split(":", 1)[1].strip()
        rows.append({"id": item["id"], "type": item["type"], "package": package})
    return rows


def _push(job: dict, step: dict) -> None:
    with JOB_LOCK:
        for index, item in enumerate(job["steps"]):
            if item["title"] == step["title"]:
                item["state"] = step["state"]
                item["detail"] = step["detail"]
                job["current"] = index
                job["phase"] = ""
                return
        job["steps"].append(step)
        job["current"] = len(job["steps"]) - 1
        job["phase"] = ""


def _phase(job: dict, title: str, detail: str) -> None:
    with JOB_LOCK:
        job["phase"] = title
        job["phase_detail"] = detail


def _gold_dir(task_dir: Path) -> str:
    gold = task_dir / "gold"
    parts = []
    if gold.is_dir():
        for path in sorted(gold.rglob("*")):
            if path.is_file() and path.suffix in {".yaml", ".json", ".sysml", ".md"}:
                parts.append(f"# {path.relative_to(gold)}\n{_read(path)}")
    return "\n\n".join(parts)


def _prepare_inbox(payload: dict) -> Path:
    kind = payload.get("type") or ""
    if kind not in {"GEN", "MOD", "QRY", "AMB", "RT"}:
        raise ValueError("类型要是 GEN、MOD、QRY、AMB、RT 之一。")
    requirements = (payload.get("requirements") or "").strip()
    gold = (payload.get("gold") or "").strip()
    if not requirements or not gold:
        raise ValueError("题面和标准答案都要有。")
    package = (payload.get("package") or "Inbox").strip()
    if kind in {"GEN", "MOD"} and not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", package):
        raise ValueError("包名要用字母开头，只能有字母、数字和下划线。")
    if kind == "QRY":
        json.loads(gold)
    else:
        import yaml
        parsed = yaml.safe_load(gold)
        if not isinstance(parsed, dict):
            raise ValueError("标准答案要是一份 YAML 对象。")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    folder = ROOT / "mvp" / "exam-inbox" / stamp
    (folder / "input").mkdir(parents=True)
    (folder / "gold").mkdir()
    case = {"id": f"INBOX-{stamp}", "type": kind, "package": package, "synthetic": True}
    import yaml
    (folder / "case.yaml").write_text(yaml.safe_dump(case, allow_unicode=True), encoding="utf-8")
    (folder / "input" / "requirements.md").write_text(requirements + "\n", encoding="utf-8")
    name = "answer.json" if kind == "QRY" else "assertions.yaml"
    (folder / "gold" / name).write_text(gold + "\n", encoding="utf-8")
    return folder


def _execute(task_dir: Path, config: str, job: dict) -> None:
    from agents.llm import chat, extract_sysml
    from agents.solve import SYSML_RULES, _answer, _retrieve, _task
    from bench.experiment import grade, load_env

    load_env()
    case, prompt = _task(task_dir)
    with JOB_LOCK:
        job["requirements"] = prompt
        job["gold"] = _gold_dir(task_dir)
        job["task_id"] = case["id"]
        job["type"] = case["type"]
        job["configuration"] = config
    _push(job, _step("发题面", "pass", "题面已交给考生。gold 目录没有放进提示。"))
    prefix: list[dict] = []
    if config in {"P2", "P3"}:
        notes = ""
        if config == "P3":
            _phase(job, "取笔记", "正在按题面里的词取笔记。笔记里没有标准答案。")
            found = _retrieve(prompt)
            notes = "\n\n".join(f"[{item['source']}]\n{item['text']}" for item in found)
            with JOB_LOCK:
                job["retrieved"] = found
            _push(job, _step("取笔记", "pass", f"取到 {len(found)} 段：" + "、".join(item["source"] for item in found)))
        _phase(job, "列提纲", "正在列提纲，这一步还不写 SysML。")
        outlined = chat([
            {"role": "system", "content": "List the parts, ports, connections, and attributes the task requires. Reply with one JSON object. Do not write SysML yet."},
            {"role": "user", "content": prompt if not notes else prompt + "\n\nReference notes:\n" + notes},
        ], max_tokens=1500)
        with JOB_LOCK:
            job["outline"] = outlined["text"]
        _push(job, _step("列提纲", "pass", "提纲已返回，下一步按提纲写模型。"))
        prefix = [{"role": "user", "content": "Outline:\n" + outlined["text"]},
                  {"role": "assistant", "content": "I will follow that outline."}]
    _phase(job, "考生写模型", "正在调用模型。这一步的提示里仍然没有标准答案。")
    written = _answer(case, prompt, prefix=prefix)
    text = written["text"]
    with JOB_LOCK:
        job["answer"] = text
    _push(job, _step("考生写模型", "pass", f"模型 {written.get('model') or ''} 已交卷。"))
    syntax = None
    rounds = 0
    run_dir = None
    if case["type"] in {"GEN", "MOD"}:
        from mvp.engine import run_submitted_model
        attempts = 4 if config == "P1" else 1
        previous_sha = None
        for attempt in range(attempts):
            _phase(job, "官方语法", f"正在用官方 Pilot 解析第 {attempt + 1} 份模型。")
            try:
                source = extract_sysml(text)
            except ValueError as exc:
                syntax = "FAIL"
                diagnostic = str(exc)
                entry = {"attempt": attempt + 1, "run_id": None, "status": "FAIL", "sha": "", "same_as_previous": False,
                         "diagnostics": [{"line": None, "message": diagnostic}], "text": text[:4000]}
            else:
                scratch = ROOT / "mvp" / "exam-inbox" / f"live-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}-{case['id']}"
                scratch.mkdir(parents=True, exist_ok=True)
                path = scratch / f"{case['package']}.sysml"
                path.write_text(source, encoding="utf-8")
                validated = run_submitted_model([path], case["package"], label=f"board-{case['id']}")
                run_dir = validated["run_dir"]
                syntax = validated["sysml"]["status"]
                diagnostic = "\n".join(item.get("message", "") for item in validated["sysml"].get("diagnostics", [])[:8])
                entry = _attempt(Path(run_dir), attempt + 1, previous_sha)
                model_dir = Path(run_dir) / "model"
                files = sorted(model_dir.glob("*.sysml")) if model_dir.is_dir() else []
                if files:
                    with JOB_LOCK:
                        job["answer"] = "\n\n".join(f"# {item.name}\n{_read(item)}" for item in files)
            previous_sha = entry["sha"]
            with JOB_LOCK:
                job.setdefault("attempts", []).append(entry)
            if syntax == "PASS" or attempt == attempts - 1:
                break
            rounds += 1
            _push(job, _step("官方语法", "fail", diagnostic or "官方语法没有通过。"))
            _phase(job, "按报错再改", f"第 {rounds} 次把官方报错发回模型。数字保持题面里的值。")
            repaired = chat([
                {"role": "system", "content": SYSML_RULES},
                {"role": "user", "content": prompt},
                {"role": "assistant", "content": text},
                {"role": "user", "content": "Official validation failed. Fix the model. Do not change numbers the task said to keep.\n" + diagnostic},
            ])
            text = repaired["text"]
            with JOB_LOCK:
                job["answer"] = text
            _push(job, _step("按报错再改", "pass", f"第 {rounds} 次修改已返回。发回模型的官方报错：{(diagnostic or '')[:400]}"))
        _push(job, _step("官方语法", "pass" if syntax == "PASS" else "fail",
                         "官方 Pilot 通过。这只表示语法通过。" if syntax == "PASS" else (diagnostic or "官方语法没有通过。")))
        if rounds == 0:
            _push(job, _step("按报错再改", "skip", "这次没有返工。"))
    else:
        _push(job, _step("官方语法", "skip", "这道题不交 SysML。"))
        _push(job, _step("按报错再改", "skip", "这道题没有语法返工。"))
    numbers = _watts(job.get("answer") or "")
    if numbers:
        _push(job, _step("读瓦数", "pass", "，".join(f"{name} {value:g}" for name, value in numbers)))
    else:
        _push(job, _step("读瓦数", "skip", "交卷里没有 Real 瓦数。"))
    _phase(job, "对照清单", "用标准答案核对交卷。这一步才读 gold。")
    solved = {"text": text, "run_dir": run_dir, "sysml_status": syntax}
    scored = grade(task_dir, solved)
    status = scored["status"]
    if status == "PASS":
        note = "和标准答案一致。"
        if scored.get("engineering_status") == "FAIL":
            note = "设计判定 FAIL，和标准答案预期一致；必须保留的数都在。题目判定通过。"
        _push(job, _step("对照清单", "pass", note))
    else:
        reason = scored.get("reason") or scored.get("missing") or ""
        preserve = scored.get("must_preserve") or {}
        if preserve.get("missing"):
            reason = "必须保留的数被改了：" + "，".join(f"{item['qualified_name']} 应为 {item['expected']}，实际 {item['actual']}" for item in preserve["missing"])
        _push(job, _step("对照清单", "fail", str(reason) or "和标准答案不一致。"))
    _push(job, _step("审批门", "skip", "这次运行没有人提交改限值的请求。"))
    _push(job, _step("存档", "pass", f"最终 {status}。运行目录：{run_dir or '无官方运行'}"))
    with JOB_LOCK:
        job["status_label"] = status
        job["sysml_status"] = syntax
        job["engineering_status"] = scored.get("engineering_status")
        job["verdict"] = {key: scored[key] for key in VERDICT_KEYS if key in scored} if case["type"] in {"GEN", "MOD"} else scored
        job["phase"] = ""


def _worker(payload: dict, job: dict) -> None:
    global BUSY
    from agents.llm import MODEL_OVERRIDE, USAGE_LOG, usage_summary
    MODEL_OVERRIDE.set(job["model"])
    calls: list[dict] = []
    USAGE_LOG.set(calls)
    try:
        if payload.get("mode") == "new":
            task_dir = _prepare_inbox(payload)
            config = payload.get("configuration") or "P0"
        else:
            task_id = payload.get("task_id") or ""
            task_dir = HELD / task_id
            if not (task_dir / "case.yaml").is_file():
                raise ValueError("没有这道现成题。")
            config = payload.get("configuration") or "P0"
        if config not in {"P0", "P1", "P2", "P3"}:
            raise ValueError("写法要是 P0、P1、P2、P3。")
        _execute(task_dir, config, job)
        with JOB_LOCK:
            if job.get("status") == "running":
                job["status"] = "done"
    except Exception as exc:
        _push(job, _step("存档", "fail", f"{type(exc).__name__}: {exc}"))
        with JOB_LOCK:
            job["status"] = "error"
            job["error"] = str(exc)
            job["phase"] = ""
    finally:
        with JOB_LOCK:
            job["usage"] = usage_summary(calls)
            BUSY = False


DISCOVER_STEPS = ("brief", "retrieve", "requirements", "source", "design", "syntax", "repair", "align", "simulate", "tradeoff", "readback", "gate")


def _discover_worker(brief: str, job: dict) -> None:
    global BUSY
    def progress(key: str, state: str, detail: str) -> None:
        with JOB_LOCK:
            for item in job["steps"]:
                if item["key"] == key:
                    item["state"] = state
                    item["detail"] = detail
            job["phase"] = key if state == "run" else ""
    try:
        from bench.discover import run
        record = run(brief, progress)
        with JOB_LOCK:
            job["record"] = record
            job["status"] = "done"
    except Exception as exc:
        with JOB_LOCK:
            job["status"] = "error"
            job["error"] = f"{type(exc).__name__}: {exc}"
            for item in job["steps"]:
                if item["state"] == "run":
                    item["state"] = "fail"
                    item["detail"] = job["error"]
    finally:
        with JOB_LOCK:
            BUSY = False


def _start_discover(brief: str) -> tuple[dict | None, str]:
    global BUSY
    brief = (brief or "").strip()
    if len(brief) < 20:
        return None, "简报至少写一句完整的任务，包括平台和要共享的信息。"
    with JOB_LOCK:
        if BUSY:
            return None, "上一次还在跑，等它走完再开下一次。"
        BUSY = True
        titles = {"brief": "任务简报", "retrieve": "① 检索记忆库", "requirements": "② 写需求", "source": "数字来源核对",
                  "design": "② 写设计 A / B", "syntax": "③ 官方校验", "repair": "按报错返工", "align": "④ 对齐",
                  "simulate": "⑤ 核算", "tradeoff": "权衡方案", "readback": "⑤ 读回", "gate": "⑥ 人决定"}
        job = {"id": uuid.uuid4().hex[:12], "kind": "discover", "status": "running", "phase": "requirements",
               "steps": [{"key": key, "title": titles[key], "state": "wait", "detail": "还没走到。"} for key in DISCOVER_STEPS],
               "brief": brief, "record": None, "error": ""}
        JOBS[job["id"]] = job
    threading.Thread(target=_discover_worker, args=(brief, job), daemon=True).start()
    return job, ""


MOD_TASKS = ("MOD-01", "MOD-02", "MOD-03", "MOD-04", "MOD-05")


def _mvp_case_file(task_id: str) -> Path | None:
    path = ROOT / "analysis" / f"mvp-case-latest-{task_id}.json"
    if path.is_file():
        return path
    legacy = ROOT / "analysis" / "mvp-case-latest.json"
    return legacy if task_id == "MOD-05" and legacy.is_file() else None


def _mvp_case_worker(job: dict, task_id: str) -> None:
    global BUSY
    try:
        import subprocess
        result = subprocess.run([sys.executable, str(ROOT / "bench" / "run_mvp_case.py"), task_id], capture_output=True, text=True, cwd=str(ROOT))
        latest = _mvp_case_file(task_id) or ROOT / "analysis" / f"mvp-case-latest-{task_id}.json"
        with JOB_LOCK:
            if result.returncode == 0 and latest.is_file():
                job["record"] = json.loads(latest.read_text(encoding="utf-8"))
                job["status"] = "done"
            else:
                job["status"] = "error"
                job["error"] = (result.stderr or result.stdout)[-600:]
    except Exception as exc:
        with JOB_LOCK:
            job["status"] = "error"
            job["error"] = f"{type(exc).__name__}: {exc}"
    finally:
        with JOB_LOCK:
            BUSY = False


def _start_mvp_case(task_id: str) -> tuple[dict | None, str]:
    global BUSY
    if task_id not in MOD_TASKS:
        return None, "题目要是 MOD-01 到 MOD-05 之一。"
    with JOB_LOCK:
        if BUSY:
            return None, "上一次还在跑，等它走完再开下一次。"
        BUSY = True
        job = {"id": uuid.uuid4().hex[:12], "kind": "mvp", "task_id": task_id, "status": "running", "record": None, "error": ""}
        JOBS[job["id"]] = job
    threading.Thread(target=_mvp_case_worker, args=(job, task_id), daemon=True).start()
    return job, ""


CONSOLE_MODELS = ("qwen3.8-flash", "qwen3.8-max")


def _start(payload: dict) -> tuple[dict | None, str]:
    global BUSY
    model = payload.get("model") or CONSOLE_MODELS[0]
    if model not in CONSOLE_MODELS:
        return None, "模型要是 qwen3.8-flash 或 qwen3.8-max。"
    with JOB_LOCK:
        if BUSY:
            return None, "上一次还在跑，等它走完再开下一次。"
        BUSY = True
        config = payload.get("configuration") or "P0"
        titles = (["发题面"] + (["取笔记"] if config == "P3" else []) + (["列提纲"] if config in {"P2", "P3"} else [])
                  + ["考生写模型", "官方语法", "按报错再改", "读瓦数", "对照清单", "审批门", "存档"])
        blank = [_step(title, "wait", "还没走到。") for title in titles]
        job = {"id": uuid.uuid4().hex[:12], "status": "running", "steps": blank, "current": 0, "attempts": [], "retrieved": [],
               "requirements": "", "answer": "", "gold": "", "phase": "发题面",
               "phase_detail": "正在读题面。", "error": "", "task_id": payload.get("task_id") or "新题",
               "configuration": payload.get("configuration") or "P0", "type": payload.get("type") or "",
               "cohort": "这次运行", "repeat": 1, "status_label": "RUNNING", "sysml_status": None,
               "engineering_status": None, "model": model, "verdict": {}, "usage": None}
        JOBS[job["id"]] = job
    threading.Thread(target=_worker, args=(payload, job), daemon=True).start()
    return job, ""


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args) -> None:
        return

    def _send(self, code: int, body: bytes, content_type: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path in {"/", "/index.html"}:
            self._send(200, PAGE.read_bytes(), "text/html; charset=utf-8")
            return
        if parsed.path == "/style.css":
            self._send(200, STYLE.read_bytes(), "text/css; charset=utf-8")
            return
        if parsed.path in STATIC:
            name, kind = STATIC[parsed.path]
            self._send(200, (ROOT / "bench" / name).read_bytes(), kind)
            return
        if parsed.path == "/api/memory":
            from bench.discover import load_memory
            self._send(200, json.dumps(load_memory(), ensure_ascii=False).encode(), "application/json; charset=utf-8")
            return
        if parsed.path == "/api/tasks":
            self._send(200, json.dumps(_tasks(), ensure_ascii=False).encode(), "application/json; charset=utf-8")
            return
        if parsed.path == "/api/cells":
            body = json.dumps([_public(row) for row in CELLS], ensure_ascii=False).encode()
            self._send(200, body, "application/json; charset=utf-8")
            return
        if parsed.path == "/api/cell":
            cell_id = parse_qs(parsed.query).get("id", [""])[0]
            row = BY_ID.get(cell_id)
            if not row:
                self._send(404, b"{}", "application/json")
                return
            body = json.dumps(_detail(row), ensure_ascii=False).encode()
            self._send(200, body, "application/json; charset=utf-8")
            return
        if parsed.path == "/api/facts":
            from bench.board_facts import facts
            self._send(200, json.dumps(facts(), ensure_ascii=False).encode(), "application/json; charset=utf-8")
            return
        if parsed.path == "/api/catalog":
            from bench.discover import CATALOG, budgets, brief_from
            query = parse_qs(parsed.query)
            choice = {key: (values[0] if key in {"visible_camera", "ir_camera", "computer", "uplink", "storage"} else float(values[0]))
                      for key, values in query.items() if values and values[0]}
            try:
                body = {"catalog": CATALOG, "budgets": budgets(choice), "brief": brief_from(choice)}
            except KeyError as exc:
                self._send(400, json.dumps({"error": f"目录里没有 {exc}"}, ensure_ascii=False).encode(), "application/json; charset=utf-8")
                return
            self._send(200, json.dumps(body, ensure_ascii=False).encode(), "application/json; charset=utf-8")
            return
        if parsed.path == "/api/discover-latest":
            latest = ROOT / "analysis" / "discover-latest.json"
            if not latest.is_file():
                self._send(404, b"{}", "application/json")
                return
            self._send(200, latest.read_bytes(), "application/json; charset=utf-8")
            return
        if parsed.path == "/api/mvp-case":
            task_id = parse_qs(parsed.query).get("task", ["MOD-05"])[0]
            latest = _mvp_case_file(task_id) if task_id in MOD_TASKS else None
            if not latest:
                self._send(404, b"{}", "application/json")
                return
            self._send(200, latest.read_bytes(), "application/json; charset=utf-8")
            return
        if parsed.path == "/api/job":
            job_id = parse_qs(parsed.query).get("id", [""])[0]
            with JOB_LOCK:
                job = JOBS.get(job_id)
                payload = dict(job) if job else None
            if not payload:
                self._send(404, b"{}", "application/json")
                return
            self._send(200, json.dumps(payload, ensure_ascii=False).encode(), "application/json; charset=utf-8")
            return
        self._send(404, b"not found", "text/plain")

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path not in {"/api/run", "/api/discover", "/api/mvp-run", "/api/approve"}:
            self._send(404, b"not found", "text/plain")
            return
        length = int(self.headers.get("Content-Length") or "0")
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
        except json.JSONDecodeError:
            self._send(400, '{"error":"不是 JSON"}'.encode(), "application/json")
            return
        if parsed.path == "/api/approve":
            from bench.discover import approve
            try:
                with JOB_LOCK:
                    result = approve(str(payload.get("run_id") or ""), str(payload.get("design") or ""))
            except ValueError as exc:
                self._send(409, json.dumps({"error": str(exc)}, ensure_ascii=False).encode(), "application/json; charset=utf-8")
                return
            self._send(200, json.dumps(result, ensure_ascii=False).encode(), "application/json; charset=utf-8")
            return
        if parsed.path == "/api/discover":
            job, error = _start_discover(payload.get("brief") or "")
        elif parsed.path == "/api/mvp-run":
            job, error = _start_mvp_case(str(payload.get("task_id") or "MOD-05"))
        else:
            job, error = _start(payload)
        if error:
            self._send(409, json.dumps({"error": error}, ensure_ascii=False).encode(), "application/json; charset=utf-8")
            return
        self._send(200, json.dumps({"id": job["id"]}, ensure_ascii=False).encode(), "application/json; charset=utf-8")


def main() -> None:
    server = ThreadingHTTPServer(("127.0.0.1", 8770), Handler)
    print("http://127.0.0.1:8770/", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
