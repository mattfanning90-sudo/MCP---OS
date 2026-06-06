"""mcp-os file-system MCP server.

Exposes a small set of safe file-system tools over an HTTP transport. All
operations are confined to a sandbox root configured via the ``MCP_OS_ROOT``
environment variable (defaults to the current working directory).

Environment variables
---------------------
MCP_OS_ROOT       Sandbox root directory (default: current working directory).
MCP_OS_TRANSPORT  "streamable-http" (default) or "sse".
MCP_OS_HOST       Bind host (default: 127.0.0.1).
MCP_OS_PORT       Bind port (default: 8000).
MCP_OS_READ_ONLY  If truthy ("1", "true", "yes"), disables write/delete tools.
MCP_OS_MAX_BYTES  Max bytes returned/written for a single file (default: 1 MiB).
"""

from __future__ import annotations

import fnmatch
import os
from datetime import datetime, timezone

from mcp.server.fastmcp import FastMCP

from .sandbox import Sandbox, SandboxError


def _env_flag(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


ROOT = os.environ.get("MCP_OS_ROOT", os.getcwd())
READ_ONLY = _env_flag("MCP_OS_READ_ONLY", False)
MAX_BYTES = int(os.environ.get("MCP_OS_MAX_BYTES", str(1024 * 1024)))

sandbox = Sandbox(ROOT)

mcp = FastMCP(
    "mcp-os",
    instructions=(
        "A sandboxed file-system server. All paths are relative to a fixed "
        "root directory; paths that escape the root are rejected. Use "
        "list_directory to explore, read_file/write_file for contents, and "
        "search_files to find files by glob pattern."
    ),
)


def _format_time(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


def _require_writable() -> None:
    if READ_ONLY:
        raise SandboxError("Server is running in read-only mode.")


@mcp.tool()
def get_root() -> str:
    """Return the absolute sandbox root that all paths are relative to."""
    return str(sandbox.root)


@mcp.tool()
def list_directory(path: str = ".") -> str:
    """List the contents of a directory within the sandbox.

    Args:
        path: Directory path relative to the sandbox root. Defaults to root.

    Returns:
        A newline-separated listing. Directories end with "/"; files show
        their size in bytes.
    """
    target = sandbox.resolve(path, must_exist=True)
    if not target.is_dir():
        raise SandboxError(f"Path {path!r} is not a directory.")

    entries = sorted(
        target.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())
    )
    if not entries:
        return f"(empty directory: {sandbox.relative(target)})"

    lines = []
    for entry in entries:
        rel = sandbox.relative(entry)
        if entry.is_dir():
            lines.append(f"{rel}/")
        else:
            try:
                size = entry.stat().st_size
            except OSError:
                size = 0
            lines.append(f"{rel}\t{size} bytes")
    return "\n".join(lines)


@mcp.tool()
def read_file(path: str) -> str:
    """Read the contents of a UTF-8 text file within the sandbox.

    Args:
        path: File path relative to the sandbox root.

    Returns:
        The file contents as text. Files larger than the configured byte
        limit are truncated with a trailing notice.
    """
    target = sandbox.resolve(path, must_exist=True)
    if not target.is_file():
        raise SandboxError(f"Path {path!r} is not a file.")

    data = target.read_bytes()
    truncated = len(data) > MAX_BYTES
    text = data[:MAX_BYTES].decode("utf-8", errors="replace")
    if truncated:
        text += f"\n\n[... truncated at {MAX_BYTES} bytes ...]"
    return text


@mcp.tool()
def get_file_info(path: str) -> str:
    """Return metadata (type, size, timestamps) for a file or directory.

    Args:
        path: Path relative to the sandbox root.
    """
    target = sandbox.resolve(path, must_exist=True)
    st = target.stat()
    kind = "directory" if target.is_dir() else "file"
    return (
        f"path: {sandbox.relative(target)}\n"
        f"type: {kind}\n"
        f"size: {st.st_size} bytes\n"
        f"modified: {_format_time(st.st_mtime)}\n"
        f"created: {_format_time(st.st_ctime)}\n"
        f"mode: {oct(st.st_mode & 0o777)}"
    )


@mcp.tool()
def search_files(pattern: str, path: str = ".") -> str:
    """Recursively search for files/directories matching a glob pattern.

    Args:
        pattern: A glob pattern matched against entry names, e.g. "*.py".
        path: Directory to search under, relative to the sandbox root.

    Returns:
        Newline-separated matching paths (relative to the root), or a notice
        if nothing matched.
    """
    base = sandbox.resolve(path, must_exist=True)
    if not base.is_dir():
        raise SandboxError(f"Path {path!r} is not a directory.")

    matches = []
    for current, dirnames, filenames in os.walk(base):
        for name in fnmatch.filter(sorted(dirnames), pattern):
            matches.append(sandbox.relative(os.path.join(current, name)) + "/")
        for name in fnmatch.filter(sorted(filenames), pattern):
            matches.append(sandbox.relative(os.path.join(current, name)))

    if not matches:
        return f"No matches for {pattern!r} under {sandbox.relative(base)}."
    return "\n".join(sorted(matches))


@mcp.tool()
def write_file(path: str, content: str) -> str:
    """Create or overwrite a UTF-8 text file within the sandbox.

    Parent directories are created as needed. Disabled in read-only mode.

    Args:
        path: File path relative to the sandbox root.
        content: Text to write.

    Returns:
        A confirmation with the bytes written.
    """
    _require_writable()
    data = content.encode("utf-8")
    if len(data) > MAX_BYTES:
        raise SandboxError(
            f"Content exceeds the {MAX_BYTES}-byte limit "
            f"({len(data)} bytes)."
        )

    target = sandbox.resolve(path)
    if target == sandbox.root:
        raise SandboxError("Refusing to write to the sandbox root itself.")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    return f"Wrote {len(data)} bytes to {sandbox.relative(target)}."


@mcp.tool()
def create_directory(path: str) -> str:
    """Create a directory (and any missing parents) within the sandbox.

    Disabled in read-only mode.

    Args:
        path: Directory path relative to the sandbox root.
    """
    _require_writable()
    target = sandbox.resolve(path)
    target.mkdir(parents=True, exist_ok=True)
    return f"Created directory {sandbox.relative(target)}."


@mcp.tool()
def move(source: str, destination: str) -> str:
    """Move or rename a file or directory within the sandbox.

    Both endpoints must stay inside the sandbox. Disabled in read-only mode.

    Args:
        source: Existing path relative to the sandbox root.
        destination: New path relative to the sandbox root.
    """
    _require_writable()
    src = sandbox.resolve(source, must_exist=True)
    dst = sandbox.resolve(destination)
    if dst == sandbox.root:
        raise SandboxError("Refusing to overwrite the sandbox root.")
    if dst.exists():
        raise SandboxError(f"Destination {destination!r} already exists.")
    dst.parent.mkdir(parents=True, exist_ok=True)
    src.rename(dst)
    return f"Moved {sandbox.relative(src)} -> {sandbox.relative(dst)}."


@mcp.tool()
def delete(path: str, recursive: bool = False) -> str:
    """Delete a file or directory within the sandbox.

    Empty directories are removed directly; non-empty ones require
    ``recursive=True``. Disabled in read-only mode.

    Args:
        path: Path relative to the sandbox root.
        recursive: Permit deleting a non-empty directory and its contents.
    """
    _require_writable()
    target = sandbox.resolve(path, must_exist=True)
    if target == sandbox.root:
        raise SandboxError("Refusing to delete the sandbox root.")

    if target.is_dir():
        if any(target.iterdir()) and not recursive:
            raise SandboxError(
                f"Directory {path!r} is not empty; pass recursive=True."
            )
        if recursive:
            import shutil

            shutil.rmtree(target)
        else:
            target.rmdir()
        return f"Deleted directory {sandbox.relative(target)}."

    target.unlink()
    return f"Deleted file {sandbox.relative(target)}."


def main() -> None:
    """Entry point: configure transport from the environment and serve."""
    transport = os.environ.get("MCP_OS_TRANSPORT", "streamable-http").strip()
    mcp.settings.host = os.environ.get("MCP_OS_HOST", "127.0.0.1")
    mcp.settings.port = int(os.environ.get("MCP_OS_PORT", "8000"))

    if transport not in {"streamable-http", "sse", "stdio"}:
        raise SystemExit(
            f"Unsupported MCP_OS_TRANSPORT {transport!r}; "
            "use 'streamable-http', 'sse', or 'stdio'."
        )

    mcp.run(transport=transport)


if __name__ == "__main__":
    main()
