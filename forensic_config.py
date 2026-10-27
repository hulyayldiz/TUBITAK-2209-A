"""Shared forensic key configuration; never uses a public default key."""
import os
import secrets
from pathlib import Path
from dotenv import load_dotenv

FORENSIC_LEDGER_PATH = Path(__file__).resolve().parent / "forensic_ledger.jsonl"


def load_forensic_key():
    root = Path(__file__).resolve().parent
    load_dotenv(root / ".env")
    configured = os.getenv("FORENSIC_SECRET_KEY")
    if configured:
        return configured.encode("utf-8")
    key_path = root / ".forensic_secret"
    from forensic_ledger import file_lock
    with file_lock(key_path):
        if not key_path.exists():
            with key_path.open("x", encoding="ascii") as handle:
                handle.write(secrets.token_hex(32))
                handle.flush()
                os.fsync(handle.fileno())
            key_path.chmod(0o600)
        value = key_path.read_text(encoding="ascii").strip()
        if not value:
            raise ValueError("Forensic key file is empty")
    return value.encode("ascii")
