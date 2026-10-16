"""Safely manage only the two generated call-comment sections."""
from __future__ import annotations

import ast
import difflib
import os
import re
import tempfile
from pathlib import Path
from .analyzer import Index
from .formatter import render

HEAD = re.compile(r"^## (调用了|被调用)：")
CATEGORY = re.compile(r"^#   (?:本模块|本类|项目模块|外部库|标准库)$")
BRANCH = re.compile(r"^#   [├└]─ .+$")
CONTINUATION = re.compile(r"^#\s{4,}\S.*$")
SINGLE = re.compile(r"^## (?:调用了|被调用)：(?:无已确认项目调用|无已识别调用|未发现静态调用)$")


def _generated(line: str, indent: str) -> bool:
    if not line.startswith(indent):
        return False
    rest = line[len(indent):].rstrip("\r\n")
    return bool(CATEGORY.fullmatch(rest) or BRANCH.fullmatch(rest)
                or CONTINUATION.fullmatch(rest) or SINGLE.fullmatch(rest)
                or HEAD.fullmatch(rest))


def _block(lines: list[str], pos: int, indent: str, path: Path) -> tuple[int, int]:
    """Locate owned annotation immediately before a declaration without touching human comments."""
    start = pos
    while start and _generated(lines[start - 1], indent):
        start -= 1
    headers = [lines[i][len(indent):].strip() for i in range(start, pos)
               if lines[i].startswith(indent) and HEAD.match(lines[i][len(indent):])]
    if not headers:
        return pos, pos
    if len(headers) != 2 or not headers[0].startswith("## 调用了：") or not headers[1].startswith("## 被调用："):
        raise ValueError(f"Ambiguous generated comments at {path}:{pos + 1}")
    if not lines[start][len(indent):].startswith("## 调用了："):
        raise ValueError(f"Ambiguous generated comments at {path}:{pos + 1}")
    return start, pos


def edit(path: Path, index: Index, operation: str) -> tuple[str, str]:
    if operation not in {"write", "remove"}:
        raise ValueError("Expected write or remove")
    data = path.read_bytes()
    codec = "utf-8-sig" if data.startswith(b"\xef\xbb\xbf") else "utf-8"
    original = data.decode(codec)
    newline = "\r\n" if "\r\n" in original else "\n"
    lines = original.splitlines(keepends=True)
    changes: list[tuple[int, int, str]] = []
    for symbol in index.by_file.get(path.resolve(), []):
        pos = symbol.lineno - 1
        if pos >= len(lines):
            raise ValueError(f"Invalid declaration position: {path}:{symbol.lineno}")
        indent = re.match(r"^[ \t]*", lines[pos]).group()
        start, end = _block(lines, pos, indent, path)
        replacement = "" if operation == "remove" else render(index, symbol, newline, indent)
        changes.append((start, end, replacement))
    result = list(lines)
    for start, end, replacement in sorted(changes, reverse=True):
        result[start:end] = [replacement] if replacement else []
    updated = "".join(result)
    if ast.dump(ast.parse(original, type_comments=True)) != ast.dump(ast.parse(updated, type_comments=True)):
        raise ValueError(f"AST changed: {path}")
    return original, updated


def diff(path: Path, before: str, after: str) -> str:
    return "".join(difflib.unified_diff(before.splitlines(True), after.splitlines(True),
                                        fromfile=str(path), tofile=str(path)))


def _encode(path: Path, text: str) -> bytes:
    raw = path.read_bytes()
    return text.encode("utf-8-sig" if raw.startswith(b"\xef\xbb\xbf") else "utf-8")


def apply_batch(changes: list[tuple[Path, str, str]]) -> None:
    """Preflight all inputs, stage outputs, replace, and restore on ordinary failures."""
    staged: list[tuple[Path, Path, bytes]] = []
    replaced: list[tuple[Path, bytes]] = []
    try:
        for path, before, after in changes:
            path = path.resolve()
            original = path.read_bytes()
            codec = "utf-8-sig" if original.startswith(b"\xef\xbb\xbf") else "utf-8"
            if original.decode(codec) != before:
                raise RuntimeError(f"File changed during analysis: {path}")
            content = after.encode(codec)
            fd, temp = tempfile.mkstemp(prefix=".code_annotations_", suffix=".tmp", dir=path.parent)
            temporary = Path(temp)
            try:
                with os.fdopen(fd, "wb") as f:
                    f.write(content)
                    f.flush()
                    os.fsync(f.fileno())
                os.chmod(temporary, path.stat().st_mode)
            except BaseException:
                temporary.unlink(missing_ok=True)
                raise
            staged.append((path, temporary, original))
        for path, temporary, original in staged:
            # Recheck concurrency after staging as well.
            if path.read_bytes() != original:
                raise RuntimeError(f"File changed before commit: {path}")
            os.replace(temporary, path)
            replaced.append((path, original))
    except BaseException:
        failures = []
        for path, data in reversed(replaced):
            try:
                fd, temp = tempfile.mkstemp(prefix=".code_annotations_restore_", dir=path.parent)
                with os.fdopen(fd, "wb") as f:
                    f.write(data)
                os.replace(temp, path)
            except OSError as exc:
                failures.append(f"{path}: {exc}")
        if failures:
            raise RuntimeError("Rollback incomplete: " + "; ".join(failures))
        raise
    finally:
        for _, temporary, _ in staged:
            temporary.unlink(missing_ok=True)


def write(path: Path, before: str, after: str) -> None:
    if before != after:
        apply_batch([(path, before, after)])
