"""Create .langflow/secrets.env once: the Langflow superuser password and secret key, and the token the
Langflow nodes send to the RTRC shell service. The folder is gitignored; nothing is printed.

    python3 scripts/langflow_secrets.py
"""
from __future__ import annotations

import secrets
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FILE = ROOT / ".langflow" / "secrets.env"
KEYS = {
    "LANGFLOW_SUPERUSER": lambda: "rtrc",
    "LANGFLOW_SUPERUSER_PASSWORD": lambda: secrets.token_urlsafe(18),
    "LANGFLOW_SECRET_KEY": lambda: secrets.token_urlsafe(32),
    "RTRC_SHELL_TOKEN": lambda: secrets.token_urlsafe(24),
}


def read() -> dict[str, str]:
    if not FILE.is_file():
        return {}
    pairs = (line.split("=", 1) for line in FILE.read_text(encoding="utf-8").splitlines() if "=" in line and not line.startswith("#"))
    return {key.strip(): value.strip() for key, value in pairs}


def main() -> None:
    values = read()
    missing = {key: make() for key, make in KEYS.items() if not values.get(key)}
    if not missing:
        print(f"{FILE.relative_to(ROOT)} is complete")
        return
    FILE.parent.mkdir(parents=True, exist_ok=True)
    values.update(missing)
    FILE.write_text("".join(f"{key}={value}\n" for key, value in values.items()), encoding="utf-8")
    FILE.chmod(0o600)
    print(f"wrote {', '.join(sorted(missing))} to {FILE.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
