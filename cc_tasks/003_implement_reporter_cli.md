# CC Task: Implement CLI and HTML Dashboard Reporter

## Priority: HIGH
## Status: READY
## Depends on: 002_implement_parser_enricher (COMPLETE)

## Objective
Implement `src/reporter.py` (self-contained HTML dashboard generator) and `src/cli.py` (entry point that wires parser → enricher → reporter). End state: `python -m src.cli data/synthetic/ --config config/acme_org_mapping.json` produces a single HTML file you can open in a browser with full interactive dashboard.

## Design Constraints
- Single self-contained HTML file. ALL JS/CSS inline. No external CDN dependencies. No server. Just open the file.
- Charting library: use lightweight inline SVG generation or embed a single JS charting lib as a base64 or inline script. Plotly.js standalone (~3.5MB) is acceptable since this is a local file. Alternatively, Chart.js (~200KB) is lighter. Pick one and inline it.
- The HTML file has the data baked in as a JSON blob in a `<script>` tag. No separate JSON loading step.
- Dashboard must work offline — no network requests.

## Module 3: `src/reporter.py`

### Public API
```python
def generate_report(
    meetings: list[dict],
    participants: pd.DataFrame,
    config: dict | None = None,
    output_path: str | Path = "report.html"
) -> Path:
    """Generate a self-contained interactive HTML dashboard.

    Args:
        meetings: list of metadata dicts from parser
        participants: enriched DataFrame from enricher
        config: org config (optional — if None, skip org-specific views)
        output_path: where to write the HTML file

    Returns:
        Path to generated HTML file
    """
```

### Dashboard Sections

#### 1. Summary Header
- Training series title (from config or "Teams Attendance Report")
- Total meetings analyzed
- Total unique participants
- Overall EMP/CTR (or FED/CTR) split — use `org_labels.employee_type` from config for label
- Date range covered (earliest to latest meeting)

#### 2. Meeting Summary Table
- Sortable table with columns: Date, Meeting Title, Total Attendees, EMP count, CTR count, Avg Duration (min), Dropped External count
- One row per meeting

#### 3. Attendance Duration Histogram
- Bucketed histogram of `attendance_minutes_capped` across all meetings
- Buckets: 0-5, 5-10, 10-15, 15-20, 20-25, 25-30, 30-35, 35-40, 40-45, 45-50, 50-55, 55-60
- Color-coded by EMP/CTR
- Note on chart: "Capped at 60 min"

#### 4. Horizontal Stacked Bar: EMP/CTR by Major Org
- One bar per major org (from config mapping)
- Stacked: EMP segment + CTR segment
- Sorted by total count descending
- Shows count labels on segments
- If config has `org_labels`, use those for axis label (e.g., "Directorate" instead of "Major Org")

#### 5. Major Org Drilldown
- Dropdown or tab selector to pick a major org
- Shows horizontal stacked bar of sub-orgs within that major org
- Same EMP/CTR stacking
- Only visible when a major org is selected

#### 6. Attendance Trend Over Time
- X-axis: meeting date (chronological)
- Y-axis: attendee count
- Stacked area or stacked bar: EMP on bottom, CTR on top
- Each meeting is a data point

#### 7. Trend by Major Org
- Same x-axis (meeting dates)
- Line chart with one line per major org
- Toggle lines on/off by clicking legend

#### 8. Participant Detail Table (collapsible)
- Searchable/filterable table
- Columns: Name, Org Code, Major Org, Sub Org, Type (EMP/CTR), Sessions Attended (count), Total Duration (sum), Avg Duration
- Sortable by any column
- Collapsed by default (expandable section)

### Styling
- Clean, professional. White background, subtle grid lines.
- Color palette: use a colorblind-friendly palette for EMP/CTR (e.g., blue/orange or teal/coral)
- Responsive — works on laptop screens, doesn't need to be mobile-optimized
- No Census branding. Generic enough for any org.
- Header can pull `org_name` from config if available

### Without Config (Generic Mode)
If no org config is provided:
- Skip sections 4, 5, 7 (org-specific views)
- Skip EMP/CTR classification
- Sections 1, 2, 3, 6, 8 still work with raw parsed data
- Name field shows as-is (no parsing)
- This is the "generic Teams attendance report" mode

---

## Module 4: `src/cli.py`

### Usage
```bash
# Full pipeline with org config
python -m src.cli data/synthetic/ --config config/acme_org_mapping.json --output report.html

# Generic mode (no org config)
python -m src.cli data/synthetic/ --output report.html

# Specify cap minutes
python -m src.cli data/synthetic/ --config config/acme_org_mapping.json --cap-minutes 55 --output report.html
```

### Implementation
```python
def main():
    parser = argparse.ArgumentParser(
        description='MS Teams Attendance Reporter — generate interactive HTML dashboards from Teams attendance exports'
    )
    parser.add_argument('input_dir', help='Directory containing Teams attendance CSV files')
    parser.add_argument('--config', help='Org config JSON file (optional, enables org-specific views)')
    parser.add_argument('--output', default='report.html', help='Output HTML file path (default: report.html)')
    parser.add_argument('--cap-minutes', type=float, default=60.0, help='Top-code attendance duration (default: 60)')
    args = parser.parse_args()

    # 1. Find all CSVs in input_dir
    # 2. Parse each with parser.parse_teams_csv()
    # 3. If config provided, load with enricher.load_org_config() and enrich each
    # 4. Generate report with reporter.generate_report()
    # 5. Print summary and output path
```

### Also add `src/__main__.py`
```python
from src.cli import main
main()
```

So `python -m src data/synthetic/ --config config/acme_org_mapping.json` works.

---

## Steps

1. Implement `src/reporter.py`
   - Start with the data serialization (bake meeting + participant data into HTML as JSON)
   - Build the HTML template with inline CSS
   - Add charting (pick Chart.js or Plotly, inline it)
   - Implement each dashboard section
   - Test: generate report from synthetic data, open in browser, verify all sections render
2. Implement `src/cli.py` and `src/__main__.py`
3. Run full pipeline: `python -m src.cli data/synthetic/ --config config/acme_org_mapping.json --output data/processed/report.html`
4. Verify the output HTML file opens correctly and all charts render with synthetic data
5. Run without config to verify generic mode: `python -m src.cli data/synthetic/ --output data/processed/report_generic.html`
6. Commit: `git add src/reporter.py src/cli.py src/__main__.py && git commit -m "Implement CLI and HTML dashboard reporter"`
7. Push: `git push`

## Acceptance Criteria
- [ ] `python -m src.cli data/synthetic/ --config config/acme_org_mapping.json` produces a working HTML file
- [ ] HTML file is fully self-contained (no external dependencies, works offline)
- [ ] All 8 dashboard sections render with synthetic data
- [ ] EMP/CTR stacked bar shows all 4 ACNE major orgs
- [ ] Drilldown shows sub-orgs within a selected major org
- [ ] Attendance histogram shows realistic distribution from synthetic data
- [ ] Trend chart shows 4 data points (one per meeting)
- [ ] Participant detail table is searchable and sortable
- [ ] Generic mode (no config) works — sections 1,2,3,6,8 render without org-specific views
- [ ] Meeting summary table is sortable
- [ ] No hardcoded org names in the reporter — all labels from config
- [ ] Committed and pushed

## Notes
- The HTML file will be large if inlining Plotly (~3.5MB). That's fine for local use. If it bothers you, Chart.js is ~200KB. Either works.
- The `data/processed/` directory is gitignored — generated reports won't be committed. That's correct.
- For the charting library: download it via `curl` or `wget` during the build step if needed, or use a Python package that bundles it. Do NOT rely on CDN links in the HTML — it must work offline.
- The reporter should handle the case where there's only 1 meeting (trend charts with 1 data point — just show it, don't error).
