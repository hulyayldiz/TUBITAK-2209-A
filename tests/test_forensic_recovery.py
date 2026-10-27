import hashlib
import hmac
import json

import pytest

from forensic_ledger import Ledger
from forensic_recovery import recover_legacy_ledger


def legacy_file(path, restart=False):
    ledger = Ledger(path, b'old-public-key')
    first = ledger.append('INFO', 'first')
    second = ledger.append('INFO', 'second')
    if restart:
        content = f"{second['timestamp']} - {second['level']} - {second['message']}"
        second['chain_hmac'] = hmac.new(b'old-public-key',
            f"{'0' * 64}{content}{second['salt']}".encode(), hashlib.sha256).hexdigest()
        path.write_text(json.dumps(first) + '\n' + json.dumps(second) + '\n', encoding='utf-8')
    return path.read_bytes()


def test_recovery_preserves_original_and_records_restart(tmp_path):
    path = tmp_path / 'events.jsonl'
    original = legacy_file(path, restart=True)
    with pytest.raises(ValueError):
        Ledger(path, b'old-public-key').verify()
    report = recover_legacy_ledger(path, b'old-public-key', b'new-private-key')
    assert report['restarted_at_lines'] == [2]
    assert report['historical_continuity_verified'] is False
    assert next(tmp_path.glob('*.legacy-*.jsonl')).read_bytes() == original
    ledger = Ledger(path, b'new-private-key', rotation_bytes=1)
    assert ledger.verify()[1] == 1
    ledger.append('INFO', 'new event')
    assert ledger.verify()[1] == 2
    # Signed recovery anchors still protect evidence after normal rotation.
    next(tmp_path.glob('*.legacy-*.jsonl')).write_bytes(original + b'\n')
    with pytest.raises(ValueError):
        ledger.verify()
    with pytest.raises(ValueError):
        ledger.append('INFO', 'blocked')


@pytest.mark.parametrize('damage', ['wrong-key', 'changed-content'])
def test_recovery_refuses_unknown_damage_without_changing_original(tmp_path, damage):
    path = tmp_path / 'events.jsonl'
    legacy_file(path)
    if damage == 'changed-content':
        path.write_bytes(path.read_bytes().replace(b'first', b'other'))
    original = path.read_bytes()
    key = b'wrong-key' if damage == 'wrong-key' else b'old-public-key'
    with pytest.raises(ValueError):
        recover_legacy_ledger(path, key, b'new-private-key')
    assert path.read_bytes() == original
    assert not list(tmp_path.glob('*.legacy-*'))


@pytest.mark.parametrize('damage', ['report-changed', 'archive-missing', 'wrong-new-key'])
def test_recovered_chain_rejects_damaged_evidence_and_wrong_key(tmp_path, damage):
    path = tmp_path / 'events.jsonl'
    legacy_file(path)
    recover_legacy_ledger(path, b'old-public-key', b'new-private-key')
    if damage == 'report-changed':
        next(tmp_path.glob('*.report.json')).write_text('{}', encoding='utf-8')
    elif damage == 'archive-missing':
        next(tmp_path.glob('*.legacy-*.jsonl')).unlink()
    key = b'wrong' if damage == 'wrong-new-key' else b'new-private-key'
    with pytest.raises((ValueError, OSError)):
        Ledger(path, key).verify()


def test_cli_uses_project_ledger_from_another_directory(tmp_path, monkeypatch):
    import verify_hashes
    path = tmp_path / 'actual' / 'events.jsonl'
    path.parent.mkdir()
    Ledger(path, b'private-key').append('INFO', 'existing')
    monkeypatch.setattr(verify_hashes, 'FORENSIC_LEDGER_PATH', path)
    monkeypatch.setattr(verify_hashes, 'load_forensic_key', lambda: b'private-key')
    monkeypatch.chdir(tmp_path)
    assert verify_hashes.verify_all_hashes()
    path.unlink()
    assert not verify_hashes.verify_all_hashes()
