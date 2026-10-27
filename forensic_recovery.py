"""Explicit legacy migration. Original bytes and chain breaks remain recorded.

No fallback key is used for new records. Recovery requires the original key and
refuses records that cannot be verified, even as a separately restarted chain.
"""
import hashlib
import hmac
import json
import os
from pathlib import Path

from forensic_ledger import Ledger, file_lock


def recover_legacy_ledger(path, legacy_key, new_key):
    path = Path(path).resolve()
    if hmac.compare_digest(legacy_key, new_key):
        raise ValueError('Recovery requires a new private key')
    with file_lock(path):
        if list(path.parent.glob(path.name + '.segment-*.jsonl')):
            raise ValueError('Segmented ledgers require a separate migration')
        raw = path.read_bytes()
        head, count, restarts = '0' * 64, 0, []
        for number, line in enumerate(raw.decode('utf-8').splitlines(), 1):
            entry = json.loads(line)
            if entry['level'] == 'RECOVERY':
                raise ValueError('Ledger was already migrated')
            content = f"{entry['timestamp']} - {entry['level']} - {entry['message']}"

            def matches(previous):
                digest = hmac.new(legacy_key,
                    f"{previous}{content}{entry['salt']}".encode(), hashlib.sha256).hexdigest()
                return hmac.compare_digest(digest, entry['chain_hmac'])

            if not matches(head):
                if number == 1 or not matches('0' * 64):
                    raise ValueError(f'Unverifiable legacy record: {number}')
                restarts.append(number)
            head, count = entry['chain_hmac'], count + 1
        if not count:
            raise ValueError('Legacy ledger is empty')
        digest = hashlib.sha256(raw).hexdigest()
        archive = path.with_name(path.name + '.legacy-' + digest + '.jsonl')
        report = archive.with_suffix('.report.json')
        report_data = dict(schema='legacy_recovery_v1', records=count,
            original_sha256=digest, restarted_at_lines=restarts,
            historical_continuity_verified=not restarts,
            legacy_key_security='Public legacy fallback; HMAC matches do not establish authenticity.',
            policy='Original bytes retained. New chain starts independently and anchors this archive and report.')
        # Exclusive writes preserve any earlier recovery artifacts on failure.
        with archive.open('xb') as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        report_raw = (json.dumps(report_data, indent=2) + '\n').encode()
        with report.open('xb') as handle:
            handle.write(report_raw)
            handle.flush()
            os.fsync(handle.fileno())
        manifest = dict(type='legacy_recovery_v1',
            archive=dict(name=archive.name, sha256=digest),
            report=dict(name=report.name, sha256=hashlib.sha256(report_raw).hexdigest()))
        temporary = path.with_name(path.name + '.recovery-pending')
        if temporary.exists():
            raise ValueError('Pending recovery exists; inspect it before retrying')
        replacement = Ledger(temporary, new_key)
        replacement.append('RECOVERY', json.dumps(manifest, sort_keys=True))
        replacement.verify()
        os.replace(temporary, path)
        return report_data
