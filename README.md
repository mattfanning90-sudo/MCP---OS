# MCP---OS

A sandboxed **file-system MCP server**, written in Python and served over HTTP.

It exposes a small set of safe file-system tools to any [Model Context
Protocol](https://modelcontextprotocol.io) client (Claude Desktop, Claude Code,
etc.). Every operation is confined to a single **sandbox root** directory —
paths that try to escape the root (via `..`, absolute paths, or symlinks) are
rejected.

## Tools

| Tool | Description |
| --- | --- |
| `get_root` | Show the absolute sandbox root that all paths are relative to. |
| `list_directory(path=".")` | List directory contents (dirs marked `/`, files show size). |
| `read_file(path)` | Read a UTF-8 text file (truncated at the byte limit). |
| `get_file_info(path)` | Type, size, timestamps, and mode for a path. |
| `search_files(pattern, path=".")` | Recursive glob search, e.g. `*.py`. |
| `write_file(path, content)` | Create/overwrite a text file (parents created). |
| `create_directory(path)` | Create a directory and any missing parents. |
| `move(source, destination)` | Move or rename a file/directory. |
| `delete(path, recursive=False)` | Delete a file or directory. |

Write/delete tools are disabled when the server runs in read-only mode.

## Configuration

All configuration is via environment variables:

| Variable | Default | Meaning |
| --- | --- | --- |
| `MCP_OS_ROOT` | current working directory | Sandbox root directory. |
| `MCP_OS_TRANSPORT` | `streamable-http` | `streamable-http`, `sse`, or `stdio`. |
| `MCP_OS_HOST` | `127.0.0.1` | Bind host (HTTP transports). |
| `MCP_OS_PORT` | `8000` | Bind port (HTTP transports). |
| `MCP_OS_READ_ONLY` | `false` | If truthy, disables write/delete tools. |
| `MCP_OS_MAX_BYTES` | `1048576` | Max bytes per single file read/write. |

## Quick start

With [`uv`](https://docs.astral.sh/uv/):

```bash
uv sync
MCP_OS_ROOT=/path/to/sandbox uv run mcp-os
```

Or with pip:

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e .
MCP_OS_ROOT=/path/to/sandbox mcp-os
```

The server starts on `http://127.0.0.1:8000` using the Streamable HTTP
transport by default. The MCP endpoint is served at `/mcp` (or `/sse` when
`MCP_OS_TRANSPORT=sse`).

## Connecting a client

Point an MCP client at the running server's URL. For example, in Claude Code:

```bash
claude mcp add --transport http mcp-os http://127.0.0.1:8000/mcp
```

For clients that launch the server themselves over stdio instead, run with
`MCP_OS_TRANSPORT=stdio`.

## Development

```bash
uv sync --extra dev   # or: pip install -e . pytest
uv run pytest         # run the test suite
```

Layout:

```
src/mcp_os/
  sandbox.py   # path confinement (the security boundary)
  server.py    # FastMCP server + tool definitions
tests/         # sandbox + tool tests
```

## Security notes

- The sandbox is the security boundary. `sandbox.py` resolves every path and
  verifies the result lives under the root *after* collapsing symlinks and
  `..`, so symlink-based escapes are blocked.
- Absolute paths are re-anchored under the root rather than honored verbatim.
- Run with `MCP_OS_READ_ONLY=1` to expose a browse-only server.
- Bind to `127.0.0.1` (the default) unless you intentionally need remote
  access; there is no built-in authentication.

## License

MIT
