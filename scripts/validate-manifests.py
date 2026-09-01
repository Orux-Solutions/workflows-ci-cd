#!/usr/bin/env python3
"""Validate Aurea module manifests without contacting production services."""

from __future__ import annotations

import json
import pathlib
import sys


ROOT = pathlib.Path.cwd()
SEARCH_ROOTS = ("apps", "packages", "src", "modules", "docs")
MANIFEST_NAMES = {"manifest.json", "module.manifest.json", "capabilities.json"}


def error(path: pathlib.Path, message: str) -> None:
    print(f"::error file={path}:{message}")


def validate(path: pathlib.Path) -> list[str]:
    problems: list[str] = []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"invalid JSON: {exc}"]

    if not isinstance(data, dict):
        return ["root must be an object"]
    for key in ("module", "section", "page"):
        if not isinstance(data.get(key), str) or not data[key].strip():
            problems.append(f"missing non-empty `{key}`")
    features = data.get("features")
    if not isinstance(features, list):
        return problems + ["`features` must be an array"]

    keys: set[str] = set()
    for index, feature in enumerate(features):
        if not isinstance(feature, dict):
            problems.append(f"features[{index}] must be an object")
            continue
        key = feature.get("key")
        if not isinstance(key, str) or not key.strip():
            problems.append(f"features[{index}] is missing a non-empty `key`")
            continue
        if key in keys:
            problems.append(f"duplicate feature key `{key}`")
        keys.add(key)
        dependencies = feature.get("dependencies", [])
        if not isinstance(dependencies, list) or any(not isinstance(dep, str) for dep in dependencies):
            problems.append(f"feature `{key}` has invalid `dependencies`")

    known = keys
    for feature in features:
        if not isinstance(feature, dict):
            continue
        key = feature.get("key", "<unknown>")
        for dependency in feature.get("dependencies", []):
            if dependency not in known:
                problems.append(f"feature `{key}` depends on unknown `{dependency}`")
    return problems


def main() -> int:
    files: list[pathlib.Path] = []
    for root in SEARCH_ROOTS:
        base = ROOT / root
        if base.exists():
            files.extend(path for path in base.rglob("*") if path.is_file() and path.name in MANIFEST_NAMES)
    files = sorted(files)
    if not files:
        print("manifest validation: no JSON manifests found; nothing to validate")
        return 0

    failures = 0
    for path in files:
        problems = validate(path)
        if problems:
            failures += len(problems)
            for problem in problems:
                error(path.relative_to(ROOT), problem)
        else:
            print(f"manifest ok: {path.relative_to(ROOT)}")
    if failures:
        print(f"manifest validation: {failures} problem(s) found", file=sys.stderr)
        return 1
    print(f"manifest validation: {len(files)} manifest(s) passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
