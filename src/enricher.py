"""Enrich parsed data with org mapping.

The parser produces a generic participant frame that knows nothing about
any particular organization. The enricher applies an org-specific config
(loaded from JSON) that supplies a name-pattern regex and a major-org /
sub-org rollup. Swapping the config swaps the org — no code changes.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd


def load_org_config(config_path) -> dict:
    """Load an org config JSON and pre-compile lookups for the enricher.

    The returned dict includes the raw config plus three derived keys:
      * ``_compiled_pattern``   compiled ``name_pattern`` regex
      * ``_code_to_major``      dict mapping any known code → major org name
      * ``_code_to_sub``        dict mapping any known code → sub-org code
                                (None for direct codes)
    """
    with open(config_path, "r", encoding="utf-8") as f:
        cfg = json.load(f)

    if "name_pattern" not in cfg:
        raise ValueError(f"{config_path}: missing required 'name_pattern' field")
    if "major_orgs" not in cfg:
        raise ValueError(f"{config_path}: missing required 'major_orgs' field")

    cfg["_compiled_pattern"] = re.compile(cfg["name_pattern"])

    code_to_major: dict[str, str] = {}
    code_to_sub: dict[str, str | None] = {}
    for major, info in cfg["major_orgs"].items():
        for code in info.get("direct_codes", []):
            code_to_major[code] = major
            code_to_sub[code] = None
        for code in info.get("sub_orgs", []):
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
    cap_minutes: float = 60.0,
) -> tuple[pd.DataFrame, list[str]]:
    """Add classification + org-mapping columns to a participant frame.

    Returns ``(enriched_df, sorted_unmapped_codes)``. Codes that survive the
    rollup as ``UNMAPPED`` are reported so the caller can prompt the operator
    to add them to the org config.
    """
    if df.empty:
        return df.copy(), []

    pattern = config["_compiled_pattern"]
    code_to_major = config["_code_to_major"]
    code_to_sub = config["_code_to_sub"]

    out = df.copy()
    parsed = out["Name"].apply(lambda n: classify_name(n, pattern))

    out["is_internal"] = parsed.notna()
    out["clean_name"] = parsed.apply(lambda p: p["clean_name"] if p else None)
    out["org_code"] = parsed.apply(lambda p: p["org_code"] if p else None)
    out["employee_type"] = parsed.apply(lambda p: p["employee_type"] if p else None)

    unmapped: set[str] = set()

    def map_major(code):
        if code is None:
            return None
        if code in code_to_major:
            return code_to_major[code]
        unmapped.add(code)
        return "UNMAPPED"

    def map_sub(code):
        if code is None:
            return None
        # Unknown codes carry their own code as sub_org so the report still
        # shows something identifiable.
        return code_to_sub.get(code, code)

    out["major_org"] = out["org_code"].apply(map_major)
    out["sub_org"] = out["org_code"].apply(map_sub)

    if "attendance_minutes" in out.columns:
        out["attendance_minutes_capped"] = out["attendance_minutes"].clip(upper=cap_minutes)

    return out, sorted(unmapped)
