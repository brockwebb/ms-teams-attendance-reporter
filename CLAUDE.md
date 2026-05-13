# MS Teams Attendance Reporter

## Project Overview
A config-driven Python pipeline that processes MS Teams meeting attendance CSV exports into a self-contained interactive HTML dashboard. Two-layer architecture: generic Teams parser + org-specific config overlay.

## Architecture
```
data/raw/          → Drop raw Teams attendance CSVs here (gitignored, real data)
data/synthetic/    → Synthetic test data (Looney-Tunes-parody themed, committed to repo)
data/processed/    → Pipeline output (gitignored)
config/            → Single YAML config (config.yaml + config.example.yaml)
src/               → Python source: parser, enricher, reporter, CLI, synthetic data generator
files/             → Legacy files from prior development thread (gitignored, reference only)
```

## Teams Attendance CSV Format
The raw file is tab-delimited with TWO sections:

### Section 1: Summary metadata (key-value pairs)
```
Meeting title\t<title>
Attended participants\t<count>
Start time\t<date>\t<time>
End time\t<date>\t<time>
Meeting duration\t<duration>
Average attendance time\t<duration>
```

### Section 2: Participant table (after "2. Participants" marker)
Header: Name, First Join, Last Leave, In-Meeting Duration, Email, Participant ID (UPN), Role, Engagement: Reaction-Applause, Engagement: Reaction-Laugh, Engagement: Reaction-Like, Engagement: Reaction-Love, Engagement: Reaction-Surprised, Engagement: Camera On, Engagement: Raise Hands, Engagement: Unmute

**CRITICAL**: "First Join" and "Last Leave" headers each map to TWO data columns (date + time). The header has 15 columns, data rows have 17. The parser must merge date+time fields.

### Name Field Pattern
The display-name field in Teams exports typically encodes org membership
in a parenthetical, e.g.:
- `Name (ACNE/CHASE EMP)` → employee, org code CHASE
- `Name (ACNE/LEGAL CTR)` → contractor, org code LEGAL
- `Name` (no parenthetical) → external participant (e.g., MS trainer), DROP from analysis

The exact pattern is configurable via `config/config.yaml`'s `name_pattern`
regex. Real-org regexes are not committed to this repo.

### Duration Format
Strings like `1h 59m 7s`, `46m 22s`, `54m 13s`. Parse to float minutes. Top-code at 60min for histograms.

## Org Mapping
Sub-org codes roll up to major orgs via `config/config.yaml`'s `org_mapping`
section:
- A major org may contain `direct_codes` (codes that ARE the major org
  itself; people at this level have no sub-org) and `sub_orgs` (codes
  that roll up under it).
- Unknown codes appear as `UNMAPPED` in the report and are echoed to
  stderr by the CLI.

## Config-Driven Design
The pipeline is reusable across any organization with the same Teams
attendance export format. Key fields in `config/config.yaml`:
- `org_name`: appears in the report header
- `name_pattern`: regex with three capture groups (clean name, org code,
  employee type)
- `labels`: customize axis labels and employee/contractor terminology
- `cap_minutes`: top-code attendance for the histogram
- `org_mapping`: hierarchical org code → major org rollup

## Synthetic Data
Looney-Tunes parody themed — legally-distinct names (ACNE = ACME parody, "Bugz Rabbit" not "Bugs Bunny", etc.). 50 characters across org units:
- Top-level org: "ACNE" (a fictional 4-directorate org used as the canonical test fixture)
- Major orgs with sub-orgs to exercise the rollup logic
- Mix of EMP and CTR designations
- Realistic attendance patterns: some full-session, some partial, some drop/reconnect
- Multiple meeting files simulating a multi-class training series
- Include some characters with NO parenthetical (to test MS trainer drop logic)

## Key Decisions
- Self-contained HTML report (no server, no Excel)
- Pandas for preprocessing
- No Jupyter — plain Python scripts
- Real data never committed; synthetic data is the canonical test fixture
- Two-layer: generic Teams parser works without org config; org-specific YAML config is an overlay

## GitHub
- Owner: brockwebb
- Repo: ms-teams-attendance-reporter
