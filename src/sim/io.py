"""Configuration loading and result serialization."""

import csv
import hashlib
import json
import subprocess
from copy import deepcopy
from pathlib import Path

import numpy as np
import yaml


def _deep_merge(base, update):
    out = deepcopy(base)
    for key, value in (update or {}).items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = deepcopy(value)
    return out


def _find_param(node, name):
    if isinstance(node, dict):
        if name in node:
            return node, name
        for value in node.values():
            found = _find_param(value, name)
            if found is not None:
                return found
    elif isinstance(node, list):
        for value in node:
            found = _find_param(value, name)
            if found is not None:
                return found
    return None


def _apply_overrides(params, overrides):
    for name, value in (overrides or {}).items():
        found = _find_param(params, name)
        if found is None:
            raise KeyError(f"unknown parameter override: {name}")
        parent, key = found
        if isinstance(parent[key], dict) and "value" in parent[key]:
            parent[key]["value"] = value
        else:
            parent[key] = value


def _load_config(path, stack):
    path = Path(path).resolve()
    if path in stack:
        chain = " -> ".join(str(item) for item in (*stack, path))
        raise ValueError(f"configuration inheritance cycle: {chain}")

    with path.open("r", encoding="utf-8") as handle:
        config = yaml.safe_load(handle) or {}
    if not isinstance(config, dict):
        raise ValueError(f"configuration root must be a mapping: {path}")

    inherit = config.pop("inherit", None)
    if inherit:
        candidates = [
            (path.parent / inherit).resolve(),
            (path.parent.parent / inherit).resolve(),
        ]
        parent_path = next((candidate for candidate in candidates if candidate.exists()), None)
        if parent_path is None:
            raise FileNotFoundError(
                f"inherited configuration {inherit!r} not found from {path}"
            )
        params = _load_config(parent_path, (*stack, path))
    else:
        params = {}

    _apply_overrides(params, config.get("overrides", {}))
    return _deep_merge(params, config)


def load_config(path):
    return _load_config(Path(path), ())


def value(params, section, name, default=None):
    block = params.get(section, {})
    entry = block.get(name, default)
    if isinstance(entry, dict) and "value" in entry:
        return entry["value"]
    return entry


def git_sha(root):
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root,
                                       text=True, stderr=subprocess.DEVNULL).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def file_md5(path):
    digest = hashlib.md5()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def tree_sha256(root):
    """Fingerprint relative paths and bytes of Python sources under root."""
    root = Path(root)
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*.py")):
        digest.update(path.relative_to(root).as_posix().encode("utf-8"))
        digest.update(b"\0")
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1 << 20), b""):
                digest.update(chunk)
        digest.update(b"\0")
    return digest.hexdigest()


def object_sha256(payload):
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True,
                         separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def write_json(path, payload):
    with Path(path).open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")


def write_ledger(path, rows):
    if not rows:
        return
    fields = list(rows[0].keys())
    with Path(path).open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def write_events(path, events, records=None):
    """Write applied storm diagnostics, retaining a row for every event."""
    fields = [
        "t", "potential_retreat", "actual_center_retreat", "center",
        "gaussian", "sigma_e", "forced", "forced_actual_retreat",
        "injected_full_m3", "injected_central_m3", "depleted_cells",
    ]
    with Path(path).open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        if records is None:
            records = [{
                "t": event.time,
                "potential_retreat": event.potential_retreat,
                "actual_center_retreat": None,
                "center": event.center,
                "gaussian": event.gaussian,
                "sigma_e": None,
                "forced": event.forced,
                "forced_actual_retreat": event.forced_actual_retreat,
                "injected_full_m3": None,
                "injected_central_m3": None,
                "depleted_cells": None,
            } for event in events]
        for record in records:
            writer.writerow({field: record.get(field) for field in fields})


def write_fields(path, fields):
    np.savez_compressed(path, **{key: np.asarray(value) for key, value in fields.items()})


def write_recovery(path, records):
    fields = ["metric", "event_index", "event_time", "cell", "duration",
              "censored", "censor_reason"]
    with Path(path).open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(records)
