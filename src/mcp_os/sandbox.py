"""Path sandboxing for mcp-os.

Every file-system operation is confined to a single root directory. Paths
supplied by callers are interpreted relative to that root, and any path that
would escape it (via ``..``, absolute paths, or symlinks) is rejected.
"""

from __future__ import annotations

import os
from pathlib import Path


class SandboxError(ValueError):
    """Raised when a requested path falls outside the sandbox root."""


class Sandbox:
    """Resolves caller-supplied paths against a fixed root directory."""

    def __init__(self, root: str | os.PathLike[str]) -> None:
        self.root = Path(root).expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def resolve(self, path: str, *, must_exist: bool = False) -> Path:
        """Resolve ``path`` to an absolute path inside the sandbox.

        ``path`` is treated as relative to the root. Absolute inputs are
        re-anchored to the root rather than honored verbatim, so a caller can
        never reach outside the sandbox. The fully resolved result (with
        symlinks collapsed) must still live under the root.
        """
        candidate = Path(path)
        # Re-anchor absolute paths to the root instead of trusting them.
        if candidate.is_absolute():
            candidate = self.root / candidate.relative_to(candidate.anchor)
        else:
            candidate = self.root / candidate

        # Resolve symlinks/.. without requiring the leaf to exist.
        resolved = candidate.resolve()

        if resolved != self.root and self.root not in resolved.parents:
            raise SandboxError(
                f"Path {path!r} resolves outside the sandbox root."
            )

        if must_exist and not resolved.exists():
            raise SandboxError(f"Path {path!r} does not exist.")

        return resolved

    def relative(self, path: str | os.PathLike[str]) -> str:
        """Render an absolute sandbox path as a root-relative string."""
        rel = Path(path).resolve().relative_to(self.root)
        return rel.as_posix() if str(rel) != "." else "."
