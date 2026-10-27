"""Atomic model persistence and file-version-aware Streamlit resource caching."""
import functools
import os
from pathlib import Path
import tempfile
import streamlit as st


def artifact_cache(*paths):
    def decorate(function):
        @st.cache_resource
        def cached(loader_identity, versions):
            return function()
        @functools.wraps(function)
        def wrapper():
            versions = []
            for name in paths:
                path = Path(name).resolve()
                try:
                    stat = path.stat()
                    versions.append((str(path), stat.st_mtime_ns, stat.st_size))
                except FileNotFoundError:
                    versions.append((str(path), None, None))
            return cached((function.__module__, function.__qualname__), tuple(versions))
        wrapper.clear = cached.clear
        return wrapper
    return decorate


def atomic_write(path, writer):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix=path.name+".", suffix=".tmp", dir=path.parent)
    os.close(descriptor)
    temporary = Path(name)
    try:
        writer(temporary)
        with temporary.open("rb+") as handle:
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def dump_joblib(value, path):
    import joblib
    atomic_write(path, lambda temporary: joblib.dump(value, temporary))


def save_torch(value, path):
    import torch
    atomic_write(path, lambda temporary: torch.save(value, temporary))


def save_numpy(value, path):
    import numpy as np
    def writer(temporary):
        with temporary.open("wb") as handle:
            np.save(handle, value)
    atomic_write(path, writer)
