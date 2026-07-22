import os
from datetime import datetime, timezone
from pathlib import Path


def default_db_path() -> str:
    return os.environ.get(
        "AI_ENTERPRISE_OS_DB_PATH",
        str(Path(__file__).resolve().parents[2] / "data" / "ai_enterprise_os.sqlite3"),
    )


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
