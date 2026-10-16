"""Run with python -m code_annotations COMMAND TARGET [--root PROJECT_ROOT]."""
from __future__ import annotations

import argparse
from pathlib import Path
from .analyzer import Index
from .editor import edit, diff, apply_batch

def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Generate and reversibly remove Python call annotations")
    parser.add_argument("command", choices=("write", "remove", "inspect", "check"))
    parser.add_argument("target", nargs="?", default=".")
    parser.add_argument("--root", type=Path, help="Project root for full call graph indexing")
    args = parser.parse_args(argv)
    target = Path(args.target).resolve()
    if not target.exists():
        parser.error(f"No such target: {target}")
    root = (args.root or (target if target.is_dir() else target.parent)).resolve()
    if target.is_relative_to(root) is False:
        parser.error("Target must be inside --root")
    index = Index(root).build()
    paths = ([target] if target.is_file() else sorted(path for path in index.by_file if path.is_relative_to(target)))
    mode = "remove" if args.command == "remove" else "write"
    changed = 0
    changes = []
    for path in paths:
        if path.suffix != ".py" or path.resolve() not in index.by_file:
            continue
        before, after = edit(path.resolve(), index, mode)
        if before == after:
            continue
        changed += 1
        if args.command in ("inspect", "check"):
            print(diff(path, before, after))
        else:
            changes.append((path, before, after))
    if changes:
        apply_batch(changes)
        for path, _, _ in changes:
            print(f"Updated: {path}")
    print(f"{changed} file(s) {'out of date' if args.command=='check' else 'changed or would change'}")
    return 1 if args.command == "check" and changed else 0

if __name__ == "__main__":
    raise SystemExit(main())
