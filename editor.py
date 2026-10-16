"""Minimal byte-preserving editing of generated comment sections."""
from __future__ import annotations

import ast
import difflib
import re
from pathlib import Path
from .analyzer import Index
from .formatter import render

HEAD = re.compile(r"^\s*## (?:调用了|被调用)：")
TREE = re.compile(r"^\s*#(?:   (?:本模块|项目模块|外部库|标准库)|   [├└]─.*| +[\w.,()， ]+)$")

def _line_start_node(lines: list[str], lineno: int) -> tuple[int, str]:
    line = lines[lineno-1]
    indent = re.match(r"^\s*", line).group()
    return lineno-1, indent

def edit(path: Path, index: Index, operation: str) -> tuple[str, str]:
    data = path.read_bytes()
    bom = data.startswith(b"\xef\xbb\xbf")
    codec = "utf-8-sig" if bom else "utf-8"
    original = data.decode(codec)
    newline = "\r\n" if "\r\n" in original else "\n"
    lines = original.splitlines(keepends=True)
    changes = []
    for symbol in index.by_file.get(path.resolve(), []):
        pos, indent = _line_start_node(lines, symbol.lineno)
        # Identify generated sections by their two explicit headings, never by
        # broad comment matching: '# 原有中文注释' belongs to the human author.
        scan = pos
        while scan > 0:
            text = lines[scan - 1].rstrip("\r\n")
            if not text.startswith(indent + "#") or text.startswith(indent + "###"):
                break
            scan -= 1
        headings = [(i, lines[i].strip()) for i in range(scan, pos)
                    if HEAD.match(lines[i].rstrip("\r\n"))]
        expected = ["## 调用了：", "## 被调用："]
        if headings:
            if len(headings) != 2 or any(not heading.startswith(prefix) for (_, heading), prefix in zip(headings, expected)):
                raise ValueError(f"Ambiguous generated comments at {path}:{symbol.lineno}")
            start = headings[0][0]
            # Strictly limit the block to the generated tree/comments.
            for item in lines[start + 1:pos]:
                text = item.rstrip("\r\n")
                if not (HEAD.match(text) or TREE.match(text)):
                    raise ValueError(f"Ambiguous generated comments at {path}:{symbol.lineno}")
        else:
            start = pos
        replacement = "" if operation == "remove" else render(index, symbol, newline, indent)
        changes.append((start, pos, replacement))
    result = lines[:]
    for begin, end, replacement in sorted(changes, reverse=True):
        result[begin:end] = [replacement] if replacement else []
    updated = "".join(result)
    if ast.dump(ast.parse(original)) != ast.dump(ast.parse(updated)):
        raise ValueError(f"AST changed: {path}")
    return original, updated

def diff(path: Path, before: str, after: str) -> str:
    return "".join(difflib.unified_diff(before.splitlines(True), after.splitlines(True), fromfile=str(path), tofile=str(path)))

def write(path: Path, before: str, after: str) -> None:
    if before == after:
        return
    data = path.read_bytes()
    codec = "utf-8-sig" if data.startswith(b"\xef\xbb\xbf") else "utf-8"
    if data.decode(codec) != before:
        raise RuntimeError(f"File changed during analysis: {path}")
    path.write_bytes(after.encode(codec))
