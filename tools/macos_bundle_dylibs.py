#!/usr/bin/env python3
"""
Bundle and rebase non-system dylib dependencies into a macOS .app Frameworks dir.

Typical usage:
  python3 tools/macos_bundle_dylibs.py \
    --app dist/Transcriby.app \
    --root dist/Transcriby.app/Contents/Frameworks/libmpv.dylib
"""

from __future__ import annotations

import argparse
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path

SYSTEM_PREFIXES = ("/System/", "/usr/lib/")
EXTERNAL_PREFIXES = ("/opt/homebrew/", "/usr/local/", "/opt/local/")


def run_cmd(cmd: list[str]) -> str:
    proc = subprocess.run(cmd, check=True, capture_output=True, text=True)
    return proc.stdout


def parse_otool_deps(binary: Path) -> list[str]:
    out = run_cmd(["otool", "-L", str(binary)])
    lines = out.splitlines()
    deps: list[str] = []
    for line in lines[1:]:
        line = line.strip()
        if not line:
            continue
        dep = line.split(" (", 1)[0].strip()
        if dep:
            deps.append(dep)
    return deps


def is_system_dep(dep: str) -> bool:
    return dep.startswith(SYSTEM_PREFIXES)


def is_external_dep(dep: str) -> bool:
    return dep.startswith(EXTERNAL_PREFIXES)


def make_writable(path: Path) -> None:
    mode = path.stat().st_mode
    path.chmod(mode | stat.S_IWUSR)


def install_name_change(target: Path, old: str, new: str) -> None:
    make_writable(target)
    subprocess.run(
        ["install_name_tool", "-change", old, new, str(target)],
        check=True,
        capture_output=True,
        text=True,
    )


def install_name_id(target: Path, new_id: str) -> None:
    make_writable(target)
    subprocess.run(
        ["install_name_tool", "-id", new_id, str(target)],
        check=True,
        capture_output=True,
        text=True,
    )


def ensure_exec_bit(path: Path) -> None:
    mode = path.stat().st_mode
    path.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def ensure_bundled(dep: str, frameworks_dir: Path, name_to_source: dict[str, str]) -> Path:
    src = Path(dep).resolve()
    if not src.is_file():
        raise RuntimeError(f"Dependency not found on disk: {dep}")

    name = src.name
    if name in name_to_source and name_to_source[name] != str(src):
        raise RuntimeError(
            f"Dylib filename collision for '{name}':\n"
            f"  existing source: {name_to_source[name]}\n"
            f"  new source:      {src}"
        )
    name_to_source[name] = str(src)

    dest = frameworks_dir / name
    if not dest.exists():
        shutil.copy2(src, dest)
        ensure_exec_bit(dest)

    return dest


def rebase_tree(root: Path, frameworks_dir: Path) -> list[Path]:
    queue: list[Path] = [root.resolve()]
    seen: set[Path] = set()
    name_to_source: dict[str, str] = {}
    touched: list[Path] = []

    while queue:
        current = queue.pop(0).resolve()
        if current in seen:
            continue
        seen.add(current)
        touched.append(current)

        # Normalize dylib id for bundled libs.
        if current.parent == frameworks_dir and current.suffix == ".dylib":
            install_name_id(current, f"@loader_path/{current.name}")

        deps = parse_otool_deps(current)
        for dep in deps:
            if dep.startswith("@loader_path/"):
                dep_name = dep.split("/", 1)[1]
                local_dep = frameworks_dir / dep_name
                if local_dep.exists():
                    queue.append(local_dep)
                continue

            if dep.startswith("@rpath/"):
                dep_name = dep.split("/", 1)[1]
                local_dep = frameworks_dir / dep_name
                if local_dep.exists():
                    install_name_change(current, dep, f"@loader_path/{dep_name}")
                    queue.append(local_dep)
                continue

            if dep.startswith("@executable_path/"):
                dep_name = dep.rsplit("/", 1)[-1]
                local_dep = frameworks_dir / dep_name
                if local_dep.exists():
                    install_name_change(current, dep, f"@loader_path/{dep_name}")
                    queue.append(local_dep)
                continue

            if not dep.startswith("/"):
                continue
            if is_system_dep(dep):
                continue

            bundled = ensure_bundled(dep, frameworks_dir, name_to_source)
            install_name_change(current, dep, f"@loader_path/{bundled.name}")
            queue.append(bundled)

    return touched


def verify_no_external_refs(paths: list[Path]) -> list[str]:
    issues: list[str] = []
    for path in paths:
        try:
            deps = parse_otool_deps(path)
        except Exception as ex:
            issues.append(f"{path}: unable to inspect deps: {ex}")
            continue

        for dep in deps:
            if dep.startswith("/"):
                if is_external_dep(dep):
                    issues.append(f"{path}: external dependency reference remains: {dep}")
    return issues


def main() -> int:
    parser = argparse.ArgumentParser(description="Bundle/rebase dylib dependencies into app Frameworks.")
    parser.add_argument("--app", required=True, help="Path to .app bundle")
    parser.add_argument("--root", required=True, help="Root bundled dylib to recurse from (e.g. libmpv.dylib)")
    args = parser.parse_args()

    app_path = Path(args.app).resolve()
    if not app_path.is_dir():
        raise SystemExit(f"App bundle not found: {app_path}")

    frameworks_dir = app_path / "Contents" / "Frameworks"
    frameworks_dir.mkdir(parents=True, exist_ok=True)

    root = Path(args.root).resolve()
    if not root.is_file():
        raise SystemExit(f"Root dylib not found: {root}")

    touched = rebase_tree(root=root, frameworks_dir=frameworks_dir)

    # Verify all bundled libs are now local/system only.
    dylibs = sorted({p for p in touched if p.parent == frameworks_dir and p.suffix == ".dylib"})
    issues = verify_no_external_refs(dylibs)
    if issues:
        print("ERROR: unresolved external dylib references after rebasing:", file=sys.stderr)
        for issue in issues:
            print(f"  - {issue}", file=sys.stderr)
        return 1

    print("Bundled/rebased dylibs:")
    for lib in dylibs:
        print(f"  - {lib}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
