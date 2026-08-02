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
            handle.flush()
            os.fsync(handle.fileno())  # durable before the atomic swap (Part H)
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


class GitUnavailable(Exception):
    """Git-based mutation detection is unavailable in a context that requires it (production write
    mode). The transaction is unsafe and the run must hard-abort -- never degrade silently to
    directory-only detection when Git is required (Part E fail-closed)."""


class CollectorTransaction:
    def __init__(self, repo_root: Path, mutable_roots: list[Path], *, require_git: bool = False) -> None:
        self.repo_root = Path(repo_root).resolve()
        self.roots = [Path(r).resolve() for r in mutable_roots]
        self.require_git = require_git
        self._snapshot: dict[Path, bytes] = {}
        self._existed: set[Path] = set()
        self._git_baseline: set[str] = set()
        # Absolute Git top level, resolved in begin() via `git rev-parse --show-toplevel`. git status
        # reports paths relative to THIS, which is NOT necessarily repo_root: the application root may
        # be a nested subdirectory (e.g. <top>/auxsays). Interpreting git paths against repo_root would
        # double the nested segment and misclassify legitimate in-surface writes as UnexpectedMutation.
        self._git_root: Path | None = None

    def baseline_bytes(self, path: Path) -> bytes | None:
        """Pre-collector bytes of a path in the declared surface (None if it did not exist)."""
        return self._snapshot.get(Path(path).resolve())

    # --- surface enumeration --------------------------------------------------
    def _iter_root_files(self):
        for root in self.roots:
            if root.is_file():
                yield root
            elif root.is_dir():
                for p in sorted(root.rglob("*")):
                    if p.is_file():
                        yield p

    def _resolve_git_root(self) -> Path:
        """Resolve the actual Git top level explicitly via `git rev-parse --show-toplevel` (never
        inferred from the application directory). git status/checkout report paths relative to this.
        Fail closed with GitUnavailable in production write mode if resolution fails, returns an
        invalid path, or resolves a repository that does not contain the application root. When git
        is not required (dry-run / unit contexts) and unavailable, fall back to repo_root."""
        try:
            proc = subprocess.run(
                ["git", "-C", str(self.repo_root), "rev-parse", "--show-toplevel"],
                capture_output=True, text=True,
            )
        except (FileNotFoundError, OSError) as exc:
            if self.require_git:
                raise GitUnavailable(f"git executable unavailable ({type(exc).__name__})") from None
            return self.repo_root
        out = (proc.stdout or "").strip()
        if proc.returncode != 0 or not out:
            if self.require_git:
                raise GitUnavailable("git rev-parse --show-toplevel failed (not a work tree)")
            return self.repo_root
        top = Path(out).resolve()
        if not top.exists():
            if self.require_git:
                raise GitUnavailable("git top-level path does not exist")
            return self.repo_root
        # The configured application root MUST live inside this Git repository.
        try:
            self.repo_root.relative_to(top)
        except ValueError:
            if self.require_git:
                raise GitUnavailable("application root is not inside the resolved git repository")
            return self.repo_root
        return top

    def _within_roots(self, rel_path: str) -> bool:
        # git-reported paths are relative to the Git top level, not repo_root.
        base = self._git_root or self.repo_root
        ap = (base / rel_path).resolve()
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
        # -z (NUL-separated, no quoting/escaping) so paths with spaces or Unicode are handled safely;
        # bytes + explicit UTF-8 decode avoids platform-codepage corruption of non-ASCII paths.
        try:
            proc = subprocess.run(
                ["git", "-C", str(self.repo_root), "status", "--porcelain", "-z", "--untracked-files=all"],
                capture_output=True,
            )
        except (FileNotFoundError, OSError) as exc:
            if self.require_git:
                raise GitUnavailable(f"git executable unavailable ({type(exc).__name__})") from None
            return set()
        if proc.returncode != 0:
            if self.require_git:
                # Fail closed: no silent degrade to directory-only detection in production write mode.
                raise GitUnavailable("git status failed (not a work tree or git error)")
            return set()
        fields = proc.stdout.decode("utf-8", "surrogateescape").split("\x00")
        paths: set[str] = set()
        i, n = 0, len(fields)
        while i < n:
            entry = fields[i]
            i += 1
            if not entry:
                continue
            xy = entry[:2]
            path = entry[3:] if len(entry) > 3 else ""
            # In -z mode a rename/copy is followed by the ORIGIN path in the next NUL field; flag both
            # the destination and the origin so a rename into OR out of the roots is detected.
            if "R" in xy or "C" in xy:
                origin = fields[i] if i < n else ""
                i += 1
                if origin:
                    paths.add(origin)
            if path:
                paths.add(path)
        return paths

    # --- lifecycle ------------------------------------------------------------
    def begin(self) -> None:
        # Resolve the Git top level FIRST so a production write mode with unusable git fails closed
        # before any state is captured.
        self._git_root = self._resolve_git_root()
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
        # restore any undeclared out-of-root mutation from git HEAD (never legitimately changed).
        # git status reports git-root-relative paths, so run git FROM the git top level (not the
        # nested repo_root) or the pathspec would gain a doubled application-directory prefix.
        git_cwd = str(self._git_root or self.repo_root)
        for rel in self.undeclared_mutations():
            subprocess.run(["git", "-C", git_cwd, "checkout", "HEAD", "--", rel],
                           capture_output=True, text=True)
            subprocess.run(["git", "-C", git_cwd, "clean", "-fdq", "--", rel],
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
