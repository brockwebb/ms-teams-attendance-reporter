# CC Task: Temu-ify the Character Names

## Priority: LOW (but fun)
## Status: READY
## Depends on: 001_initial_setup (COMPLETE)
## Must complete before: 002_implement_parser_enricher

## Objective
Replace all Looney Tunes character names in the synthetic data generator with "legally distinct" parody versions. Regenerate all 4 synthetic CSV files. This is a cosmetic change only — org assignments, attendance patterns, and file structure remain identical.

## Character Mapping

Replace the CHARACTERS list in `src/generate_synthetic.py` with these names. Keep all org/sub-org/EMP|CTR assignments exactly as they are. Same order, same count (50).

```
# ROCKETWORKS
Wile E. Coyote        → Wily D. Coydog
Road Runner           → Street Sprinter
Yosemite Sam          → Yellowstone Stan
Marvin Martian        → Melvin Venusian
Sylvester Pussycat    → Salvador Housecat
Tweety Bird           → Tweetie Birb
Foghorn Leghorn       → Foghat Rooster
Speedy Gonzales       → Zippy Gonzalez
Slowpoke Rodriguez    → Pokeyboy Rodrigo
Gonzales Jr           → Gonzalez Junior
Pepe Le Pew           → Pierre Le Phew
Penelope Pussycat     → Priscilla Kittycat
Elmer Fudd            → Elroy Fuzz
Tasmanian Devil       → Taswegian Demon
Witch Hazel           → Witch Hickory
Granny                → Nana

# TOONOPS
Bugs Bunny            → Bugz Rabbit
Daffy Duck            → Dappy Goose
Porky Pig             → Bork E. Hog
Lola Bunny            → Lulu Hare
Michigan J. Frog      → Wisconsin K. Toad
Gossamer              → Fuzzmonster
Hugo the Abominable   → Yugo the Tolerable
Wile E. Coyote Jr     → Wily D. Coydog Jr
Barnyard Dawg         → Farmstead Mutt
Henery Hawk           → Henry Falcon
Bugs Bunny Sr         → Bugz Rabbit Sr

# ACMELABS
Brain                 → Cortex
Pinky                 → Blinky
Snowball              → Slushball
Chicken Hawk          → Turkey Vulture
Egghead Jr            → Noggin Jr
Dr. I.Q. Hi           → Dr. E.Q. High
Instant Martian       → Minute Venusian
Beaker                → Flask

# ADMIN
Granny Smith          → Nana McIntosh
Miss Prissy           → Ms. Fussy
Lawyer Falcon         → Attorney Hawk
Pete Puma             → Pat Cougar
Counting Cat          → Tally Tabby
Penny Penguin         → Nickel Puffin
Cecil Turtle          → Cedric Tortoise

# Padding (Tiny Toons → Teeny Cartoons)
Buster Bunny          → Blaster Rabbit
Babs Bunny            → Babs Hare
Plucky Duck           → Lucky Goose
Hampton Pig           → Hamilton Boar
Fifi La Fume          → Gigi La Stink
Calamity Coyote       → Catastrophe Coydog
Little Beeper         → Tiny Honker
Furrball              → Fuzzball
```

Also update these constants:
- CHAMPIONS: `{"Bugz Rabbit", "Wily D. Coydog", "Cortex", "Nana", "Cedric Tortoise"}`
- RELUCTANT: `{"Yellowstone Stan", "Taswegian Demon", "Fuzzmonster", "Pat Cougar"}`
- MS_TRAINERS: keep as-is (they're already generic: "Microsoft Trainer", "Copilot Support Team", "MS Learning Facilitator")

Also update email addresses to match new names (e.g., `bugz.rabbit@acne.test`).

Change the org name in the test domain from `acme.test` to `acne.test`.

## Steps

1. Update the CHARACTERS list in `src/generate_synthetic.py` with the new names
2. Update CHAMPIONS and RELUCTANT sets
3. Update email generation logic to use `@acne.test` domain
4. Run `python src/generate_synthetic.py` to regenerate all 4 CSVs in `data/synthetic/`
5. Verify output: spot-check that names render correctly, org codes unchanged, file format intact
6. Update `config/acme_org_mapping.json`: change `"org_name": "ACME"` → `"org_name": "ACNE"` and update `name_pattern` regex from `ACME` to `ACNE`
7. Update `CLAUDE.md` to reflect the name change (ACME → ACNE, note the parody names)
8. Commit: `git add -A && git commit -m "Temu-ify character names: legally distinct parody versions"`
9. Push: `git push`

## Acceptance Criteria
- [ ] All 50 characters renamed, no Looney Tunes originals remain
- [ ] Email addresses use `@acne.test`
- [ ] Name parentheticals use `ACNE/` prefix (e.g., `Bugz Rabbit (ACNE/CHASE EMP)`)
- [ ] 4 synthetic CSVs regenerated with new names
- [ ] Config updated with ACNE org name and pattern
- [ ] File format (two-section, column mismatch, metadata) unchanged
- [ ] Committed and pushed
