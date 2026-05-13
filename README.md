# MS Teams Attendance Reporter

Config-driven Python pipeline that turns MS Teams meeting attendance CSV
exports into a self-contained interactive HTML dashboard — attendance
histograms, EMP/CTR splits, directorate rollups with drilldown, and
trend charts across meetings.

No server, no Excel, no dependencies beyond pandas and pyyaml. One command
produces a single HTML file you open in a browser.

## Quick Start

```bash
pip install -r requirements.txt

# Try it with the included synthetic data
python -m src.cli data/synthetic/ --config config/config.yaml
open output/report.html
```

Reports land in `output/` by default (gitignored). Override with `--output`.

## Usage

```bash
# With org config (EMP/CTR splits, directorate rollups, drilldown charts)
python -m src.cli data/synthetic/ --config config/config.yaml

# Generic mode — no org classification, just attendance stats
python -m src.cli data/synthetic/

# Custom attendance cap (default: 60 min) and explicit output path
python -m src.cli data/raw/ --config config/config.yaml \
    --cap-minutes 55 --output output/raw_report.html
```

## Real Data

1. Export attendance from a Teams meeting (requires Teams Premium).
2. Drop the CSV file(s) into `data/raw/`.
3. Run the CLI against that directory:

```bash
python -m src.cli data/raw/ --config config/config.yaml
```

`data/raw/` and `output/` are both gitignored — your real attendance data
and the generated reports stay local.

## Customizing for Your Organization

1. Copy `config/config.example.yaml` to `config/config.yaml`.
2. Edit the fields:
   - `org_name` — appears in the report header
   - `name_pattern` — regex matching your Teams display names (3 capture groups: clean name, org code, employee type)
   - `labels` — your org's terms for employees/contractors and org levels
   - `org_mapping` — which sub-org codes roll up to which major orgs
3. Names that don't match the pattern are treated as external (e.g., MS trainers) and excluded from analysis.
4. Unrecognized org codes show as "UNMAPPED" in the report so you know what to add to the config.

See `config/config.example.yaml` for inline documentation of every field.

## Project Layout

```
config/            config.yaml + config.example.yaml
data/raw/          Drop real Teams CSVs here (gitignored)
data/synthetic/    Parody test fixtures — 50 "ACNE Corp" characters (committed)
output/            Generated HTML reports (gitignored)
src/
  parser.py        Parse the two-section Teams CSV format
  enricher.py      Apply org config (name classification, org rollup)
  reporter.py      Generate self-contained HTML dashboard
  cli.py           Entry point: parser → enricher → reporter
  generate_synthetic.py   Generate the test fixture CSVs
  validate_synthetic.py   Validate parser+enricher against test data
  assets/          Vendored Chart.js 4.4.6 (~200KB, MIT) inlined into
                   every report so the HTML runs fully offline
```

## Synthetic Test Data

The included test data uses "ACNE Corp" — a Temu-grade Looney Tunes parody
with 50 characters across 4 directorates. Regenerate it:

```bash
python src/generate_synthetic.py
```

Validate the pipeline against it:

```bash
python src/validate_synthetic.py
```

## License

MIT
