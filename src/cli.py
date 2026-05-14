"""CLI entry point.

Wires together the parser → enricher → reporter pipeline:

    python -m src.cli data/synthetic/ \\
        --config config/config.yaml \\
        --output output/report.html

If ``--config`` is omitted the pipeline runs in generic mode (no EMP/CTR
classification, no org-specific dashboard sections).
"""

from __future__ import annotations

import argparse
import datetime as _dt
import os
import sys
from pathlib import Path

# Support both ``python -m src.cli ...`` and direct script execution.
SCRIPT_DIR = Path(__file__).resolve().parent
if __package__ in (None, ""):
    sys.path.insert(0, str(SCRIPT_DIR))
    from enricher import enrich_participants, load_org_config  # type: ignore
    from parser import parse_teams_csv  # type: ignore
    from reporter import export_csv, generate_report  # type: ignore
else:
    from .enricher import enrich_participants, load_org_config
    from .parser import parse_teams_csv
    from .reporter import export_csv, generate_report


def _resolve_output_paths(output_arg: str, timestamp: str) -> tuple[Path, Path]:
    """Resolve --output into (html_path, csv_path).

    Directory mode (trailing slash, existing directory, or no suffix):
        output_arg=output/   → output/report_TIMESTAMP.html, output/data_TIMESTAMP.csv
    File mode (path with a file suffix that isn't an existing directory):
        output_arg=foo.html  → foo.html, <parent>/data_TIMESTAMP.csv

    CSV always gets the timestamp; HTML keeps the explicit name when given.
    """
    out = Path(output_arg)
    looks_like_dir = (
        output_arg.endswith(("/", os.sep))
        or out.is_dir()
        or out.suffix == ""
    )
    if looks_like_dir:
        output_dir = out
        html_path = output_dir / f"report_{timestamp}.html"
    else:
        html_path = out
        output_dir = out.parent
    csv_path = output_dir / f"data_{timestamp}.csv"
    return html_path, csv_path


def _gather_csvs(input_dir: Path) -> list[Path]:
    if input_dir.is_file():
        return [input_dir]
    if not input_dir.is_dir():
        raise SystemExit(f"input path not found: {input_dir}")
    return sorted(input_dir.glob("*.csv"))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="MS Teams Attendance Reporter — generate an interactive HTML "
                    "dashboard from Teams attendance exports.",
    )
    ap.add_argument("input_dir",
                    help="Directory of Teams attendance CSVs (or a single CSV)")
    ap.add_argument("--config",
                    help="Org config file (YAML or JSON; enables EMP/CTR + org "
                         "rollup views). Omit for generic mode.")
    ap.add_argument("--output", default="output/",
                    help="Output destination. A directory (e.g. 'output/') "
                         "gets timestamped report_YYYYMMDD_HHMM.html and "
                         "data_YYYYMMDD_HHMM.csv files. An explicit .html "
                         "path is used as-is for HTML; the CSV is always "
                         "timestamped alongside it. Default: output/")
    ap.add_argument("--cap-minutes", type=float, default=None,
                    help="Top-code attendance duration in minutes. Overrides "
                         "the config's cap_minutes (default: 60 if neither set).")
    ap.add_argument("--title",
                    help="Override the report title (default derived from config "
                         "org_name or 'Teams Attendance Report')")
    args = ap.parse_args(argv)

    csv_files = _gather_csvs(Path(args.input_dir))
    if not csv_files:
        print(f"No CSV files found under {args.input_dir!r}", file=sys.stderr)
        return 1

    config = load_org_config(args.config) if args.config else None
    cap_minutes = (args.cap_minutes
                   if args.cap_minutes is not None
                   else (config or {}).get("cap_minutes", 60.0))
    print(f"Parsing {len(csv_files)} CSV file(s)"
          f"{' (org config: ' + str(args.config) + ')' if config else ' (generic mode)'}")

    meetings: list[dict] = []
    enriched_frames = []
    unmapped_total: set[str] = set()

    for path in csv_files:
        result = parse_teams_csv(path)
        meta = result["metadata"]
        df = result["participants"]
        if config is not None and not df.empty:
            df, unmapped = enrich_participants(df, config, cap_minutes=cap_minutes)
            unmapped_total.update(unmapped)
        if not df.empty:
            df = df.copy()
            df["source_file"] = meta.get("source_file", path.name)
        meetings.append(meta)
        enriched_frames.append(df)
        print(f"  {path.name}: {len(df)} participants")

    import pandas as pd
    combined = (pd.concat([f for f in enriched_frames if not f.empty], ignore_index=True)
                if any(not f.empty for f in enriched_frames)
                else pd.DataFrame())

    timestamp = _dt.datetime.now().strftime("%Y%m%d_%H%M")
    html_target, csv_target = _resolve_output_paths(args.output, timestamp)

    out_path = generate_report(meetings, combined, config=config,
                               output_path=html_target, title=args.title,
                               cap_minutes=cap_minutes)
    csv_path = export_csv(meetings, combined, config=config,
                          output_path=csv_target, cap_minutes=cap_minutes)
    print(f"\nReport written to: {out_path} ({out_path.stat().st_size:,} bytes)")
    print(f"CSV data written to: {csv_path} ({csv_path.stat().st_size:,} bytes)")
    if unmapped_total:
        print(f"\nUnmapped org codes (consider adding to config): {sorted(unmapped_total)}",
              file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
