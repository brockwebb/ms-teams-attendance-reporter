# MS Teams Attendance Reporter

Config-driven Python pipeline that turns MS Teams meeting attendance CSV
exports into a self-contained interactive HTML dashboard.

**Status: work in progress.** Pipeline scaffolding and synthetic test data
are in place; parser, enricher, and reporter modules are not yet implemented.

## Layout

```
config/        Org mapping configs (ACME synthetic + Census real)
data/raw/      Drop raw Teams CSVs here (gitignored)
data/synthetic/ Looney-Tunes-themed test fixtures (committed)
data/processed/ Pipeline output (gitignored)
src/           Python source (parser, enricher, reporter, CLI)
```

## Generating synthetic test data

```bash
python src/generate_synthetic.py
```

Writes four meeting CSVs to `data/synthetic/` in the exact two-section format
real Teams exports use (metadata block + participant table with split
date/time data columns).

## Usage

End-to-end CLI is not wired yet. Coming next: parser → enricher → reporter.

## License

MIT
