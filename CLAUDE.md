# MS Teams Attendance Reporter

## Project Overview
A config-driven Python pipeline that processes MS Teams meeting attendance CSV exports into a self-contained interactive HTML dashboard. Two-layer architecture: generic Teams parser + org-specific config overlay.

## Architecture
```
data/raw/          → Drop raw Teams attendance CSVs here (gitignored, real data)
data/synthetic/    → Synthetic test data (Looney Tunes themed, committed to repo)
data/processed/    → Pipeline output (gitignored)
config/            → Org mapping, column config, synthetic data generation config
src/               → Python source: preprocessor, report generator, synthetic data generator
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
- `Name (CENSUS/CSVD FED)` → Federal employee, org code CSVD
- `Name (CENSUS/OCIO CTR)` → Contractor, org code OCIO
- `Name` (no parenthetical) → MS trainer, DROP from analysis
- Pattern: `^(.+?)\s*\(CENSUS/(\S+)\s+(FED|CTR)\)\s*$`

### Duration Format
Strings like `1h 59m 7s`, `46m 22s`, `54m 13s`. Parse to float minutes. Top-code at 60min for histograms.

## Org Mapping
Sub-org codes roll up to major orgs via config/org_mapping.json:
- CSVD, ADSD, OIS, ITSMO, CSD → CIO (major org)
- OCIO → CIO (direct, top-level)
- Unknown codes → UNMAPPED (flagged in report)

## Config-Driven Design
The pipeline should be reusable beyond Census. Key config points:
- `org_labels`: rename "Company"→"Agency", "Division"→"Directorate" etc.
- `name_pattern`: regex for parsing the name field (default: Census pattern)
- `org_mapping`: hierarchical org code → major org rollup
- Column names configurable so other orgs can swap labels

## Synthetic Data
Looney Tunes themed. 50 characters across org units:
- Top-level org: "ACME" (analogous to "CENSUS")
- Major orgs with sub-orgs mimicking Census structure
- Mix of EMP and CTR designations
- Realistic attendance patterns: some full-session, some partial, some drop/reconnect
- Multiple meeting files simulating the 12-class training series
- Include some characters with NO parenthetical (to test MS trainer drop logic)

## Key Decisions
- Self-contained HTML report (no server, no Excel)
- Pandas for preprocessing
- No Jupyter — plain Python scripts
- Real data never committed; synthetic data is the canonical test fixture
- Two-layer: generic Teams parser works without org config; Census config is an overlay

## GitHub
- Owner: brockwebb
- Repo: ms-teams-attendance-reporter
