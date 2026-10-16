"""Conservative, project-wide Python call index using the standard-library AST."""
from __future__ import annotations

import ast
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

SKIP = {".git", ".venv", "venv", "__pycache__", ".tox", "node_modules", "build", "dist"}

@dataclass
class Symbol:
    module: str
    qualname: str
    path: Path
    lineno: int
    kind: str
    calls: set[str] = field(default_factory=set)
    callers: set[str] = field(default_factory=set)
    external_calls: set[str] = field(default_factory=set)

    @property
    def key(self) -> str:
        return f"{self.module}.{self.qualname}" if self.module else self.qualname

class Index:
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.symbols: dict[str, Symbol] = {}
        self.by_file: dict[Path, list[Symbol]] = defaultdict(list)
        self.unresolved: dict[str, set[str]] = defaultdict(set)
        self._modules: dict[Path, ast.Module] = {}
        self._aliases: dict[Path, dict[str, str]] = {}
        self._nodes: list[tuple[Symbol, ast.AST]] = []

    def build(self) -> "Index":
        for path in sorted(self.root.rglob("*.py")):
            if set(path.relative_to(self.root).parts) & SKIP:
                continue
            path = path.resolve()
            try:
                tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
            except (SyntaxError, UnicodeError):
                continue
            self._modules[path] = tree
            aliases = {}
            for node in tree.body:
                if isinstance(node, ast.Import):
                    for item in node.names:
                        aliases[item.asname or item.name.split(".")[0]] = item.name if item.asname else item.name.split(".")[0]
                elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                    for item in node.names:
                        aliases[item.asname or item.name] = node.module + "." + item.name
                elif isinstance(node, ast.ImportFrom) and node.level:
                    mod = self._module(path)
                    package = mod.split(".")[:-1]
                    up = node.level - 1
                    prefix = package[:len(package)-up] if up else package
                    source = ".".join(prefix + ([node.module] if node.module else []))
                    for item in node.names:
                        aliases[item.asname or item.name] = source + "." + item.name
            self._aliases[path] = aliases
            self._collect(path, tree.body, "")
        for symbol, node in self._nodes:
            if isinstance(node, ast.ClassDef):
                # Class declarations are not function calls; their methods are indexed separately.
                continue
            visitor = _Calls(self, symbol)
            for stmt in node.body:
                if not isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    visitor.visit(stmt)
        for symbol in self.symbols.values():
            for callee in symbol.calls:
                if callee in self.symbols:
                    self.symbols[callee].callers.add(symbol.key)
        return self

    def _module(self, path: Path) -> str:
        parts = list(path.relative_to(self.root).with_suffix("").parts)
        if parts[-1] == "__init__":
            parts.pop()
        return ".".join(parts)

    def _collect(self, path: Path, nodes: list[ast.stmt], parent: str) -> None:
        for node in nodes:
            if not isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            qual = parent + "." + node.name if parent else node.name
            kind = "class" if isinstance(node, ast.ClassDef) else "function"
            line = min((d.lineno for d in node.decorator_list), default=node.lineno) if hasattr(node, "decorator_list") else node.lineno
            symbol = Symbol(self._module(path), qual, path, line, kind)
            self.symbols[symbol.key] = symbol
            self.by_file[path].append(symbol)
            self._nodes.append((symbol, node))
            self._collect(path, node.body, qual)

class _Calls(ast.NodeVisitor):
    def __init__(self, index: Index, owner: Symbol):
        self.index, self.owner = index, owner

    def visit_FunctionDef(self, node):
        return  # Nested definition body does not execute at definition time.
    visit_AsyncFunctionDef = visit_FunctionDef
    def visit_ClassDef(self, node):
        return

    def visit_Call(self, node: ast.Call):
        resolved = self.resolve(node.func)
        if resolved in self.index.symbols:
            self.owner.calls.add(resolved)
        elif resolved and not resolved.startswith("builtin:"):
            root = resolved.split(".")[0]
            if root not in {s.module.split(".")[0] for s in self.index.symbols.values()}:
                self.owner.external_calls.add(resolved)
            else:
                self.index.unresolved[self.owner.key].add(resolved)
        self.generic_visit(node)

    def resolve(self, fn: ast.expr) -> str | None:
        owner = self.owner
        aliases = self.index._aliases[owner.path]
        if isinstance(fn, ast.Name):
            name = fn.id
            if name in aliases:
                return aliases[name]
            scopes = [owner.qualname]
            if "." in owner.qualname:
                scopes.append(owner.qualname.rsplit(".", 1)[0])
            scopes.append("")
            for prefix in scopes:
                candidate = ".".join(x for x in (owner.module, prefix, name) if x)
                if candidate in self.index.symbols:
                    return candidate
            return None
        if isinstance(fn, ast.Attribute):
            parts = []
            cur = fn
            while isinstance(cur, ast.Attribute):
                parts.insert(0, cur.attr)
                cur = cur.value
            if not isinstance(cur, ast.Name):
                return None
            if cur.id in ("self", "cls") and "." in owner.qualname:
                candidate = ".".join(x for x in (owner.module, owner.qualname.rsplit(".", 1)[0], *parts) if x)
                return candidate
            if cur.id in aliases:
                base = aliases[cur.id]
                return ".".join([base, *parts])
            candidate = ".".join([cur.id, *parts])
            return candidate if candidate in self.index.symbols else None
        return None
