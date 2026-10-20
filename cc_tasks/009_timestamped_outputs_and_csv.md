# CC Task: Timestamped Output Filenames + CSV Data Export

## Priority: HIGH
## Status: READY
## Depends on: 008_fix_chart_axes (COMPLETE)

## Objective
Two changes to output handling:
1. Timestamped filenames so reports don't overwrite each other
2. CSV data export alongside the HTML report — the "Excel people" escape hatch

## Part 1: Timestamped Output Filenames

### Current behavior
`--output` defaults to `output/report.html`. Every run overwrites the last.

### New behavior
When `--output` specifies a **directory** (or uses the default), generate timestamped filenames:
```
output/report_20260514_1430.html
output/data_20260514_1430.csv
```

Format: `{base}_{YYYYMMDD}_{HHMM}.{ext}` using local time at generation.

When `--output` specifies a **file path** (e.g. `output/my_report.html`), respect the exact name for the HTML but still generate the CSV alongside it with matching timestamp:
```
output/my_report.html
output/data_20260514_1430.csv
```

### Implementation — `src/cli.py`
- Import `datetime`
- After parsing args, generate the timestamp string: `datetime.datetime.now().strftime("%Y%m%d_%H%M")`
- Determine if `args.output` looks like a directory path (ends with `/`, is an existing dir, or equals the default `output/report.html`)
- If default/directory: construct `output/report_{timestamp}.html`
- If explicit file: use as-is for HTML
- CSV path: always `{output_dir}/data_{timestamp}.csv`
- Pass both paths downstream

### CLI changes
- Change `--output` default to `"output/"` (directory, not file)
- Add print line for CSV path alongside the HTML print line

## Part 2: CSV Data Export

### What goes in the CSV
One row per (meeting × participant) — the same `rows` payload that feeds the HTML dashboard, plus meeting metadata joined in. No names, no PII. Columns:

| Column | Source | Notes |
|--------|--------|-------|
| meeting_date | meetings_meta.date | ISO format YYYY-MM-DD |
| meeting_title | meetings_meta.meeting_title | |
| meeting_duration_min | meetings_meta.duration_min | |
| source_file | row.source_file | links to meeting |
| employee_type | row.employee_type | EMP/CTR (or config labels) |
| major_org | row.major_org | null in generic mode |
| sub_org | row.sub_org | null in generic mode |
| attendance_minutes | row.minutes | capped value |
| pid | row.pid | integer, deduplication key |

### Implementation — `src/reporter.py`
Add a new function `export_csv(meetings, participants, config, output_path, cap_minutes)`:

```python
import csv

def export_csv(meetings: list[dict],
               participants: pd.DataFrame,
               config: dict | None = None,
               output_path: str | Path = "output/data.csv",
               cap_minutes: float | None = None) -> Path:
    """Write a flat CSV of attendance data. No names/PII."""
    if cap_minutes is None:
        cap_minutes = float((config or {}).get("cap_minutes", DEFAULT_CAP_MINUTES))

    has_config = config is not None
    payload = _build_payload(meetings, participants, config, float(cap_minutes))

    # Build a lookup from source_file → meeting metadata
    meta_lookup = {m["source_file"]: m for m in payload["meetings"]}

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "meeting_date", "meeting_title", "meeting_duration_min",
        "source_file", "employee_type", "major_org", "sub_org",
        "attendance_minutes", "pid",
    ]

    with open(out, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in payload["rows"]:
            meta = meta_lookup.get(row["source_file"], {})
            writer.writerow({
                "meeting_date": meta.get("date", ""),
                "meeting_title": meta.get("meeting_title", ""),
                "meeting_duration_min": meta.get("duration_min", ""),
                "source_file": row["source_file"],
                "employee_type": row.get("employee_type", ""),
                "major_org": row.get("major_org", ""),
                "sub_org": row.get("sub_org", ""),
                "attendance_minutes": row["minutes"],
                "pid": row["pid"],
            })
    return out
```

### Integration in `src/cli.py`
After `generate_report(...)`, call `export_csv(...)` with the CSV path. Print the CSV output path and size.

```python
from .reporter import generate_report, export_csv

# ... after generate_report call ...
csv_path = export_csv(meetings, combined, config=config,
                      output_path=csv_output_path, cap_minutes=cap_minutes)
print(f"CSV data written to: {csv_path} ({csv_path.stat().st_size:,} bytes)")
```

## Steps
1. Edit `src/reporter.py` — add `export_csv()` function
2. Edit `src/cli.py` — timestamp logic, default change, CSV call
3. Regenerate with synthetic data: `python -m src.cli data/synthetic/ --config config/config.yaml`
4. Verify:
   - HTML output has timestamped filename in `output/`
   - CSV output has matching timestamp in `output/`
   - CSV has correct columns, correct row count, no names/PII
   - Running again produces new files (no overwrite)
   - Explicit `--output output/custom.html` still works for HTML, CSV still gets timestamp
5. Spot-check CSV in a spreadsheet — columns parse cleanly, no encoding issues
6. Commit: `git add -A && git commit -m "Add timestamped output filenames and CSV data export"`
7. Push: `git push`

## Acceptance Criteria
- [ ] Default run produces timestamped HTML and CSV in `output/`
- [ ] Repeated runs do not overwrite previous output
- [ ] CSV contains all expected columns with no PII
- [ ] CSV row count matches HTML dashboard participant-rows
- [ ] Explicit `--output` path still works for HTML
- [ ] Generic mode (no config) produces valid CSV (major_org/sub_org/employee_type empty)
- [ ] No regressions in HTML report
- [ ] Committed and pushed

## Design Notes
- Reuses `_build_payload()` to guarantee CSV and HTML show identical data
- `pid` is included so Excel users can dedup unique participants across meetings
- No `clean_name` or `Name` column — PII never leaves the pipeline
- CSV uses `csv.DictWriter` (not pandas `to_csv`) to avoid adding a pandas dependency for a trivial operation — though pandas is already imported, DictWriter gives explicit column control
