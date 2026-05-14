"""Enrich parsed data with org mapping.

The parser produces a generic participant frame that knows nothing about
any particular organization. The enricher applies an org-specific config
(loaded from YAML, with JSON tolerated for backward compatibility) that
supplies a name-pattern regex and a major/sub-org rollup. Swapping the
config swaps the org — no code changes.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd


def _normalize_config(raw: dict, source: str) -> dict:
    """Coerce a loaded config (YAML- or JSON-shaped) into the canonical
    internal structure. Older JSON used 'major_orgs' / 'org_labels' with
    different sub-keys; new YAML uses 'org_mapping' / 'labels'. Either is
    accepted but downstream code only sees the canonical shape.
    """
    org_mapping = raw.get("org_mapping") or raw.get("major_orgs")
    if org_mapping is None:
        raise ValueError(f"{source}: missing 'org_mapping' (or legacy 'major_orgs')")

    name_pattern = raw.get("name_pattern")
    if name_pattern is None:
        raise ValueError(f"{source}: missing 'name_pattern'")

    # Labels: prefer new 'labels', fall back to legacy 'org_labels' mapping.
    new_labels = raw.get("labels") or {}
    legacy = raw.get("org_labels") or {}
    labels = {
        "employee": new_labels.get("employee", "EMP"),
        "contractor": new_labels.get("contractor", "CTR"),
        # Legacy 'level_2' (e.g., "Directorate") becomes new 'level_1';
        # legacy 'level_3' (e.g., "Division") becomes new 'level_2'.
        "level_1": new_labels.get("level_1") or legacy.get("level_2") or "Major Org",
        "level_2": new_labels.get("level_2") or legacy.get("level_3") or "Sub Org",
    }

    cap_minutes = raw.get("cap_minutes")
    if cap_minutes is None:
        cap_minutes = 60.0
    cap_minutes = float(cap_minutes)

    return {
        "org_name": str(raw.get("org_name", "")),
        "name_pattern": str(name_pattern),
        "labels": labels,
        "cap_minutes": cap_minutes,
        "org_mapping": org_mapping,
    }


def load_org_config(config_path) -> dict:
    """Load an org config (YAML or JSON) and pre-compile lookups.

    The returned dict has a canonical shape — ``org_name``, ``name_pattern``,
    ``labels``, ``cap_minutes``, ``org_mapping`` — plus three derived keys
    used by the enricher itself: ``_compiled_pattern``, ``_code_to_major``,
    ``_code_to_sub`` (None for direct codes).
    """
    path = Path(config_path)
    suffix = path.suffix.lower()

    if suffix in (".yaml", ".yml"):
        try:
            import yaml
        except ImportError as exc:
            raise ImportError(
                f"YAML config requested but pyyaml isn't installed. "
                f"Run `pip install pyyaml>=6.0` (or `pip install -r requirements.txt`). "
                f"Original error: {exc}"
            ) from exc
        with open(path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f)
    elif suffix == ".json":
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)
    else:
        raise ValueError(f"Unsupported config extension {suffix!r} for {path}")

    if not isinstance(raw, dict):
        raise ValueError(f"{path}: top-level config must be a mapping")

    cfg = _normalize_config(raw, str(path))
    cfg["_compiled_pattern"] = re.compile(cfg["name_pattern"])

    code_to_major: dict[str, str] = {}
    code_to_sub: dict[str, str | None] = {}
    for major, info in cfg["org_mapping"].items():
        info = info or {}
        for code in info.get("direct_codes", []) or []:
            code_to_major[code] = major
            code_to_sub[code] = None
        for code in info.get("sub_orgs", []) or []:
            code_to_major[code] = major
            code_to_sub[code] = code
    cfg["_code_to_major"] = code_to_major
    cfg["_code_to_sub"] = code_to_sub
    return cfg


def classify_name(name, pattern: re.Pattern) -> dict | None:
    """Extract ``clean_name`` / ``org_code`` / ``employee_type`` from a name.

    Returns ``None`` when the name doesn't match the pattern (typically MS
    trainers or other externals that lack the org parenthetical).
    """
    if name is None or (isinstance(name, float) and pd.isna(name)):
        return None
    match = pattern.match(str(name).strip())
    if not match:
        return None
    return {
        "clean_name": match.group(1).strip(),
        "org_code": match.group(2).strip(),
        "employee_type": match.group(3).strip(),
    }


def enrich_participants(
    df: pd.DataFrame,
    config: dict,
    cap_minutes: float | None = None,
) -> tuple[pd.DataFrame, list[str]]:
    """Add classification + org-mapping columns to a participant frame.

    Returns ``(enriched_df, sorted_unmapped_codes)``. Codes that survive
    the rollup as ``UNMAPPED`` are reported so the caller can prompt the
    operator to extend the org_mapping section of the config.

    ``cap_minutes`` defaults to whatever the config specifies (60 if
    unset). Pass an explicit value to override.
    """
    if df.empty:
        return df.copy(), []

    pattern = config["_compiled_pattern"]
    code_to_major = config["_code_to_major"]
    code_to_sub = config["_code_to_sub"]
    cap = cap_minutes if cap_minutes is not None else config.get("cap_minutes", 60.0)

    out = df.copy()
    parsed = out["Name"].apply(lambda n: classify_name(n, pattern))

    out["is_internal"] = parsed.notna()
    out["clean_name"] = parsed.apply(lambda p: p["clean_name"] if p else None)
    out["org_code"] = parsed.apply(lambda p: p["org_code"] if p else None)
    out["employee_type"] = parsed.apply(lambda p: p["employee_type"] if p else None)

    unmapped: set[str] = set()

    def _is_missing(code):
        # Pandas coerces None → NaN in mixed-type Series, so a plain
        # ``code is None`` check misses externals after a column round-trip.
        return code is None or (isinstance(code, float) and pd.isna(code))

    def map_major(code):
        if _is_missing(code):
            return None
        if code in code_to_major:
            return code_to_major[code]
        unmapped.add(code)
        return "UNMAPPED"

    def map_sub(code):
        if _is_missing(code):
            return None
        # Unknown codes carry their own code as sub_org so the report still
        # shows something identifiable.
        return code_to_sub.get(code, code)

    out["major_org"] = out["org_code"].apply(map_major)
    out["sub_org"] = out["org_code"].apply(map_sub)

    if "attendance_minutes" in out.columns:
        out["attendance_minutes_capped"] = out["attendance_minutes"].clip(upper=cap)

    return out, sorted(unmapped)
