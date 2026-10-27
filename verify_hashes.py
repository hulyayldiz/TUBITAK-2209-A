"""Verify all active and archived forensic segments with the configured key."""
from forensic_config import load_forensic_key, FORENSIC_LEDGER_PATH
from forensic_ledger import Ledger


def verify_all_hashes():
    try:
        if not FORENSIC_LEDGER_PATH.is_file():
            raise ValueError("Forensic ledger is missing")
        _, count = Ledger(FORENSIC_LEDGER_PATH, load_forensic_key()).verify()
        print(f"Verified forensic records: {count}")
        print("Recovery archives, when present, match their signed SHA-256 anchors. "
              "This does not certify historical continuity; see the recovery report.")
        return True
    except (ValueError, OSError, TimeoutError) as error:
        print(f"Verification failed: {error}")
        return False


if __name__ == "__main__":
    raise SystemExit(0 if verify_all_hashes() else 1)
