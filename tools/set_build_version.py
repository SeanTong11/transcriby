#!/usr/bin/env python3

"""Generate transcriby/build_version.py from CI context."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
import tomllib


@dataclass
class BuildInfo:
    base_version: str
    app_version: str
    channel: str
    tag: str
    commit: str


def read_base_version(pyproject_path: Path) -> str:
    with pyproject_path.open("rb") as f:
        data = tomllib.load(f)
    return str(data.get("project", {}).get("version", "0.0.0"))


def resolve_build_info(base_version: str) -> BuildInfo:
    ref = os.getenv("GITHUB_REF", "").strip()
    ref_name = os.getenv("GITHUB_REF_NAME", "").strip()
    commit = os.getenv("GITHUB_SHA", "").strip()
    short_commit = commit[:7]

    channel = "dev"
    tag = ref_name
    app_version = base_version

    if ref.startswith("refs/tags/v"):
        channel = "stable"
        tag = ref_name
        if ref_name.startswith("v") and len(ref_name) > 1:
            app_version = ref_name[1:]
    elif ref == "refs/heads/main":
        channel = "nightly"
        tag = "nightly"
        app_version = f"{base_version}-nightly+{short_commit}" if short_commit else f"{base_version}-nightly"
    else:
        app_version = f"{base_version}-dev+{short_commit}" if short_commit else base_version

    return BuildInfo(
        base_version=base_version,
        app_version=app_version,
        channel=channel,
        tag=tag,
        commit=short_commit,
    )


def render_build_module(info: BuildInfo) -> str:
    return (
        '"""Build/version metadata for runtime and session exports.\n\n'
        "This file is updated by CI via tools/set_build_version.py.\n"
        '"""\n\n'
        f'APP_BASE_VERSION = "{info.base_version}"\n'
        f'APP_VERSION = "{info.app_version}"\n'
        f'BUILD_CHANNEL = "{info.channel}"\n'
        f'BUILD_TAG = "{info.tag}"\n'
        f'BUILD_COMMIT = "{info.commit}"\n'
    )


def main() -> int:
    repo_root = Path(__file__).resolve().parent.parent
    pyproject_path = repo_root / "pyproject.toml"
    output_path = repo_root / "transcriby" / "build_version.py"

    base_version = read_base_version(pyproject_path)
    info = resolve_build_info(base_version)
    output_path.write_text(render_build_module(info), encoding="utf-8")

    print(f"[build-version] wrote: {output_path}")
    print(f"[build-version] base_version={info.base_version}")
    print(f"[build-version] app_version={info.app_version}")
    print(f"[build-version] channel={info.channel}")
    print(f"[build-version] tag={info.tag}")
    print(f"[build-version] commit={info.commit}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
