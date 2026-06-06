"""Tests for the file-system tools.

The tool functions close over a module-level ``sandbox`` bound to
``MCP_OS_ROOT`` at import time, so the root is set before importing the server.
"""

import importlib
import os

import pytest


@pytest.fixture()
def srv(tmp_path, monkeypatch):
    monkeypatch.setenv("MCP_OS_ROOT", str(tmp_path))
    monkeypatch.delenv("MCP_OS_READ_ONLY", raising=False)
    import mcp_os.server as server

    importlib.reload(server)
    return server


def test_write_then_read(srv):
    srv.write_file("notes/hello.txt", "hi there")
    assert srv.read_file("notes/hello.txt") == "hi there"


def test_list_directory(srv):
    srv.write_file("a.txt", "x")
    srv.create_directory("sub")
    listing = srv.list_directory(".")
    assert "sub/" in listing
    assert "a.txt" in listing


def test_search_files(srv):
    srv.write_file("src/app.py", "x")
    srv.write_file("src/util.py", "y")
    srv.write_file("README.md", "z")
    result = srv.search_files("*.py")
    assert "src/app.py" in result
    assert "src/util.py" in result
    assert "README.md" not in result


def test_move(srv):
    srv.write_file("old.txt", "data")
    srv.move("old.txt", "new.txt")
    assert srv.read_file("new.txt") == "data"


def test_delete_file(srv):
    srv.write_file("gone.txt", "x")
    srv.delete("gone.txt")
    with pytest.raises(Exception):
        srv.read_file("gone.txt")


def test_delete_nonempty_requires_recursive(srv):
    srv.write_file("dir/child.txt", "x")
    with pytest.raises(Exception):
        srv.delete("dir")
    srv.delete("dir", recursive=True)


def test_traversal_blocked(srv):
    with pytest.raises(Exception):
        srv.read_file("../../etc/passwd")


def test_read_only_mode(tmp_path, monkeypatch):
    monkeypatch.setenv("MCP_OS_ROOT", str(tmp_path))
    monkeypatch.setenv("MCP_OS_READ_ONLY", "1")
    import mcp_os.server as server

    importlib.reload(server)
    with pytest.raises(Exception):
        server.write_file("x.txt", "data")


def test_get_root(srv, tmp_path):
    assert srv.get_root() == str(tmp_path.resolve())
