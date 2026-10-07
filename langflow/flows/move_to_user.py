"""Give everything RTRC in Langflow to one user: the project and its flows, the Qwen provider credentials, the
enabled-models list, the knowledge base rtrc_memory (row, ingestion runs and files) and the rtrc-assistant MCP server.

    .venv-langflow/bin/python langflow/flows/move_to_user.py FelixFang

Langflow keeps credentials, knowledge bases and MCP servers per user, so a flow owned by one user cannot use another
user's provider key or knowledge base. Run this once for the account people log in with, then restart Langflow
(the knowledge-base files move to ~/.langflow/knowledge_bases/<username>/). Values are moved, never printed.
"""
from __future__ import annotations

import shutil
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DB = ROOT / ".venv-langflow" / "lib" / "python3.12" / "site-packages" / "langflow" / "langflow.db"
KB_ROOT = Path.home() / ".langflow" / "knowledge_bases"
PROJECT = "RTRC SysML-AgentBench"
VARIABLES = ("OPENAI_COMPATIBLE_BASE_URL", "OPENAI_COMPATIBLE_API_KEY", "__enabled_models__")
KNOWLEDGE_BASE = "rtrc_memory"
MCP_SERVER = "rtrc-assistant"


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

    # The project and every flow in any project of that name, whoever owns them; one project remains, owned by the target.
    folders = list(cur.execute("SELECT id, user_id FROM folder WHERE name = ?", (PROJECT,)))
    if folders:
        keep = next((fid for fid, uid in folders if uid == target), folders[0][0])
        for fid, _ in folders:
            cur.execute("UPDATE flow SET user_id = ?, folder_id = ? WHERE folder_id = ?", (target, keep, fid))
            if fid != keep:
                cur.execute("DELETE FROM folder WHERE id = ?", (fid,))
        cur.execute("UPDATE folder SET user_id = ? WHERE id = ?", (target, keep))
        # Two flows with the same name: keep the most recently updated one.
        for (name,) in list(cur.execute("SELECT name FROM flow WHERE folder_id = ? GROUP BY name HAVING count(*) > 1", (keep,))):
            rows = list(cur.execute("SELECT id FROM flow WHERE folder_id = ? AND name = ? ORDER BY updated_at DESC", (keep, name)))
            for (fid,) in rows[1:]:
                cur.execute("DELETE FROM flow WHERE id = ?", (fid,))
        report.append(f"project {PROJECT}: {cur.execute('SELECT count(*) FROM flow WHERE folder_id = ?', (keep,)).fetchone()[0]} flows")

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

    # The knowledge base: the row, its ingestion runs and its files (the directory is rooted by username).
    row = cur.execute("SELECT user_id FROM knowledge_base WHERE name = ?", (KNOWLEDGE_BASE,)).fetchone()
    if row and row[0] != target:
        old_owner = next(name for name, uid in users.items() if uid == row[0])
        cur.execute("UPDATE knowledge_base SET user_id = ? WHERE name = ?", (target, KNOWLEDGE_BASE))
        cur.execute("UPDATE ingestion_run SET user_id = ? WHERE kb_name = ?", (target, KNOWLEDGE_BASE))
        old_dir, new_dir = KB_ROOT / old_owner / KNOWLEDGE_BASE, KB_ROOT / username / KNOWLEDGE_BASE
        if old_dir.is_dir() and not new_dir.exists():
            new_dir.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(old_dir), str(new_dir))
        report.append(f"knowledge base {KNOWLEDGE_BASE}: moved from {old_owner} (files {new_dir})")
    else:
        report.append(f"knowledge base {KNOWLEDGE_BASE}: " + ("already owned by the user" if row else "absent"))

    # The assistant's MCP server registration.
    rows = list(cur.execute("SELECT id, user_id FROM mcp_server WHERE name = ?", (MCP_SERVER,)))
    if rows and not any(uid == target for _, uid in rows):
        cur.execute("UPDATE mcp_server SET user_id = ? WHERE id = ?", (target, rows[0][0]))
        report.append(f"mcp server {MCP_SERVER}: moved")
    elif rows:
        cur.execute("DELETE FROM mcp_server WHERE name = ? AND user_id != ?", (MCP_SERVER, target))
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
