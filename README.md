# MS Teams Attendance Reporter

Config-driven Python pipeline that turns MS Teams meeting attendance CSV
exports into a self-contained interactive HTML dashboard.

**Status: work in progress.** Pipeline scaffolding and synthetic test data
are in place; parser, enricher, and reporter modules are not yet implemented.

## Layout

```
config/         config.yaml (single source of org config) + config.example.yaml
data/raw/       Drop raw Teams CSVs here (gitignored)
data/synthetic/ Looney-Tunes-parody test fixtures (committed)
data/processed/ Pipeline output (gitignored)
src/            Python source (parser, enricher, reporter, CLI)
```

## Generating synthetic test data

```bash
python src/generate_synthetic.py
```

Writes four meeting CSVs to `data/synthetic/` in the exact two-section format
real Teams exports use (metadata block + participant table with split
date/time data columns).

## Usage

```bash
pip install -r requirements.txt

# With org config (EMP/CTR splits, directorate rollups, drilldown)
python -m src.cli data/synthetic/ --config config/config.yaml \
    --output data/processed/report.html

# Generic mode (no org classification)
python -m src.cli data/synthetic/ --output data/processed/report_generic.html

# Open the result in any browser — no server needed
open data/processed/report.html
```

## Customizing for your organization

1. Copy `config/config.example.yaml` to `config/config.yaml`.
2. Edit `org_name`, `name_pattern` (regex with three capture groups:
   clean name, org code, employee type), `labels`, and `org_mapping`.
3. Drop your real Teams attendance CSV exports into `data/raw/` and run
   the CLI against that directory.

## License

MIT
