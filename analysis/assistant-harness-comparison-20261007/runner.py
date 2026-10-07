"""Run the comparison script on one assistant flow; append one JSON line per turn to <tag>.jsonl."""
import json
import subprocess
import sys
import time

FLOW, TAG = sys.argv[1], sys.argv[2]
OUT = f"/tmp/rtrc-compare/{TAG}.jsonl"
WF = ["python3", "/tmp/rtrc-compare/wf2.py"]

TURNS = [
    ("1", "记忆里有哪些项目？每个的功率上限是多少？", 300),
    ("2", "我想给船加个传感器，你看怎么改。", 300),
    ("3", "在 20261003T150116 那个设计上改：红外相机保持 7 W，上传速率降到 12 Mbps，别的数字不变。先把你会发给管线的 brief 给我看，先别跑。", 400),
    ("4", "确认，跑吧。", 1700),
    ("5", "先不写入记忆。把这个运行记录为 Send back，理由是：对比测试。", 400),
    ("6", "如果把 20261003T150116 的 28 W 可见光相机拿掉，换成一个 30 W 的激光雷达，总功率还在 60 W 以内吗？算给我看。", 300),
]
REPEATS = [("6r1", TURNS[5][1], 300), ("6r2", TURNS[5][1], 300)]


def chat(session, text, limit):
    started = time.time()
    proc = subprocess.run(WF + ["chat", FLOW, session, text, str(limit)], capture_output=True, text=True)
    try:
        result = json.loads(proc.stdout.strip().splitlines()[-1])
    except Exception:  # noqa: BLE001
        result = {"status": "error", "raw": (proc.stdout + proc.stderr)[-800:]}
    result["wall_seconds"] = round(time.time() - started, 1)
    if result.get("status") == "suspended":
        pending = json.loads(subprocess.run(WF + ["pending", FLOW], capture_output=True, text=True).stdout.strip().splitlines()[-1])
        mine = [p for p in pending if p.get("job_id") == result.get("job_id")]
        result["pending"] = mine
        if mine:
            resumed = subprocess.run(WF + ["resume", result["job_id"], mine[0]["request_id"], "reject", session], capture_output=True, text=True)
            try:
                result["after_reject"] = json.loads(resumed.stdout.strip().splitlines()[-1])
            except Exception:  # noqa: BLE001
                result["after_reject"] = {"raw": resumed.stdout[-600:]}
    return result


with open(OUT, "a", encoding="utf-8") as out:
    session = f"cmp-{TAG}-main"
    for turn, text, limit in TURNS:
        result = chat(session, text, limit)
        result.update({"turn": turn, "question": text})
        out.write(json.dumps(result, ensure_ascii=False) + "\n"); out.flush()
        print(f"[{TAG}] turn {turn}: {result.get('status')} {result.get('seconds')}s tools={[t['name'] for t in result.get('tools', [])]}", flush=True)
    for turn, text, limit in REPEATS:
        result = chat(f"cmp-{TAG}-{turn}", text, limit)
        result.update({"turn": turn, "question": text})
        out.write(json.dumps(result, ensure_ascii=False) + "\n"); out.flush()
        print(f"[{TAG}] turn {turn}: {result.get('status')} {result.get('seconds')}s tools={[t['name'] for t in result.get('tools', [])]}", flush=True)
print(f"[{TAG}] done")
