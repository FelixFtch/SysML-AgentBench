"""Give everything RTRC in Langflow to one user: the six projects and their flows, the Qwen provider credentials, the
enabled-models list, the knowledge base rtrc_memory (row, ingestion runs and files) and the rtrc-assistant MCP
registration used by the Langflow-Agent flows.

    .venv-langflow/bin/python langflow/flows/move_to_user.py FelixFang

Langflow keeps credentials, knowledge bases and MCP registrations per user, so a flow owned by one user cannot use
another user's provider key or knowledge base. Run this once for the account people log in with, then restart
Langflow (the knowledge-base files move to ~/.langflow/knowledge_bases/<username>/). Values are moved, never printed.
Flows with a retired name (catalog.RETIRED) and the empty project of decisions 030 to 034 are removed, whoever owns them.
"""
from __future__ import annotations

import shutil
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from catalog import OLD_PROJECT, PROJECTS, RETIRED  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
DB = ROOT / ".venv-langflow" / "lib" / "python3.12" / "site-packages" / "langflow" / "langflow.db"
KB_ROOT = Path.home() / ".langflow" / "knowledge_bases"
PROJECT_NAMES = [name for name, _, _ in PROJECTS]
VARIABLES = ("OPENAI_COMPATIBLE_BASE_URL", "OPENAI_COMPATIBLE_API_KEY", "OLLAMA_BASE_URL", "__enabled_models__")
KNOWLEDGE_BASE = "rtrc_memory"
MCP_SERVER = "rtrc-assistant"


def _move_project(cur, project: str, target: str) -> int:
    """Every flow in any project of that name, whoever owns it, ends in one project owned by the target. A user cannot
    hold two flows with one name (an import run as the superuser creates a second copy of each flow), so of two flows
    with the same name the most recently updated one is kept, the other deleted, before the move. Returns the flow count."""
    folders = list(cur.execute("SELECT id, user_id FROM folder WHERE name = ?", (project,)))
    if not folders:
        return 0
    keep = next((fid for fid, uid in folders if uid == target), folders[0][0])
    marks = ",".join("?" * len(folders))
    flows = list(cur.execute(f"SELECT id, name, updated_at FROM flow WHERE folder_id IN ({marks}) ORDER BY updated_at DESC", [fid for fid, _ in folders]))
    keepers: dict[str, str] = {}
    for flow_id, name, _ in flows:
        if name in keepers:
            cur.execute("DELETE FROM flow WHERE id = ?", (flow_id,))
        else:
            keepers[name] = flow_id
    for flow_id in keepers.values():
        cur.execute("UPDATE flow SET user_id = ?, folder_id = ? WHERE id = ?", (target, keep, flow_id))
    for fid, _ in folders:
        if fid != keep:
            cur.execute("DELETE FROM folder WHERE id = ?", (fid,))
    cur.execute("UPDATE folder SET user_id = ? WHERE id = ?", (target, keep))
    return len(keepers)


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    username = sys.argv[1]
    con = sqlite3.connect(DB)
    cur = con.cursor()
    users = {name: uid for uid, name in cur.execute("SELECT id, username FROM user")}
    if username not in users:
        sys.exit(f"No Langflow user {username!r}; users: {sorted(users)}")
    target = users[username]
    report = []

    # Flows of the earlier single project that still carry a retired name go first, whoever owns them; a flow with a
    # current name that is still in the old project is left for the import to move (it keeps the newest copy).
    marks = ",".join("?" * len(RETIRED))
    removed = cur.execute(f"DELETE FROM flow WHERE name IN ({marks})", RETIRED).rowcount
    if removed:
        report.append(f"retired flows removed: {removed}")
    for project in PROJECT_NAMES:
        count = _move_project(cur, project, target)
        if count:
            report.append(f"project {project}: {count} flows")
    for fid, in list(cur.execute("SELECT id FROM folder WHERE name = ?", (OLD_PROJECT,))):
        left = cur.execute("SELECT COUNT(*) FROM flow WHERE folder_id = ?", (fid,)).fetchone()[0]
        if left == 0:
            cur.execute("DELETE FROM folder WHERE id = ?", (fid,))
            report.append(f"project {OLD_PROJECT}: removed (empty)")
        else:
            report.append(f"project {OLD_PROJECT}: kept, {left} flow(s) still in it")

    # Provider credentials and the enabled-models list: the target's own rows are replaced by the moved ones.
    for name in VARIABLES:
        rows = list(cur.execute("SELECT id, user_id FROM variable WHERE name = ?", (name,)))
        source = next((vid for vid, uid in rows if uid != target), None)
        if source is None:
            report.append(f"variable {name}: " + ("already owned by the user" if rows else "absent"))
            continue
        cur.execute("DELETE FROM variable WHERE name = ? AND user_id = ?", (name, target))
        cur.execute("UPDATE variable SET user_id = ? WHERE id = ?", (target, source))
        cur.execute("DELETE FROM variable WHERE name = ? AND user_id != ?", (name, target))
        report.append(f"variable {name}: moved")

    # The knowledge base: the row, its ingestion runs and its files (the directory is rooted by username). When the
    # user already owns one, copies that setup_knowledge.py created for another account (an import run as the
    # superuser makes an empty one) are removed, so the Knowledge page shows one rtrc_memory.
    rows = list(cur.execute("SELECT user_id FROM knowledge_base WHERE name = ?", (KNOWLEDGE_BASE,)))
    owners = [uid for (uid,) in rows]
    new_dir = KB_ROOT / username / KNOWLEDGE_BASE
    if rows and target not in owners:
        old_owner = next(name for name, uid in users.items() if uid == owners[0])
        cur.execute("UPDATE knowledge_base SET user_id = ? WHERE name = ? AND user_id = ?", (target, KNOWLEDGE_BASE, owners[0]))
        cur.execute("UPDATE ingestion_run SET user_id = ? WHERE kb_name = ? AND user_id = ?", (target, KNOWLEDGE_BASE, owners[0]))
        old_dir = KB_ROOT / old_owner / KNOWLEDGE_BASE
        if old_dir.is_dir() and not new_dir.exists():
            new_dir.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(old_dir), str(new_dir))
        report.append(f"knowledge base {KNOWLEDGE_BASE}: moved from {old_owner} (files {new_dir})")
        owners = [target] + owners[1:]
    elif rows:
        report.append(f"knowledge base {KNOWLEDGE_BASE}: already owned by the user")
    else:
        report.append(f"knowledge base {KNOWLEDGE_BASE}: absent")
    for uid in owners:
        if uid == target:
            continue
        other = next(name for name, user_id in users.items() if user_id == uid)
        cur.execute("DELETE FROM knowledge_base WHERE name = ? AND user_id = ?", (KNOWLEDGE_BASE, uid))
        cur.execute("DELETE FROM ingestion_run WHERE kb_name = ? AND user_id = ?", (KNOWLEDGE_BASE, uid))
        shutil.rmtree(KB_ROOT / other / KNOWLEDGE_BASE, ignore_errors=True)
        report.append(f"knowledge base {KNOWLEDGE_BASE}: {other}'s copy removed")

    # The MCP registration of the Langflow-Agent comparison flow (the OpenCode assistant reaches the server directly).
    rows = list(cur.execute("SELECT id, user_id FROM mcp_server WHERE name = ?", (MCP_SERVER,)))
    if rows and not any(uid == target for _, uid in rows):
        cur.execute("UPDATE mcp_server SET user_id = ? WHERE id = ?", (target, rows[0][0]))
        report.append(f"mcp server {MCP_SERVER}: moved")
    if rows:
        cur.execute("DELETE FROM mcp_server WHERE name = ? AND user_id != ?", (MCP_SERVER, target))
        if any(uid == target for _, uid in rows):
            report.append(f"mcp server {MCP_SERVER}: already owned by the user")
    else:
        report.append(f"mcp server {MCP_SERVER}: absent (run setup_assistant.py)")

    con.commit()
    print(f"Moved to {username}:")
    for line in report:
        print("  " + line)
    print("Restart Langflow so the knowledge base is read from its new directory.")


if __name__ == "__main__":
    main()
