# CC Task: Implement Parser and Enricher

## Priority: HIGH
## Status: READY
## Depends on: 001_initial_setup (COMPLETE)

## Objective
Implement the core parser (`src/parser.py`) and enricher (`src/enricher.py`) modules. These replace the monolithic `files/preprocess.py` with clean, config-driven, testable modules. Validate against the 4 synthetic CSV files in `data/synthetic/`.

## Context
- Read `CLAUDE.md` for the full Teams CSV format spec (two-section layout, column mismatch, name patterns, duration format).
- Reference `files/preprocess.py` for working logic — it handles the Census-specific case. The new modules must be **config-driven** so they work with any org's naming convention.
- The config files in `config/` now include `org_name`, `org_labels`, `name_pattern` fields. The parser should use `name_pattern` from config (not a hardcoded Census regex).
- Synthetic data in `data/synthetic/` is the canonical test fixture.

## Design Principles
1. **Two-layer architecture**: The parser handles generic Teams CSV parsing (works without any config). The enricher applies org-specific logic using a config file.
2. **Config-driven**: All org-specific behavior comes from the config JSON, not hardcoded logic.
3. **Defensive parsing**: Unknown formats, missing columns, encoding issues should produce warnings, not crashes.
4. **Deterministic**: Same input → same output. No randomness in the pipeline.

---

## Module 1: `src/parser.py`

### Responsibilities
- Parse the two-section Teams CSV format (metadata + participant table)
- Handle the header/data column count mismatch (15 header cols → 17 data cols for date+time split)
- Parse duration strings to float minutes
- Handle multiple rows per participant (drop/reconnect) — aggregate into single record per person per meeting
- Handle both tab-delimited and comma-delimited files
- Detect and handle UTF-8 BOM (`utf-8-sig`)

### Public API
```python
def parse_teams_csv(filepath: str | Path) -> dict:
    """Parse a single Teams attendance CSV.

    Returns:
        {
            'metadata': {
                'meeting_title': str,
                'attended_participants': int,
                'start_time': str,
                'end_time': str,
                'meeting_duration': str,
                'meeting_duration_min': float,
                'avg_attendance_time': str,
                'avg_attendance_min': float,
                'source_file': str,
            },
            'participants': pd.DataFrame  # columns: Name, First Join, Last Leave,
                                          # In-Meeting Duration, attendance_minutes,
                                          # Email, Participant ID (UPN), Role,
                                          # Engagement: * columns
        }
    """

def parse_duration(duration_str: str) -> float:
    """Parse '1h 59m 7s', '46m 22s', '54m 13s' → float minutes."""

def aggregate_multi_row_participants(df: pd.DataFrame) -> pd.DataFrame:
    """For participants with multiple join/leave rows (drop/reconnect),
    aggregate into a single row:
    - First Join = earliest join
    - Last Leave = latest leave
    - In-Meeting Duration = sum of all durations
    - Engagement metrics = sum across rows
    """
```

### Key Implementation Details

**Column mismatch handling**: The header has "First Join" and "Last Leave" as single columns, but data rows split each into date + time. Detection logic:
1. Parse header to get column count
2. Parse first data row to get its column count
3. If data has more columns than header, merge adjacent date+time fields
4. The merge heuristic: if a field looks like a time (matches `^\s*\d{1,2}:\d{2}`), merge it with the preceding field

**Duration parsing**: Handle these formats:
- `1h 59m 7s` → 119.117
- `54m 13s` → 54.217
- `48m` → 48.0 (no seconds)
- `15s` → 0.25
- `27s` → 0.45
- Empty/NaN → 0.0

**Multi-row aggregation**: Some participants drop and reconnect. Same email = same person. Aggregate:
- `attendance_minutes` = sum of all their duration rows
- `First Join` = min of all their join times
- `Last Leave` = max of all their leave times
- Engagement columns = sum
- Keep first row's Name, Email, UPN, Role

---

## Module 2: `src/enricher.py`

### Responsibilities
- Load org config JSON
- Parse the name field using the config's `name_pattern` regex
- Classify participants: org employee, contractor, or external (drop)
- Map org codes to major org / sub-org hierarchy
- Add `attendance_minutes_capped` (top-coded at configurable max, default 60)
- Flag unmapped org codes

### Public API
```python
def load_org_config(config_path: str | Path) -> dict:
    """Load and validate an org config JSON file.
    Returns the parsed config with compiled regex pattern.
    """

def enrich_participants(
    df: pd.DataFrame,
    config: dict,
    cap_minutes: float = 60.0
) -> tuple[pd.DataFrame, list[str]]:
    """Apply org-specific enrichment to parsed participant data.

    Args:
        df: Participant DataFrame from parser
        config: Loaded org config
        cap_minutes: Top-code attendance at this value

    Returns:
        (enriched_df, unmapped_org_codes)

    enriched_df adds columns:
        - clean_name: name without parenthetical
        - org_code: extracted org code
        - employee_type: EMP/CTR (or FED/CTR for Census)
        - is_internal: True if matches org pattern, False if external
        - major_org: rolled-up major org from mapping
        - sub_org: sub-org code (None if direct code)
        - attendance_minutes_capped: top-coded duration
    """

def classify_name(name: str, pattern: re.Pattern) -> dict | None:
    """Parse a single name field using compiled regex pattern.
    Returns dict with clean_name, org_code, employee_type or None if no match.
    """
```

### Key Implementation Details

**Config-driven regex**: The `name_pattern` field in config JSON is a regex string. For ACME synthetic data: `^(.+?)\s*\(ACME/(\S+)\s+(EMP|CTR)\)\s*$`. For Census: `^(.+?)\s*\(CENSUS/(\S+)\s+(FED|CTR)\)\s*$`. The enricher compiles this once and applies it to every name.

**Org mapping logic**:
```
org_code found in major_org's direct_codes → major_org = that major, sub_org = None
org_code found in major_org's sub_orgs → major_org = that major, sub_org = org_code
org_code not found anywhere → major_org = "UNMAPPED", sub_org = org_code
```

**External filtering**: Names that don't match the pattern are marked `is_internal = False`. The pipeline can optionally drop them (for stats) or keep them (for completeness). Default: drop.

---

## Validation Script

Create `src/validate_synthetic.py` — a standalone script that:
1. Parses all 4 synthetic CSVs using `parser.py`
2. Enriches using `enricher.py` with `config/acme_org_mapping.json`
3. Prints summary stats:
   - Per-meeting: title, total participants (before/after filtering), EMP/CTR split, attendance distribution
   - Across meetings: unique participants, avg sessions per person, champions (4/4 attendance)
   - Unmapped org codes (should be empty for synthetic data)
   - Dropped externals count per meeting
4. Validates multi-row aggregation worked (check for duplicate emails within a meeting)
5. Exit code 0 if all checks pass, 1 if any fail

```bash
python src/validate_synthetic.py
```

Expected output:
```
=== Parsing 4 synthetic meeting files ===
copilot_prompting_20260513.csv: 37 raw rows → [N] participants (dropped [M] external)
copilot_ama_20260515.csv: ...
copilot_agents_20260518.csv: ...
copilot_word_outlook_20260520.csv: ...

=== Enrichment Summary ===
Unique participants across all meetings: ~50
EMP/CTR split: ~80/20
Champions (attended all 4): [list names]
Unmapped org codes: [] (empty = PASS)
Duplicate emails after aggregation: 0 (PASS)

=== ALL CHECKS PASSED ===
```

---

## Steps

1. Implement `src/parser.py` with all functions described above
2. Implement `src/enricher.py` with all functions described above
3. Create `src/validate_synthetic.py`
4. Run validation: `python src/validate_synthetic.py`
5. Fix any issues until validation passes clean
6. Commit: `git add src/parser.py src/enricher.py src/validate_synthetic.py && git commit -m "Implement parser and enricher, validated against synthetic data"`
7. Push: `git push`

## Acceptance Criteria
- [ ] `parse_teams_csv()` correctly handles the two-section format and column mismatch
- [ ] Duration parsing handles all observed formats (h/m/s combinations, edge cases)
- [ ] Multi-row participants aggregated into single records
- [ ] `enrich_participants()` correctly classifies all 50 ACME characters
- [ ] MS trainers (no parenthetical) identified and filterable
- [ ] All org codes map correctly — zero UNMAPPED for synthetic data
- [ ] `validate_synthetic.py` exits 0
- [ ] No hardcoded Census-specific logic in parser or enricher (all from config)
- [ ] Committed and pushed

## Notes
- `files/preprocess.py` is reference code with working logic but Census-hardcoded. Port the ideas, not the code verbatim.
- The `name_pattern` in config uses standard Python regex groups: group(1)=clean name, group(2)=org code, group(3)=employee type.
- Keep imports minimal: pandas, re, json, pathlib. No external deps beyond pandas.
