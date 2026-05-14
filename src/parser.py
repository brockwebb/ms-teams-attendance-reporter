"""Parse Teams attendance CSV (two-section format).

The MS Teams attendance export is tab-delimited (sometimes comma-delimited)
with a metadata header section followed by a participant table. The header
row in the participant table is 15 columns, but data rows are 17 columns
because "First Join" and "Last Leave" each split into date + time fields.
This module reconstructs the table into 15 columns and aggregates
drop/reconnect rows into one row per participant.

No org-specific knowledge lives here — that belongs in ``enricher``.
"""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd


_DURATION_RE = re.compile(r"(\d+)\s*([hms])")
_TIME_HEAD_RE = re.compile(r"^\s*\d{1,2}:\d{2}")


def parse_duration(duration_str) -> float:
    """Parse '1h 59m 7s' / '46m 22s' / '15s' / '' → float minutes.

    Tolerant of NaN, empty strings, and partial unit lists.
    """
    if duration_str is None or (isinstance(duration_str, float) and pd.isna(duration_str)):
        return 0.0
    s = str(duration_str).strip()
    if not s:
        return 0.0
    h = m = sec = 0
    for match in _DURATION_RE.finditer(s):
        val, unit = int(match.group(1)), match.group(2)
        if unit == "h":
            h = val
        elif unit == "m":
            m = val
        elif unit == "s":
            sec = val
    return h * 60 + m + sec / 60.0


def _detect_delimiter(line: str) -> str:
    return "\t" if "\t" in line else ","


def _read_lines(filepath: Path) -> list[str]:
    """Read lines from a Teams CSV, handling encoding variations.

    Teams exports vary by platform:
      - UTF-8 with BOM (utf-8-sig) — most common on web/Mac
      - UTF-16 LE with BOM — sometimes seen on Windows desktop
    Try utf-8-sig first; on failure, fall back to utf-16. As a final
    safety net, latin-1 accepts any byte sequence so the tool can't
    hard-crash on a surprise encoding — the user will see garbled names
    in the report and know something's off.
    """
    for encoding in ("utf-8-sig", "utf-16"):
        try:
            with open(filepath, "r", encoding=encoding) as f:
                return f.readlines()
        except (UnicodeDecodeError, UnicodeError):
            continue
    with open(filepath, "r", encoding="latin-1") as f:
        return f.readlines()


def _extract_metadata(lines: list[str], source_file: str) -> dict:
    """Pull Section-1 key/value pairs until we hit the '2.' section marker."""
    metadata: dict = {"source_file": source_file}
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("2."):
            break
        parts = stripped.split("\t")
        if len(parts) < 2:
            continue
        key = parts[0].strip().lower()
        # Date+time entries split key/value across multiple tab fields; rejoin them.
        value = " ".join(p.strip() for p in parts[1:] if p.strip())
        if "meeting title" in key:
            metadata["meeting_title"] = value
        elif "attended participants" in key:
            metadata["attended_participants"] = int(value) if value.isdigit() else value
        elif "start time" in key:
            metadata["start_time"] = value
        elif "end time" in key:
            metadata["end_time"] = value
        elif "meeting duration" in key:
            metadata["meeting_duration"] = value
            metadata["meeting_duration_min"] = parse_duration(value)
        elif "average attendance" in key:
            metadata["avg_attendance_time"] = value
            metadata["avg_attendance_min"] = parse_duration(value)
    return metadata


def _find_participant_header(lines: list[str]) -> int | None:
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("Name\t") or stripped.startswith("Name,"):
            return i
    return None


def _reconcile_columns(parts: list[str], extra_cols: int) -> list[str]:
    """Merge adjacent date+time fields so a 17-field row becomes 15 fields.

    The heuristic: starting after the Name column, when the next field looks
    like a clock time (HH:MM...), merge it with the preceding date field.
    Repeat until we've collapsed ``extra_cols`` pairs.
    """
    if extra_cols <= 0:
        return parts
    merged = [parts[0]]
    i = 1
    merges_done = 0
    while i < len(parts) and merges_done < extra_cols:
        if i + 1 < len(parts) and _TIME_HEAD_RE.match(parts[i + 1]):
            merged.append(parts[i].strip() + " " + parts[i + 1].strip())
            i += 2
            merges_done += 1
        else:
            merged.append(parts[i])
            i += 1
    merged.extend(parts[i:])
    return merged


def _parse_participant_table(lines: list[str], header_idx: int) -> pd.DataFrame:
    delimiter = _detect_delimiter(lines[header_idx])
    header = [h.strip() for h in lines[header_idx].rstrip("\n").split(delimiter)]
    header_count = len(header)

    # Use the first non-empty data row to detect column-count drift
    first_data = None
    for line in lines[header_idx + 1:]:
        if line.strip():
            first_data = line.rstrip("\n").split(delimiter)
            break
    extra_cols = (len(first_data) - header_count) if first_data else 0

    rows: list[list[str]] = []
    for line in lines[header_idx + 1:]:
        stripped = line.rstrip("\n")
        if not stripped.strip():
            continue
        parts = stripped.split(delimiter)
        parts = _reconcile_columns(parts, extra_cols)
        while len(parts) < header_count:
            parts.append("")
        rows.append(parts[:header_count])

    return pd.DataFrame(rows, columns=header)


def aggregate_multi_row_participants(df: pd.DataFrame) -> pd.DataFrame:
    """Collapse drop/reconnect rows so each (Email, Name) appears exactly once.

    - First Join         → earliest of the rows (string lex order works because
                           the date/time format used in exports sorts correctly
                           only when normalized; we instead carry the row with
                           the earliest parsed Duration start by picking ``min``
                           on the raw string, which is good enough for display)
    - Last Leave         → latest (same caveat as above; display-only)
    - In-Meeting Duration→ string carried from first row (display value)
    - attendance_minutes → SUM across all rows for that participant
    - Engagement: *      → SUM across rows
    - Name, Email, UPN,
      Role              → taken from the first row in file order
    """
    if df.empty:
        return df

    # Group key: prefer Email when present; fall back to a per-row sentinel so
    # missing-email rows aren't accidentally merged with one another.
    email_series = df["Email"].astype(str).str.strip() if "Email" in df.columns else pd.Series([""] * len(df))
    group_keys = [
        email if email else f"_anon_{idx}"
        for idx, email in enumerate(email_series)
    ]
    df = df.assign(_group_key=group_keys)

    engagement_cols = [c for c in df.columns if c.startswith("Engagement:")]
    for col in engagement_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)

    sum_cols = ["attendance_minutes"] + engagement_cols
    first_cols = [
        c for c in df.columns
        if c not in sum_cols + ["_group_key", "First Join", "Last Leave"]
    ]

    agg: dict = {c: "first" for c in first_cols}
    agg.update({c: "sum" for c in sum_cols})
    agg["First Join"] = "min"
    agg["Last Leave"] = "max"

    # sort=False preserves file order of the first appearance of each group
    grouped = df.groupby("_group_key", sort=False, as_index=False).agg(agg)
    grouped = grouped.drop(columns=["_group_key"])
    # Restore original column order
    grouped = grouped[[c for c in df.columns if c != "_group_key"]]
    return grouped.reset_index(drop=True)


def parse_teams_csv(filepath) -> dict:
    """Parse a single Teams attendance CSV.

    Returns ``{'metadata': dict, 'participants': pd.DataFrame}``. The
    participants frame has one row per unique participant (drop/reconnect
    rows already aggregated) plus a numeric ``attendance_minutes`` column.
    """
    path = Path(filepath)
    lines = _read_lines(path)

    metadata = _extract_metadata(lines, source_file=path.name)
    header_idx = _find_participant_header(lines)
    if header_idx is None:
        return {"metadata": metadata, "participants": pd.DataFrame()}

    df = _parse_participant_table(lines, header_idx)
    if df.empty:
        return {"metadata": metadata, "participants": df}

    # Derive numeric attendance_minutes from the In-Meeting Duration string
    duration_cols = [c for c in df.columns if "duration" in c.lower()]
    if duration_cols:
        df["attendance_minutes"] = df[duration_cols[0]].apply(parse_duration)
    else:
        df["attendance_minutes"] = 0.0

    df = aggregate_multi_row_participants(df)
    return {"metadata": metadata, "participants": df}
