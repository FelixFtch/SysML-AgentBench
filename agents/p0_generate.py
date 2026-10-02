"""P0: one-shot requirements → SysML v2, then the official toolchain. No repair loop.

The model writes exactly one package. Its text is saved unchanged and scored only by
the official parser. A language PASS is recorded as engineering UNKNOWN, because P0
supplies no domain contract. This is the bare-generation baseline in plan §7.1.
"""
from __future__ import annotations

import json
import os
import re
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mvp.engine import dump, run_submitted_model  # noqa: E402

SYSTEM = """You write SysML v2 textual notation and nothing else.
Rules:
- Output one fenced code block tagged sysml, and no prose before or after it.
- The file contains exactly one package whose name is given in the task.
- Import only standard-library packages you actually use, for example: private import ScalarValues::*;
- Use part def / part, port, attribute with a type, and requirement with a doc comment when the task states a requirement.
- Do not invent numeric limits the task did not state. If a number is missing, omit the value.
- Do not import packages that are not part of the SysML v2 standard library.
"""


def _extract_sysml(text: str) -> str:
    fenced = re.findall(r"```(?:sysml)?\s*\n(.*?)```", text, flags=re.S)
    body = fenced[-1] if fenced else text
    body = body.strip()
    if "package " not in body:
        raise ValueError("Model output contained no SysML package")
    return body + "\n"


def generate_once(requirements: str, package_name: str) -> dict:
    url = os.environ.get("MVP_LLM_URL", "")
    model = os.environ.get("MVP_LLM_MODEL", "")
    key = os.environ.get("MVP_LLM_API_KEY", "")
    if not url or not model:
        raise RuntimeError("Set MVP_LLM_URL and MVP_LLM_MODEL (see .env.example)")
    messages = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": f"Package name: {package_name}\n\nRequirements:\n{requirements}"},
    ]
    body = json.dumps({"model": model, "messages": messages, "temperature": 0.2,
                       "max_tokens": 4000}, ensure_ascii=False).encode()
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = "Bearer " + key
    request = urllib.request.Request(url, data=body, headers=headers, method="POST")
    with urllib.request.urlopen(request, timeout=180) as response:
        completion = json.loads(response.read(4_000_000))
    message = completion["choices"][0]["message"]
    source = _extract_sysml(message.get("content") or "")
    return {"source": source, "model": completion.get("model", model),
            "usage": completion.get("usage"), "finish_reason": completion["choices"][0].get("finish_reason")}


def run_p0(requirements: str, package_name: str, *, task_id: str = "adhoc") -> dict:
    started = datetime.now(timezone.utc)
    folder = ROOT / "mvp" / "agent-runs" / (started.strftime("%Y%m%dT%H%M%S") + "-p0-" + task_id)
    folder.mkdir(parents=True)
    generated = generate_once(requirements, package_name)
    source_path = folder / f"{package_name}.sysml"
    source_path.write_text(generated["source"], encoding="utf-8")
    validated = run_submitted_model([source_path], package_name, label=f"p0-{task_id}")
    record = {"configuration": "P0", "task_id": task_id, "package_name": package_name,
              "provider_model": generated["model"], "usage": generated["usage"],
              "finish_reason": generated["finish_reason"],
              "sysml_status": validated.get("sysml", {}).get("status"),
              "engineering_status": validated.get("status"),
              "named_elements": len(validated.get("model_elements") or []),
              "diagnostics": [d.get("message") for d in validated.get("sysml", {}).get("diagnostics", [])][:12],
              "engine_run": validated.get("run_id"), "source_path": str(source_path)}
    dump(folder / "p0-record.json", record)
    return record


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task", default="GEN-01")
    parser.add_argument("--requirements", type=Path, required=True)
    parser.add_argument("--package", default="HarborLink")
    args = parser.parse_args()
    text = args.requirements.read_text(encoding="utf-8")
    print(json.dumps(run_p0(text, args.package, task_id=args.task), ensure_ascii=False, indent=2))
