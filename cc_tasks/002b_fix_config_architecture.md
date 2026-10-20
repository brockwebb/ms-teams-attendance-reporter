# CC Task: Fix Config Architecture

## Priority: HIGH
## Status: READY
## Must complete before: 003_implement_reporter_cli

## Objective
1. Delete `config/census_org_mapping.json` — this contains internal federal org structure and should never have been in a public repo. Remove it from git history too.
2. Convert `config/acme_org_mapping.json` to a single unified YAML config file at `config/config.yaml`.
3. Update `src/enricher.py` to load YAML instead of JSON.
4. Update `src/validate_synthetic.py` to use the new config path/format.
5. Add `pyyaml` to `requirements.txt`.

## Step 1: Remove Census Config from Git History

```bash
cd /Users/brock/Documents/GitHub/ms-teams-attendance-reporter

# Remove the file and purge from history
git filter-branch --force --index-filter \
  'git rm --cached --ignore-unmatch config/census_org_mapping.json' \
  --prune-empty -- --all

# Alternative if git-filter-repo is available (preferred):
# git filter-repo --path config/census_org_mapping.json --invert-paths

# Force push to overwrite remote history
git push origin --force --all
```

If neither `filter-branch` nor `filter-repo` works cleanly, at minimum:
```bash
git rm config/census_org_mapping.json
git commit -m "Remove internal org mapping — should not be in public repo"
git push
```
The history purge is ideal but the deletion is mandatory.

## Step 2: Create Unified YAML Config

Create `config/config.yaml` with the ACNE synthetic org structure. Delete `config/acme_org_mapping.json` after.

```yaml
# =============================================================================
# MS Teams Attendance Reporter — Configuration
# =============================================================================
# Copy this file and customize for your organization.
# See README.md for documentation on each field.
#
# This example uses the "ACNE Corp" synthetic test data.
# For real use, change org_name, name_pattern, labels, and org_mapping
# to match your organization's Teams display name conventions.
# =============================================================================

# Organization name — appears in report header
org_name: "ACNE Corp"

# -----------------------------------------------------------------------------
# Name Pattern
# -----------------------------------------------------------------------------
# Regex to parse the name field from Teams attendance exports.
# Must define exactly 3 capture groups:
#   Group 1: clean display name (e.g., "Bugz Rabbit")
#   Group 2: org code (e.g., "CHASE")
#   Group 3: employee type (e.g., "EMP")
#
# Examples this pattern would match:
#   "Bugz Rabbit (ACNE/CHASE EMP)"   → name=Bugz Rabbit, org=CHASE, type=EMP
#   "Pat Cougar (ACNE/LEGAL CTR)"    → name=Pat Cougar, org=LEGAL, type=CTR
#
# Names that DON'T match are treated as external (e.g., MS trainers)
# and excluded from analysis.
#
# Set to null to run in generic mode (no org classification).
name_pattern: '^(.+?)\s*\(ACNE/(\S+)\s+(EMP|CTR)\)\s*$'

# -----------------------------------------------------------------------------
# Labels
# -----------------------------------------------------------------------------
# Customize terminology to match your organization.
# These appear in charts, tables, and report headers.
labels:
  employee: "EMP"          # Your org's term for employees (e.g., "FED" for federal)
  contractor: "CTR"        # Your org's term for contractors
  level_1: "Directorate"   # Top-level org grouping label
  level_2: "Division"      # Sub-org grouping label

# -----------------------------------------------------------------------------
# Attendance Settings
# -----------------------------------------------------------------------------
# Durations above this value (in minutes) are top-coded in histograms.
# For a 55-minute meeting, 60 is a reasonable cap.
cap_minutes: 60

# -----------------------------------------------------------------------------
# Org Hierarchy Mapping
# -----------------------------------------------------------------------------
# Maps org codes (from the name field) to a two-level hierarchy:
#   Major Org (level_1) → Sub-Orgs (level_2)
#
# direct_codes: Codes that represent the major org itself.
#               People with these codes are at the top level (no sub-org).
# sub_orgs:     Codes that roll up to this major org.
#
# Any code not found here will appear as "UNMAPPED" in the report
# so you can add it to this file.
org_mapping:
  ROCKETWORKS:
    direct_codes: [RKTW]
    sub_orgs: [ANVIL, BOOM, JETPK, PAINT, TRAPS]

  TOONOPS:
    direct_codes: [TOPS]
    sub_orgs: [CHASE, STUNT, PROPS]

  ACMELABS:
    direct_codes: [LABS]
    sub_orgs: [BRAIN, GENETICS, QUANTUM]

  ADMIN:
    direct_codes: [ADMN]
    sub_orgs: [HR, LEGAL, FINANCE]
```

Also create `config/config.example.yaml` as a copy with a comment at top: `# Example config — copy to config.yaml and customize for your org`

## Step 3: Update enricher.py

Change `load_org_config()` to:
- Accept YAML files (use `yaml.safe_load()`)
- Read `org_mapping` key (not `major_orgs`) for the hierarchy
- Read `name_pattern`, `labels`, `cap_minutes`, `org_name` from top level
- Keep backward compat: if the file is JSON (detected by extension), load it as JSON with the old structure. But YAML is the primary path.
- Add `import yaml` and handle `ImportError` with a helpful message ("pip install pyyaml")

The enricher's `enrich_participants()` should also accept `cap_minutes` from config rather than as a separate argument (but allow override via function param).

## Step 4: Update validate_synthetic.py

Change the default config path from `config/acme_org_mapping.json` to `config/config.yaml`.

## Step 5: Update requirements.txt

Add `pyyaml>=6.0` to requirements.txt.

## Step 6: Update CLAUDE.md

- Remove any reference to `census_org_mapping.json`
- Change config references from JSON to YAML
- Note that config is a single YAML file at `config/config.yaml`

## Step 7: Verify and Commit

```bash
python src/validate_synthetic.py
# Must still pass clean

git add -A
git commit -m "Unify config to single YAML file, remove internal org mapping from repo"
git push --force  # force needed if history was rewritten in step 1
```

## Acceptance Criteria
- [ ] `config/census_org_mapping.json` is gone (deleted, ideally purged from history)
- [ ] `config/acme_org_mapping.json` is gone (replaced by config.yaml)
- [ ] `config/config.yaml` exists with full ACNE org structure and inline comments
- [ ] `config/config.example.yaml` exists as a copy-ready template
- [ ] `src/enricher.py` loads YAML via pyyaml
- [ ] `pyyaml` in requirements.txt
- [ ] `python src/validate_synthetic.py` passes clean
- [ ] No Census-specific content anywhere in the repo
- [ ] Committed and pushed
