"""Fixed-display-column tree layout for Python comment blocks."""
from __future__ import annotations

import unicodedata
from collections import defaultdict
from .analyzer import Index, Symbol

ARROW_COLUMN = 44  # Zero-based display column of the arrow.
LINE_WIDTH = 112

def width(value: str) -> int:
    return sum(2 if unicodedata.east_asian_width(c) in ("F", "W") else 1 for c in value)

def sections(index: Index, symbol: Symbol, direction: str) -> list[str]:
    keys = sorted(symbol.calls if direction == "调用了" else symbol.callers)
    groups: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
    for key in keys:
        target = index.symbols[key]
        if target.path == symbol.path:
            category, module = "本模块", ""
        else:
            category, module = "项目模块", target.module or target.path.stem
        groups[category][module].append(target.qualname + "()")
    if direction == "调用了":
        for external in sorted(symbol.external_calls):
            module, _, func = external.rpartition(".")
            if module and func:
                groups["外部库"][module].append(func + "()")
    if not groups:
        return [f"## {direction}：{'未发现静态调用' if direction == '被调用' else '无已确认项目调用'}"]
    result = [f"## {direction}："]
    for category in ("本模块", "项目模块", "外部库"):
        if category not in groups:
            continue
        result.append("#   " + category)
        entries = sorted(groups[category].items())
        for pos, (module, names) in enumerate(entries):
            stem = "#   " + ("└─ " if pos == len(entries)-1 else "├─ ")
            if module:
                stem += module
                gap = max(1, ARROW_COLUMN - width(stem))
                first = stem + " " * gap + "→ "
            else:
                first = stem
            continuation = "# " + " " * max(0, width(first)-2)
            line = ""
            for name in sorted(set(names)):
                candidate = name if not line else line + ", " + name
                if line and width(first) + width(candidate) > LINE_WIDTH:
                    result.append(first + line + ",")
                    first = continuation
                    line = name
                else:
                    line = candidate
            result.append(first + line)
    return result

def render(index: Index, symbol: Symbol, newline: str = "\n", indent: str = "") -> str:
    lines = sections(index, symbol, "调用了") + sections(index, symbol, "被调用")
    return "".join(indent + line + newline for line in lines)
