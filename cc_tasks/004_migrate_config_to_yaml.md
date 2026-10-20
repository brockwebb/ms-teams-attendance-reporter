# CC Task: Migrate Config to YAML, Remove Census Data

## Priority: HIGH  
## Status: READY
## Depends on: 003_implement_reporter_cli (COMPLETE)

## Objective
1. Delete `config/census_org_mapping.json` if it exists — it contains internal federal org structure and must not be in a public repo. Purge from git history.
2. Convert `config/acme_org_mapping.json` to a single unified YAML config at `config/config.yaml`. Delete the JSON file after.
3. Update `src/enricher.py` to load YAML (with JSON fallback for backward compat).
4. Update `src/cli.py` help text and docstring to reference YAML.
5. Update `src/validate_synthetic.py` to use the new config path.
6. Add `pyyaml` to `requirements.txt`.
7. Create `config/config.example.yaml` as a copy-ready template.

## Step 1: Remove Census Config

Check if `config/census_org_mapping.json` exists. If so, remove it and purge from git history:

```bash
cd /Users/brock/Documents/GitHub/ms-teams-attendance-reporter

# Check if it exists in current tree or git history
git log --all --full-history -- config/census_org_mapping.json

# If it exists in history, purge it:
git filter-repo --path config/census_org_mapping.json --invert-paths --force
# If git-filter-repo not available:
git filter-branch --force --index-filter \
  'git rm --cached --ignore-unmatch config/census_org_mapping.json' \
  --prune-empty -- --all

# If neither tool is available, at minimum delete it:
git rm -f config/census_org_mapping.json 2>/dev/null || true
```

Also grep the entire repo for any Census-specific content (org codes like CSVD, ADSD, OCIO, ITSMO, CSD, SEHSD, DCMD, ADRM referenced as real org structures — NOT as examples or documentation about the tool's capabilities). Remove any such content.

## Step 2: Create config/config.yaml

Convert the ACNE org mapping from JSON to YAML with extensive inline comments. The YAML should be the SINGLE source of configuration. Key changes from the JSON structure:

- Top-level key `org_mapping` (not `major_orgs`) for the hierarchy
- Add `labels` section
- Add `cap_minutes` 
- All fields at top level of one file
- Extensive comments explaining each field

```yaml
# =============================================================================
# MS Teams Attendance Reporter — Configuration
# =============================================================================
# Copy this file and customize for your organization.
# See README.md for field documentation.
#
# This example uses "ACNE Corp" synthetic test data.
# For real use: change org_name, name_pattern, labels, and org_mapping.
# =============================================================================

# Organization name — appears in report header
org_name: "ACNE Corp"

# ---------------------------------------------------------------------------
# Name Pattern
# ---------------------------------------------------------------------------
# Regex for the Teams display name field. Must have 3 capture groups:
#   (1) clean name    e.g. "Bugz Rabbit"
#   (2) org code      e.g. "CHASE"
#   (3) employee type e.g. "EMP"
#
# Matched examples:
#   "Bugz Rabbit (ACNE/CHASE EMP)"  → name=Bugz Rabbit, org=CHASE, type=EMP
#   "Pat Cougar (ACNE/LEGAL CTR)"   → name=Pat Cougar, org=LEGAL, type=CTR
#
# Unmatched names are treated as external (e.g., MS trainers) and excluded.
# Set to null to run in generic mode (no org classification).
name_pattern: '^(.+?)\s*\(ACNE/(\S+)\s+(EMP|CTR)\)\s*$'

# ---------------------------------------------------------------------------
# Labels — customize to match your org's terminology
# ---------------------------------------------------------------------------
labels:
  employee: "EMP"          # internal staff label (e.g., "FED" for federal)
  contractor: "CTR"        # contractor label
  level_1: "Directorate"   # top-level org grouping
  level_2: "Division"      # sub-org grouping

# ---------------------------------------------------------------------------
# Attendance Settings
# ---------------------------------------------------------------------------
# Durations above this value (minutes) are top-coded in histograms.
cap_minutes: 60

# ---------------------------------------------------------------------------
# Org Hierarchy
# ---------------------------------------------------------------------------
# Maps org codes (from the name field) to a two-level hierarchy.
#
# direct_codes: codes representing the major org itself
#               (people at this level have no sub-org)
# sub_orgs:     codes that roll up to this major org
#
# Unrecognized codes appear as "UNMAPPED" in the report.
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

Also create `config/config.example.yaml` — identical content but with a header comment:
```yaml
# EXAMPLE CONFIG — copy to config.yaml and customize for your organization.
# See README.md for documentation.
```

Then delete `config/acme_org_mapping.json`.

## Step 3: Update src/enricher.py

Modify `load_org_config()`:
- Accept both `.yaml`/`.yml` and `.json` files (detect by extension)
- For YAML: `import yaml` then `yaml.safe_load()`
- For YAML: read `org_mapping` key (not `major_orgs`)
- For JSON: keep existing `major_orgs` key for backward compat
- Handle `ImportError` for yaml: print helpful message "pip install pyyaml"
- Read `cap_minutes` from config if present, store in returned dict
- Read `labels` from config if present, store in returned dict
- Read `org_name` from config if present, store in returned dict

The enricher should normalize internally so downstream code doesn't care whether config was JSON or YAML. The internal structure after loading should be:
```python
{
    'org_name': str,
    'name_pattern': str,
    'labels': dict,
    'cap_minutes': float,
    'org_mapping': dict,  # normalized key name regardless of source format
    '_compiled_pattern': re.Pattern,
    '_code_to_major': dict,
    '_code_to_sub': dict,
}
```

## Step 4: Update src/cli.py

- Change `--config` help text from "Org config JSON" to "Org config file (YAML or JSON)"
- Update module docstring example from `.json` to `.yaml`
- If config has `cap_minutes`, use it as default (CLI `--cap-minutes` overrides)

## Step 5: Update src/validate_synthetic.py

- Change default config path from whatever it currently uses to `config/config.yaml`

## Step 6: Update requirements.txt

Add `pyyaml>=6.0`

## Step 7: Update CLAUDE.md

- Remove any reference to `census_org_mapping.json`
- Change config references from JSON to YAML
- Note single config file at `config/config.yaml`

## Step 8: Verify and Commit

```bash
# Validate the pipeline still works end-to-end
python src/validate_synthetic.py

# Generate a report to confirm CLI works with new config
python -m src.cli data/synthetic/ --config config/config.yaml --output /tmp/test_report.html

# Both must succeed

git add -A
git commit -m "Migrate config to YAML, remove JSON configs, purge internal org data"
git push --force  # force needed if history was rewritten
```

## Acceptance Criteria
- [ ] `config/census_org_mapping.json` is gone from current tree AND git history
- [ ] `config/acme_org_mapping.json` is gone (replaced by config.yaml)
- [ ] `config/config.yaml` exists with ACNE structure and thorough inline comments
- [ ] `config/config.example.yaml` exists as copy-ready template
- [ ] `src/enricher.py` loads YAML via pyyaml, falls back to JSON by extension
- [ ] Enricher normalizes config structure regardless of source format
- [ ] `pyyaml>=6.0` in requirements.txt
- [ ] `python src/validate_synthetic.py` passes clean
- [ ] `python -m src.cli data/synthetic/ --config config/config.yaml` produces working HTML
- [ ] No Census-specific org codes anywhere in the repo
- [ ] `cli.py` and `CLAUDE.md` updated to reference YAML
- [ ] Committed and pushed
