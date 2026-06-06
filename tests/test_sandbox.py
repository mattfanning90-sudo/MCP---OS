"""Tests for the path sandbox."""

import pytest

from mcp_os.sandbox import Sandbox, SandboxError


def test_resolves_relative_path(tmp_path):
    sb = Sandbox(tmp_path)
    assert sb.resolve("a/b.txt") == (tmp_path / "a/b.txt").resolve()


def test_rejects_parent_traversal(tmp_path):
    sb = Sandbox(tmp_path / "root")
    with pytest.raises(SandboxError):
        sb.resolve("../escape.txt")


def test_reanchors_absolute_paths(tmp_path):
    sb = Sandbox(tmp_path / "root")
    # An absolute input is re-anchored under the root, not honored verbatim.
    resolved = sb.resolve("/etc/passwd")
    assert resolved == (sb.root / "etc/passwd").resolve()


def test_rejects_symlink_escape(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (root / "link").symlink_to(outside)
    sb = Sandbox(root)
    # The symlink target is outside the root, so resolution must fail.
    with pytest.raises(SandboxError):
        sb.resolve("link/secret.txt")


def test_must_exist(tmp_path):
    sb = Sandbox(tmp_path)
    with pytest.raises(SandboxError):
        sb.resolve("nope.txt", must_exist=True)


def test_relative_of_root(tmp_path):
    sb = Sandbox(tmp_path)
    assert sb.relative(sb.root) == "."
