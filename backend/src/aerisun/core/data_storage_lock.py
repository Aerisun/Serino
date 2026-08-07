from __future__ import annotations

import fcntl
import os
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps
from typing import Any, TypeVar

from aerisun.core.settings import get_settings

ResultT = TypeVar("ResultT")
_lock_depth: ContextVar[int] = ContextVar("aerisun_data_storage_lock_depth", default=0)


@contextmanager
def exclusive_data_storage_lock() -> Iterator[None]:
    depth = _lock_depth.get()
    if depth > 0:
        token = _lock_depth.set(depth + 1)
        try:
            yield
        finally:
            _lock_depth.reset(token)
        return

    data_dir = get_settings().data_dir.expanduser().resolve()
    data_dir.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(data_dir, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    token = _lock_depth.set(1)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)
        _lock_depth.reset(token)


def data_storage_locked(operation: Callable[..., ResultT]) -> Callable[..., ResultT]:
    @wraps(operation)
    def wrapped(*args: Any, **kwargs: Any) -> ResultT:
        with exclusive_data_storage_lock():
            return operation(*args, **kwargs)

    return wrapped


def data_storage_cleanup_pending() -> bool:
    state_dir = get_settings().data_dir.expanduser().resolve() / ".data-migrations"
    if not state_dir.exists():
        return False
    if state_dir.is_symlink() or not state_dir.is_dir():
        return True
    for path in state_dir.iterdir():
        if path.is_symlink():
            return True
        if path.is_file() and path.suffix == ".json":
            return True
    return False
