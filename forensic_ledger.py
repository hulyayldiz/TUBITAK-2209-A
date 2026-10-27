"""Process-safe, streaming HMAC ledger with verified segment rotation."""
from contextlib import contextmanager
from datetime import datetime
import hashlib
import hmac
import json
import os
from pathlib import Path
import time


@contextmanager
def file_lock(path, timeout_s=5.):
    lock = Path(str(path)+".lock")
    lock.parent.mkdir(parents=True, exist_ok=True)
    with lock.open("a+b") as handle:
        if handle.tell() == 0:
            handle.write(b"0")
            handle.flush()
        deadline = time.monotonic()+timeout_s
        while True:
            try:
                handle.seek(0)
                if os.name == "nt":
                    import msvcrt
                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError:
                if time.monotonic() >= deadline:
                    raise TimeoutError("Forensic ledger lock is busy")
                time.sleep(.01)
        try:
            yield
        finally:
            handle.seek(0)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


class Ledger:
    def __init__(self, path, key, rotation_bytes=10*1024*1024):
        self.path = Path(path)
        self.key = key
        self.rotation_bytes = rotation_bytes

    def _files(self):
        archives = sorted(self.path.parent.glob(self.path.name+".segment-*.jsonl"))
        return archives + ([self.path] if self.path.exists() else [])

    def _verify_recovery(self, entry):
        if entry['level'] != 'RECOVERY':
            return
        manifest = json.loads(entry['message'])
        if manifest.get('type') != 'legacy_recovery_v1':
            raise ValueError('Unknown recovery format')
        for item in ('archive', 'report'):
            name = manifest[item]['name']
            if not isinstance(name, str) or Path(name).name != name or name in ('.', '..'):
                raise ValueError('Invalid recovery filename')
            data = (self.path.parent / name).read_bytes()
            if not hmac.compare_digest(hashlib.sha256(data).hexdigest(), manifest[item]['sha256']):
                raise ValueError('Recovery archive or report was changed')

    def _verify(self):
        head, count = "0"*64, 0
        for path in self._files():
            with path.open(encoding="utf-8") as handle:
                for number, line in enumerate(handle, 1):
                    try:
                        entry = json.loads(line)
                        content = f"{entry['timestamp']} - {entry['level']} - {entry['message']}"
                        digest = hmac.new(self.key, f"{head}{content}{entry['salt']}".encode(), hashlib.sha256).hexdigest()
                        if not hmac.compare_digest(digest, entry["chain_hmac"]):
                            raise ValueError("HMAC mismatch")
                        self._verify_recovery(entry)
                        head, count = digest, count+1
                    except (ValueError, KeyError, TypeError) as error:
                        raise ValueError(f"Invalid forensic chain: {path.name}:{number}") from error
        return head, count

    def verify(self):
        with file_lock(self.path):
            return self._verify()

    def append(self, level, message):
        with file_lock(self.path):
            head, _ = self._verify()
            if self.path.exists() and self.path.stat().st_size >= self.rotation_bytes:
                archives = sorted(self.path.parent.glob(self.path.name+".segment-*.jsonl"))
                index = int(archives[-1].name.split(".segment-")[-1].split(".")[0])+1 if archives else 1
                archive = self.path.with_name(self.path.name+f".segment-{index:08d}.jsonl")
                self.path.rename(archive)
            entry = dict(timestamp=datetime.now().astimezone().isoformat(timespec="seconds"),
                         level=str(level), message=str(message), salt=os.urandom(8).hex())
            content = f"{entry['timestamp']} - {entry['level']} - {entry['message']}"
            entry["chain_hmac"] = hmac.new(self.key, f"{head}{content}{entry['salt']}".encode(), hashlib.sha256).hexdigest()
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(entry, ensure_ascii=False)+"\n")
                handle.flush()
                os.fsync(handle.fileno())
            return entry
