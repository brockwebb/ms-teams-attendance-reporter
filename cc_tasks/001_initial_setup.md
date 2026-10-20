# CC Task: Initial Project Setup

## Priority: HIGH
## Status: READY

## Objective
Set up the ms-teams-attendance-reporter project: initialize git repo, create the synthetic dataset generator, generate canonical test data, and scaffold the core pipeline modules.

## Steps

### 1. Initialize Git Repo
```bash
cd /Users/brock/Documents/GitHub/ms-teams-attendance-reporter
git init
git add .gitignore CLAUDE.md handoffs/README.md cc_tasks/README.md data/raw/.gitkeep data/processed/.gitkeep
git commit -m "Initial project scaffold"
```

### 2. Create Org Config for Synthetic Data
Create `config/acme_org_mapping.json` — the Looney Tunes version of org_mapping.json.

ACME Corp org structure (mirrors Census hierarchy):
```json
{
  "_comment": "Synthetic org mapping. ACME mirrors Census structure for testing.",
  "org_name": "ACME",
  "org_labels": {
    "level_1": "Agency",
    "level_2": "Directorate",
    "level_3": "Division",
    "employee_type": "Status"
  },
  "name_pattern": "^(.+?)\\s*\\(ACME/(\\S+)\\s+(EMP|CTR)\\)\\s*$",
  "major_orgs": {
    "ROCKETWORKS": {
      "direct_codes": ["RKTW"],
      "sub_orgs": ["ANVIL", "BOOM", "JETPK", "PAINT", "TRAPS"]
    },
    "TOONOPS": {
      "direct_codes": ["TOPS"],
      "sub_orgs": ["CHASE", "STUNT", "PROPS"]
    },
    "ACMELABS": {
      "direct_codes": ["LABS"],
      "sub_orgs": ["BRAIN", "GENETICS", "QUANTUM"]
    },
    "ADMIN": {
      "direct_codes": ["ADMN"],
      "sub_orgs": ["HR", "LEGAL", "FINANCE"]
    }
  }
}
```

Also create `config/census_org_mapping.json` using the existing mapping from `files/org_mapping.json` but restructured to include the new config fields (org_name, org_labels, name_pattern).

### 3. Create Synthetic Data Generator
Create `src/generate_synthetic.py`

This script generates realistic Teams attendance CSV files in the exact format described in CLAUDE.md.

**50 Characters Pool** — Looney Tunes themed names with org assignments:

ROCKETWORKS/ANVIL: Wile E. Coyote (EMP), Road Runner (EMP), Yosemite Sam (EMP), Marvin Martian (CTR)
ROCKETWORKS/BOOM: Sylvester Pussycat (EMP), Tweety Bird (EMP), Foghorn Leghorn (CTR)
ROCKETWORKS/JETPK: Speedy Gonzales (EMP), Slowpoke Rodriguez (EMP), Gonzales Jr (CTR)
ROCKETWORKS/PAINT: Pepe Le Pew (EMP), Penelope Pussycat (EMP)
ROCKETWORKS/TRAPS: Elmer Fudd (EMP), Tasmanian Devil (EMP), Witch Hazel (CTR)
ROCKETWORKS (direct/RKTW): Granny (EMP)

TOONOPS/CHASE: Bugs Bunny (EMP), Daffy Duck (EMP), Porky Pig (EMP), Lola Bunny (CTR)
TOONOPS/STUNT: Michigan J. Frog (EMP), Gossamer (EMP), Hugo the Abominable (CTR)
TOONOPS/PROPS: Wile E. Coyote Jr (EMP), Barnyard Dawg (EMP), Henery Hawk (CTR)
TOONOPS (direct/TOPS): Bugs Bunny Sr (EMP)

ACMELABS/BRAIN: Brain (EMP), Pinky (EMP), Snowball (CTR)
ACMELABS/GENETICS: Chicken Hawk (EMP), Egghead Jr (EMP)
ACMELABS/QUANTUM: Dr. I.Q. Hi (EMP), Instant Martian (CTR)
ACMELABS (direct/LABS): Beaker (EMP)

ADMIN/HR: Granny Smith (EMP), Miss Prissy (EMP)
ADMIN/LEGAL: Lawyer Falcon (EMP), Pete Puma (CTR)
ADMIN/FINANCE: Counting Cat (EMP), Penny Penguin (EMP)
ADMIN (direct/ADMN): Cecil Turtle (EMP)

MS Trainers (no parenthetical, should be DROPPED): 
- "Microsoft Trainer"
- "Copilot Support Team" 
- "MS Learning Facilitator"

Total: ~50 named characters + 3 trainers

**Generate 4 meeting files** (subset of the 12-class series):
1. `copilot_prompting_20260513.csv` — "Prompting That Works" — ~35 attendees (good turnout)
2. `copilot_ama_20260515.csv` — "Ask Me Anything" — ~25 attendees (lighter)  
3. `copilot_agents_20260518.csv` — "Prompt or Agents: Intro to Agents" — ~40 attendees (high interest)
4. `copilot_word_outlook_20260520.csv` — "Write Faster with Copilot" — ~30 attendees

Each file must:
- Have the full Section 1 metadata header (meeting title, participant count, start/end times, duration, avg attendance)
- Have the Section 2 participant table with ALL columns including engagement metrics
- Use tab-delimited format
- Split date and time into separate columns in data rows (matching real Teams export)
- Include 1-2 MS trainers per file
- Have realistic attendance patterns:
  - ~60% attend full session (50-55 min for a 55-min meeting)
  - ~20% attend partial (20-40 min)
  - ~10% join late
  - ~5% have drop/reconnect (multiple rows for same person)
  - ~5% very short attendance (< 5 min, just popped in)
- Randomize engagement metrics (most zeros, occasional reactions)
- Vary which characters attend which sessions (not everyone attends everything)
- Some characters should attend ALL sessions (the champions)
- Some characters attend only 1 (the reluctant ones)

Output files to `data/synthetic/`

### 4. Scaffold Core Pipeline Modules
Create empty/minimal module files:
- `src/__init__.py`
- `src/parser.py` — stub with docstring: "Parse Teams attendance CSV (two-section format)"
- `src/enricher.py` — stub with docstring: "Enrich parsed data with org mapping"  
- `src/reporter.py` — stub with docstring: "Generate self-contained HTML dashboard"
- `src/cli.py` — stub with docstring: "CLI entry point"

Do NOT port the full logic from `files/preprocess.py` yet — just create the module structure. The existing code in `files/` is reference material.

### 5. Create requirements.txt
```
pandas>=2.0
```
That's it. Keep it minimal.

### 6. Create initial README.md
Brief README at project root:
- One-liner description
- "Work in progress" notice
- Basic usage placeholder
- License: MIT

### 7. Git Commit
```bash
git add -A
git commit -m "Add synthetic data generator, org configs, project scaffold"
```

### 8. Create GitHub Repo and Push
```bash
# Create the repo on GitHub (public)
gh repo create ms-teams-attendance-reporter --public --source=. --push
```
If `gh` CLI isn't available, note that the repo needs to be created manually at github.com/brockwebb/ms-teams-attendance-reporter and then:
```bash
git remote add origin https://github.com/brockwebb/ms-teams-attendance-reporter.git
git branch -M main
git push -u origin main
```

## Acceptance Criteria
- [ ] Git repo initialized with clean history
- [ ] Synthetic data generator produces 4 valid CSV files matching real Teams format
- [ ] Generated CSVs have the two-section layout (metadata + participant table)
- [ ] Date/time column split matches real export (header says "First Join" but data has date and time in separate columns)
- [ ] 50 Looney Tunes characters with correct org/status assignments
- [ ] 3 MS trainers (no parenthetical) present in files
- [ ] Org configs created for both ACME (synthetic) and Census (real)
- [ ] Module stubs created in src/
- [ ] All committed and pushed to GitHub

## Notes
- The files/ directory contains working code from a prior conversation thread. It's gitignored but available for reference.
- The synthetic data is the canonical test fixture — all pipeline development tests against it.
- Census org_mapping should preserve the structure from files/org_mapping.json but add the new config fields.
