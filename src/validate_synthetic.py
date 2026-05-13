#!/usr/bin/env python3
"""End-to-end smoke test against the committed synthetic data.

Parses all CSVs under ``data/synthetic/`` using ``parser``, enriches them
with ``config/acme_org_mapping.json``, prints summary stats, and asserts
the invariants that the pipeline must hold for the canonical fixtures.

Exits 0 if every check passes, 1 otherwise.
"""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

import pandas as pd

# Make ``src`` importable when running as a script
SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from enricher import enrich_participants, load_org_config  # noqa: E402
from parser import parse_teams_csv  # noqa: E402


REPO_ROOT = SCRIPT_DIR.parent
SYNTHETIC_DIR = REPO_ROOT / "data" / "synthetic"
CONFIG_PATH = REPO_ROOT / "config" / "acme_org_mapping.json"


def main() -> int:
    failures: list[str] = []
    config = load_org_config(CONFIG_PATH)
    csv_files = sorted(SYNTHETIC_DIR.glob("*.csv"))
    if not csv_files:
        print(f"FAIL: no CSV files in {SYNTHETIC_DIR}")
        return 1

    print(f"=== Parsing {len(csv_files)} synthetic meeting files ===")
    per_meeting_enriched: list[pd.DataFrame] = []
    all_unmapped: set[str] = set()

    for csv in csv_files:
        result = parse_teams_csv(csv)
        meta = result["metadata"]
        participants = result["participants"]
        raw_rows = len(participants)

        enriched, unmapped = enrich_participants(participants, config)
        all_unmapped.update(unmapped)
        internal = enriched[enriched["is_internal"]]
        external = enriched[~enriched["is_internal"]]

        # Per-meeting invariant: aggregator should have left zero duplicates by email
        dup_emails = (
            internal["Email"].value_counts().pipe(lambda s: s[s > 1])
            if "Email" in internal.columns
            else pd.Series(dtype=int)
        )
        if len(dup_emails) > 0:
            failures.append(
                f"{csv.name}: duplicate emails after aggregation: {dup_emails.to_dict()}"
            )

        emp_count = int((internal["employee_type"] == "EMP").sum())
        ctr_count = int((internal["employee_type"] == "CTR").sum())
        title = meta.get("meeting_title", "<unknown>")
        print(
            f"  {csv.name}: {raw_rows} unique rows → {len(internal)} internal "
            f"(EMP {emp_count}, CTR {ctr_count}); dropped {len(external)} external "
            f"({title!r})"
        )
        per_meeting_enriched.append(internal.assign(_source=csv.name))

    if not per_meeting_enriched:
        print("FAIL: no participants parsed from any file")
        return 1

    combined = pd.concat(per_meeting_enriched, ignore_index=True)

    print("\n=== Enrichment Summary ===")
    unique = combined.groupby("Email").size().reset_index(name="meetings_attended")
    unique = unique.merge(
        combined.drop_duplicates("Email")[["Email", "clean_name"]],
        on="Email",
        how="left",
    )

    total_meetings = len(csv_files)
    champions = unique[unique["meetings_attended"] == total_meetings]["clean_name"].tolist()
    one_only = unique[unique["meetings_attended"] == 1]["clean_name"].tolist()

    emp_share = (combined["employee_type"] == "EMP").mean()
    ctr_share = (combined["employee_type"] == "CTR").mean()

    print(f"Unique internal participants across all meetings: {len(unique)}")
    print(f"EMP/CTR split: {emp_share:.0%} / {ctr_share:.0%}")
    print(f"Champions (attended all {total_meetings}): {sorted(champions)}")
    print(f"Attended exactly 1 meeting: {len(one_only)} people")

    unmapped_sorted = sorted(all_unmapped)
    print(f"Unmapped org codes: {unmapped_sorted or '[] (PASS)'}")
    if unmapped_sorted:
        failures.append(f"unmapped org codes present: {unmapped_sorted}")

    # Sanity: every internal row should have a non-null major_org
    null_major = combined["major_org"].isna().sum()
    if null_major:
        failures.append(f"{null_major} internal rows have null major_org")

    # Sanity: attendance_minutes_capped should never exceed 60
    if (combined["attendance_minutes_capped"] > 60).any():
        failures.append("attendance_minutes_capped exceeds 60 for some rows")

    # Sanity: org_code should always be present for internal rows
    if combined["org_code"].isna().any():
        failures.append("some internal rows have null org_code")

    # Sanity: duplicate-emails-per-meeting check already ran in the loop
    duplicate_failures = [f for f in failures if "duplicate emails" in f]
    if not duplicate_failures:
        print("Duplicate emails after aggregation: 0 (PASS)")

    if failures:
        print("\n=== FAILED ===")
        for fail in failures:
            print(f"  - {fail}")
        return 1

    print("\n=== ALL CHECKS PASSED ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
