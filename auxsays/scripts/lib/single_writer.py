#!/usr/bin/env python3
"""One writer at a time for a tracked data file, and never a stale one.

WHY THIS EXISTS. Twice now, two processes have written the same tracked evidence file and the
LOSER of the race won: a backfill started before a rule was corrected finished after the corrected
one and replaced 7 adjudicated rows with its own stale 10, two of which the corrected rules refuse.
Nothing detected it. Both writes "succeeded", the file was valid YAML, the tests passed, and the
defect reached main.

Agent discipline is not a mechanism. Two properties are enforced here instead:

  MUTUAL EXCLUSION -- an exclusive lock file taken with O_CREAT|O_EXCL, so a second writer waits or
  fails rather than interleaving. Held for the replace only, never across the network work.

  NO STALE OVERWRITE -- the writer states the fingerprint of the content it READ. If the file on
  disk no longer matches, somebody else has written since and this output is derived from a
  superseded baseline, so the write is REFUSED. This is what makes the race a loud failure instead
  of silent data loss: a fast writer can still lose, but it can no longer win by finishing late.

Writes are atomic (temp file in the same directory, then os.replace), so a crash or a kill mid-write
leaves the previous complete file rather than a truncated one.
"""
from __future__ import annotations

import hashlib
import os
import time
from contextlib import contextmanager
from pathlib import Path

LOCK_SUFFIX = ".writer.lock"
DEFAULT_TIMEOUT_S = 120.0
STALE_LOCK_S = 900.0


class WriterBusy(RuntimeError):
    """Another process holds the write lock for this path."""


class StaleWrite(RuntimeError):
    """The file changed since it was read, so this output is derived from a superseded baseline."""


def fingerprint(path) -> str:
    """Content fingerprint of a file, or "" when it does not exist.

    Content rather than mtime: a same-second rewrite is exactly the case that bit us, and file
    timestamps on this platform are too coarse to separate two writers a few hundred ms apart.
    """
    target = Path(path)
    if not target.exists():
        return ""
    return hashlib.sha256(target.read_bytes()).hexdigest()


@contextmanager
def write_lock(path, *, timeout_s: float = DEFAULT_TIMEOUT_S):
    """Hold an exclusive lock for `path` while the body runs."""
    lock = Path(str(path) + LOCK_SUFFIX)
    lock.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + timeout_s
    handle = None
    while True:
        try:
            handle = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            break
        except FileExistsError:
            # A crashed writer must not block the lane forever, but the window is long enough that
            # it can never expire under a live writer doing ordinary work.
            try:
                age = time.time() - lock.stat().st_mtime
            except OSError:
                age = 0.0
            if age > STALE_LOCK_S:
                try:
                    lock.unlink()
                except OSError:
                    pass
                continue
            if time.monotonic() >= deadline:
                raise WriterBusy(f"{lock.name} held for {age:.0f}s")
            time.sleep(0.2)
    try:
        os.write(handle, f"{os.getpid()} {time.time():.3f}".encode())
        os.close(handle)
        handle = None
        yield
    finally:
        if handle is not None:
            os.close(handle)
        try:
            lock.unlink()
        except OSError:
            pass


def atomic_replace(path, data: bytes) -> None:
    """Replace `path` with `data` in one step, or leave the previous file untouched."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = target.with_name(f".{target.name}.{os.getpid()}.tmp")
    try:
        temp.write_bytes(data)
        os.replace(temp, target)
    finally:
        if temp.exists():
            try:
                temp.unlink()
            except OSError:
                pass


def replace_via(path, writer) -> None:
    """Atomically publish whatever `writer` serialises. Takes NO lock -- the caller holds it.

    `writer` is called with a temporary path inside the target's directory and must write the
    COMPLETE intended file. Nothing is published until it returns, so a writer that raises halfway
    leaves the previous file in place rather than a half-serialised one.
    """
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = target.with_name(f".{target.name}.{os.getpid()}.tmp")
    try:
        writer(temp)
        os.replace(temp, target)
    finally:
        if temp.exists():
            try:
                temp.unlink()
            except OSError:
                pass


def guarded_write_via(path, writer, *, expected: str | None,
                      timeout_s: float = DEFAULT_TIMEOUT_S) -> None:
    """`replace_via` under the lock, refusing if the file changed since `expected` was taken.

    For a writer that rebuilds a whole file from a baseline it read minutes earlier -- a backfill.
    The collector instead re-reads and merges inside the lock, so it has nothing stale to reinstate.
    """
    with write_lock(path, timeout_s=timeout_s):
        if expected is not None:
            current = fingerprint(path)
            if current != expected:
                raise StaleWrite(
                    f"{Path(path).name} changed since it was read "
                    f"(expected {expected[:12] or 'absent'}, found {current[:12] or 'absent'})")
        replace_via(path, writer)


def guarded_write(path, data: bytes, *, expected: str | None,
                  timeout_s: float = DEFAULT_TIMEOUT_S) -> None:
    """Write `data` to `path` under the lock, refusing if the file changed since it was read.

    `expected` is the fingerprint of the content this output was derived from; pass None only for a
    write that legitimately does not care what was there (a first creation from nothing).
    """
    with write_lock(path, timeout_s=timeout_s):
        if expected is not None:
            current = fingerprint(path)
            if current != expected:
                raise StaleWrite(
                    f"{Path(path).name} changed since it was read "
                    f"(expected {expected[:12] or 'absent'}, found {current[:12] or 'absent'})")
        atomic_replace(path, data)
