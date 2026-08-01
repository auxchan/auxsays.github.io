"""Per-collector filesystem transaction boundary for evidence collection.

Evidence collectors mutate tracked files (``_data/consensus_evidence.yml`` and
``updates/generated/*.md``) eagerly, per-patch, INSIDE ``collect()``. A collector can therefore
write output and then raise. Exception catching alone is insufficient: the runner would withhold
the failed collector's returned method-health rows but leave its earlier filesystem writes in the
tree. This module isolates each collector so that a failed (or undeclared-mutating) collector
contributes ZERO current-run changes to tracked files, while earlier successful collectors' changes
are preserved.

Contract per collector (write mode):
  begin()      -- snapshot the declared mutable surface (bytes + existence) as the baseline; this is
                  the POST-previous-successful-collector state, so A stays visible to B's baseline.
  after collect():
      undeclared_mutations()  -- git-detected tracked paths changed OUTSIDE the declared roots.
      commit()  -- ONLY when the collector returned normally, produced no undeclared mutation, and
                   left no torn output. Changes persist and become the next collector's baseline.
      rollback()-- on ANY exception / undeclared mutation: restore modified files byte-for-byte,
                   restore deleted files, delete created files (all via atomic replace), then
                   restore any undeclared out-of-root path from git HEAD. Asserts the declared
                   surface matches its pre-collector bytes + existence afterwards.

The declared mutable surface is determined from collector code (append_evidence_rows -> the evidence
file; apply_consensus_writeback / update_obs_record -> generated records), NOT a guessed glob.
"""
from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path


def atomic_write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


class UnexpectedMutation(Exception):
    """A collector wrote a tracked path outside its declared mutable roots."""

    def __init__(self, paths: list[str]) -> None:
        self.paths = list(paths)
        super().__init__("collector mutated undeclared tracked path(s): " + ", ".join(self.paths))


class RollbackError(Exception):
    """Rollback did not fully restore the declared surface to its pre-collector state."""


class CollectorTransaction:
    def __init__(self, repo_root: Path, mutable_roots: list[Path]) -> None:
        self.repo_root = Path(repo_root).resolve()
        self.roots = [Path(r).resolve() for r in mutable_roots]
        self._snapshot: dict[Path, bytes] = {}
        self._existed: set[Path] = set()
        self._git_baseline: set[str] = set()

    # --- surface enumeration --------------------------------------------------
    def _iter_root_files(self):
        for root in self.roots:
            if root.is_file():
                yield root
            elif root.is_dir():
                for p in sorted(root.rglob("*")):
                    if p.is_file():
                        yield p

    def _within_roots(self, rel_path: str) -> bool:
        ap = (self.repo_root / rel_path).resolve()
        for root in self.roots:
            if root.is_file() or not root.exists():
                if ap == root:
                    return True
            try:
                ap.relative_to(root)
                return True
            except ValueError:
                continue
        return False

    # --- git mutation detection ----------------------------------------------
    def _git_dirty(self) -> set[str]:
        proc = subprocess.run(
            ["git", "-C", str(self.repo_root), "status", "--porcelain", "--untracked-files=all"],
            capture_output=True, text=True,
        )
        if proc.returncode != 0:
            return set()
        paths: set[str] = set()
        for line in proc.stdout.splitlines():
            entry = line[3:] if len(line) > 3 else ""
            entry = entry.strip()
            if " -> " in entry:  # rename: take the destination
                entry = entry.split(" -> ", 1)[1]
            entry = entry.strip().strip('"')
            if entry:
                paths.add(entry)
        return paths

    # --- lifecycle ------------------------------------------------------------
    def begin(self) -> None:
        self._snapshot = {p: p.read_bytes() for p in self._iter_root_files()}
        self._existed = set(self._snapshot)
        self._git_baseline = self._git_dirty()

    def declared_mutations(self) -> set[Path]:
        """Actual create/modify/delete set WITHIN the declared roots (filesystem compare)."""
        current = set(self._iter_root_files())
        muts: set[Path] = set()
        for p in current:
            if p not in self._existed or p.read_bytes() != self._snapshot[p]:
                muts.add(p)
        muts |= {p for p in self._existed if p not in current}
        return muts

    def undeclared_mutations(self) -> list[str]:
        """Tracked paths this collector changed that lie OUTSIDE the declared roots (git-detected)."""
        new_dirty = self._git_dirty() - self._git_baseline
        return sorted(rel for rel in new_dirty if not self._within_roots(rel))

    def commit(self) -> None:
        self._snapshot = {}
        self._existed = set()

    def rollback(self) -> None:
        current = set(self._iter_root_files())
        # delete files created within the roots during this collector
        for p in current:
            if p not in self._existed:
                p.unlink()
        # restore modified or deleted files within the roots, byte-for-byte, atomically
        for p, data in self._snapshot.items():
            if p not in current or p.read_bytes() != data:
                atomic_write_bytes(p, data)
        # restore any undeclared out-of-root mutation from git HEAD (never legitimately changed)
        for rel in self.undeclared_mutations():
            subprocess.run(["git", "-C", str(self.repo_root), "checkout", "HEAD", "--", rel],
                           capture_output=True, text=True)
            subprocess.run(["git", "-C", str(self.repo_root), "clean", "-fdq", "--", rel],
                           capture_output=True, text=True)
        self._assert_restored()
        self._snapshot = {}
        self._existed = set()

    def _assert_restored(self) -> None:
        current = set(self._iter_root_files())
        for p, data in self._snapshot.items():
            if p not in current:
                raise RollbackError(f"failed to restore deleted file: {p}")
            if p.read_bytes() != data:
                raise RollbackError(f"failed to restore modified file: {p}")
        for p in current:
            if p not in self._existed:
                raise RollbackError(f"failed to remove created file: {p}")
