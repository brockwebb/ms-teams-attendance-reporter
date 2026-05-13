#!/usr/bin/env python3
"""Synthetic Teams attendance data generator.

Produces tab-delimited CSV files matching the MS Teams attendance export format:
  - Section 1: meeting metadata (tab-delimited key/value pairs; date and time
    occupy adjacent fields, mirroring how real exports split them).
  - Section 2: participant table. The header lists "First Join" and "Last Leave"
    as single columns but the data rows split each into date + time. The parser
    is responsible for merging them back; the generator must produce the
    real-world mismatch (15-column header vs. 17-column data rows).

Characters are Looney Tunes themed (ACME Corp) — ~50 named characters across
4 directorates and 14 sub-orgs, plus 3 "MS Trainers" who appear with no org
parenthetical. The trainers exist so the parser's drop-non-org logic has
something to drop.

Run:
    python src/generate_synthetic.py [--out-dir data/synthetic] [--seed 42]
"""

import argparse
import random
from datetime import datetime, timedelta
from pathlib import Path


# (display_name, "MAJOR/SUB" or "MAJOR/<direct_code>", "EMP"|"CTR")
CHARACTERS = [
    # ROCKETWORKS
    ("Wile E. Coyote",        "ROCKETWORKS/ANVIL",   "EMP"),
    ("Road Runner",           "ROCKETWORKS/ANVIL",   "EMP"),
    ("Yosemite Sam",          "ROCKETWORKS/ANVIL",   "EMP"),
    ("Marvin Martian",        "ROCKETWORKS/ANVIL",   "CTR"),
    ("Sylvester Pussycat",    "ROCKETWORKS/BOOM",    "EMP"),
    ("Tweety Bird",           "ROCKETWORKS/BOOM",    "EMP"),
    ("Foghorn Leghorn",       "ROCKETWORKS/BOOM",    "CTR"),
    ("Speedy Gonzales",       "ROCKETWORKS/JETPK",   "EMP"),
    ("Slowpoke Rodriguez",    "ROCKETWORKS/JETPK",   "EMP"),
    ("Gonzales Jr",           "ROCKETWORKS/JETPK",   "CTR"),
    ("Pepe Le Pew",           "ROCKETWORKS/PAINT",   "EMP"),
    ("Penelope Pussycat",     "ROCKETWORKS/PAINT",   "EMP"),
    ("Elmer Fudd",            "ROCKETWORKS/TRAPS",   "EMP"),
    ("Tasmanian Devil",       "ROCKETWORKS/TRAPS",   "EMP"),
    ("Witch Hazel",           "ROCKETWORKS/TRAPS",   "CTR"),
    ("Granny",                "ROCKETWORKS/RKTW",    "EMP"),  # direct code

    # TOONOPS
    ("Bugs Bunny",            "TOONOPS/CHASE",       "EMP"),
    ("Daffy Duck",            "TOONOPS/CHASE",       "EMP"),
    ("Porky Pig",             "TOONOPS/CHASE",       "EMP"),
    ("Lola Bunny",            "TOONOPS/CHASE",       "CTR"),
    ("Michigan J. Frog",      "TOONOPS/STUNT",       "EMP"),
    ("Gossamer",              "TOONOPS/STUNT",       "EMP"),
    ("Hugo the Abominable",   "TOONOPS/STUNT",       "CTR"),
    ("Wile E. Coyote Jr",     "TOONOPS/PROPS",       "EMP"),
    ("Barnyard Dawg",         "TOONOPS/PROPS",       "EMP"),
    ("Henery Hawk",           "TOONOPS/PROPS",       "CTR"),
    ("Bugs Bunny Sr",         "TOONOPS/TOPS",        "EMP"),  # direct code

    # ACMELABS
    ("Brain",                 "ACMELABS/BRAIN",      "EMP"),
    ("Pinky",                 "ACMELABS/BRAIN",      "EMP"),
    ("Snowball",              "ACMELABS/BRAIN",      "CTR"),
    ("Chicken Hawk",          "ACMELABS/GENETICS",   "EMP"),
    ("Egghead Jr",            "ACMELABS/GENETICS",   "EMP"),
    ("Dr. I.Q. Hi",           "ACMELABS/QUANTUM",    "EMP"),
    ("Instant Martian",       "ACMELABS/QUANTUM",    "CTR"),
    ("Beaker",                "ACMELABS/LABS",       "EMP"),  # direct code

    # ADMIN
    ("Granny Smith",          "ADMIN/HR",            "EMP"),
    ("Miss Prissy",           "ADMIN/HR",            "EMP"),
    ("Lawyer Falcon",         "ADMIN/LEGAL",         "EMP"),
    ("Pete Puma",             "ADMIN/LEGAL",         "CTR"),
    ("Counting Cat",          "ADMIN/FINANCE",       "EMP"),
    ("Penny Penguin",         "ADMIN/FINANCE",       "EMP"),
    ("Cecil Turtle",          "ADMIN/ADMN",          "EMP"),  # direct code

    # Padding to 50 named characters
    ("Buster Bunny",          "TOONOPS/CHASE",       "EMP"),
    ("Babs Bunny",            "TOONOPS/CHASE",       "EMP"),
    ("Plucky Duck",           "TOONOPS/CHASE",       "CTR"),
    ("Hampton Pig",           "TOONOPS/PROPS",       "EMP"),
    ("Fifi La Fume",          "ROCKETWORKS/PAINT",   "CTR"),
    ("Calamity Coyote",       "ROCKETWORKS/ANVIL",   "EMP"),
    ("Little Beeper",         "ROCKETWORKS/JETPK",   "CTR"),
    ("Furrball",              "ACMELABS/BRAIN",      "EMP"),
]
assert len(CHARACTERS) == 50, f"expected 50 named characters, got {len(CHARACTERS)}"

# Trainers appear in real exports with no org parenthetical. Must be DROPPED.
MS_TRAINERS = [
    "Microsoft Trainer",
    "Copilot Support Team",
    "MS Learning Facilitator",
]

CHAMPIONS = {"Bugs Bunny", "Wile E. Coyote", "Brain", "Granny", "Cecil Turtle"}
RELUCTANT = {"Yosemite Sam", "Tasmanian Devil", "Gossamer", "Pete Puma"}

HEADER_COLUMNS = [
    "Name",
    "First Join",
    "Last Leave",
    "In-Meeting Duration",
    "Email",
    "Participant ID (UPN)",
    "Role",
    "Engagement: Reaction-Applause",
    "Engagement: Reaction-Laugh",
    "Engagement: Reaction-Like",
    "Engagement: Reaction-Love",
    "Engagement: Reaction-Surprised",
    "Engagement: Camera On",
    "Engagement: Raise Hands",
    "Engagement: Unmute",
]

MEETINGS = [
    {
        "filename": "copilot_prompting_20260513.csv",
        "title": "Prompting That Works",
        "start": datetime(2026, 5, 13, 13, 0),
        "duration_min": 55,
        "target_attendees": 35,
    },
    {
        "filename": "copilot_ama_20260515.csv",
        "title": "Ask Me Anything",
        "start": datetime(2026, 5, 15, 13, 0),
        "duration_min": 55,
        "target_attendees": 25,
    },
    {
        "filename": "copilot_agents_20260518.csv",
        "title": "Prompt or Agents: Intro to Agents",
        "start": datetime(2026, 5, 18, 13, 0),
        "duration_min": 55,
        "target_attendees": 40,
    },
    {
        "filename": "copilot_word_outlook_20260520.csv",
        "title": "Write Faster with Copilot",
        "start": datetime(2026, 5, 20, 13, 0),
        "duration_min": 55,
        "target_attendees": 30,
    },
]


def format_name(name: str, org_path: str, status: str) -> str:
    sub = org_path.split("/")[1] if "/" in org_path else org_path
    return f"{name} (ACME/{sub} {status})"


def fmt_date(dt: datetime) -> str:
    return f"{dt.month}/{dt.day}/{dt.year}"


def fmt_time(dt: datetime) -> str:
    # Real Teams exports use no-padding hour with AM/PM
    return dt.strftime("%I:%M:%S %p").lstrip("0")


def fmt_duration(seconds: float) -> str:
    total = max(0, int(seconds))
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    parts = []
    if h:
        parts.append(f"{h}h")
    if m or h:
        parts.append(f"{m}m")
    parts.append(f"{s}s")
    return " ".join(parts)


def email_for(name: str) -> str:
    slug = name.strip().lower().replace(".", "").replace("  ", " ").replace(" ", ".")
    return f"{slug}@acme.test"


def engagement_row(rng: random.Random) -> list[int]:
    return [
        rng.choices([0, 1], weights=[95, 5])[0],          # applause
        rng.choices([0, 1], weights=[92, 8])[0],          # laugh
        rng.choices([0, 1, 2], weights=[80, 17, 3])[0],   # like
        rng.choices([0, 1], weights=[97, 3])[0],          # love
        rng.choices([0, 1], weights=[96, 4])[0],          # surprised
        rng.choices([0, 1], weights=[55, 45])[0],         # camera on
        rng.choices([0, 1], weights=[90, 10])[0],         # raise hands
        rng.choices([0, 1], weights=[75, 25])[0],         # unmute
    ]


def generate_sessions(meeting_start: datetime, meeting_dur_min: int, rng: random.Random):
    """Return one or more (join_dt, leave_dt) windows for a single participant.

    Pattern weights mirror the spec: ~60% full, ~20% partial, ~10% late,
    ~5% drop/reconnect (yields TWO rows for one person), ~5% cameo (< 5 min).
    """
    end = meeting_start + timedelta(minutes=meeting_dur_min)
    pattern = rng.choices(
        ["full", "partial", "late", "drop_reconnect", "cameo"],
        weights=[60, 20, 10, 5, 5],
    )[0]

    if pattern == "full":
        join = meeting_start + timedelta(seconds=rng.randint(-60, 120))
        leave = end - timedelta(seconds=rng.randint(0, 300))
        return [(join, leave)]

    if pattern == "partial":
        join = meeting_start + timedelta(seconds=rng.randint(0, 600))
        stay = timedelta(minutes=rng.randint(20, 40))
        return [(join, min(end, join + stay))]

    if pattern == "late":
        join = meeting_start + timedelta(minutes=rng.randint(10, 25))
        leave = end - timedelta(seconds=rng.randint(0, 180))
        return [(join, leave)]

    if pattern == "drop_reconnect":
        join1 = meeting_start + timedelta(seconds=rng.randint(0, 300))
        leave1 = join1 + timedelta(minutes=rng.randint(10, 25))
        gap = timedelta(minutes=rng.randint(2, 6))
        join2 = leave1 + gap
        leave2 = end - timedelta(seconds=rng.randint(0, 180))
        if join2 >= leave2:
            return [(join1, leave1)]
        return [(join1, leave1), (join2, leave2)]

    join = meeting_start + timedelta(minutes=rng.randint(0, 40))
    leave = join + timedelta(seconds=rng.randint(30, 240))
    return [(join, min(end, leave))]


def pick_attendees(meeting: dict, rng: random.Random):
    """Choose which characters attend this meeting.

    Champions always attend. Reluctants drop out 75% of the time (so they
    typically land in only one of the four meetings). Remaining slots are
    filled from a shuffled pool.
    """
    pool = list(CHARACTERS)
    rng.shuffle(pool)

    champions = [c for c in pool if c[0] in CHAMPIONS]
    pool = [c for c in pool if c[0] not in CHAMPIONS]

    target = meeting["target_attendees"]
    selected = list(champions)
    for char in pool:
        if len(selected) >= target:
            break
        if char[0] in RELUCTANT and rng.random() > 0.25:
            continue
        selected.append(char)
    return selected


def generate_meeting(meeting: dict, rng: random.Random) -> str:
    attendees = pick_attendees(meeting, rng)
    participant_rows: list[list[str]] = []
    total_minutes = 0.0
    unique_attended = 0

    # 1-2 MS trainers per file (no org parenthetical → parser should drop)
    trainer_count = rng.choice([1, 2])
    for trainer in rng.sample(MS_TRAINERS, trainer_count):
        join = meeting["start"] - timedelta(minutes=rng.randint(2, 5))
        leave = meeting["start"] + timedelta(minutes=meeting["duration_min"] + rng.randint(1, 5))
        participant_rows.append([
            trainer,
            fmt_date(join), fmt_time(join),
            fmt_date(leave), fmt_time(leave),
            fmt_duration((leave - join).total_seconds()),
            email_for(trainer),
            email_for(trainer),
            "Presenter",
            *[str(v) for v in engagement_row(rng)],
        ])
        total_minutes += (leave - join).total_seconds() / 60.0
        unique_attended += 1

    for char_name, org_path, status in attendees:
        sessions = generate_sessions(meeting["start"], meeting["duration_min"], rng)
        display_name = format_name(char_name, org_path, status)
        role = "Organizer" if char_name == "Bugs Bunny" else "Attendee"
        for join, leave in sessions:
            participant_rows.append([
                display_name,
                fmt_date(join), fmt_time(join),
                fmt_date(leave), fmt_time(leave),
                fmt_duration((leave - join).total_seconds()),
                email_for(char_name),
                email_for(char_name),
                role,
                *[str(v) for v in engagement_row(rng)],
            ])
            total_minutes += (leave - join).total_seconds() / 60.0
        unique_attended += 1

    avg_seconds = int((total_minutes / max(1, len(participant_rows))) * 60)
    end_dt = meeting["start"] + timedelta(minutes=meeting["duration_min"])

    metadata_lines = [
        f"Meeting title\t{meeting['title']}",
        f"Attended participants\t{unique_attended}",
        f"Start time\t{fmt_date(meeting['start'])}\t{fmt_time(meeting['start'])}",
        f"End time\t{fmt_date(end_dt)}\t{fmt_time(end_dt)}",
        f"Meeting duration\t{fmt_duration(meeting['duration_min'] * 60)}",
        f"Average attendance time\t{fmt_duration(avg_seconds)}",
    ]

    lines = list(metadata_lines)
    lines.append("")
    lines.append("2. Participants")
    lines.append("\t".join(HEADER_COLUMNS))
    for row in participant_rows:
        lines.append("\t".join(row))

    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser(description="Generate synthetic Teams attendance CSVs")
    ap.add_argument(
        "--out-dir",
        default="data/synthetic",
        help="Output directory for generated CSVs (default: data/synthetic)",
    )
    ap.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for reproducibility (default: 42)",
    )
    args = ap.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = random.Random(args.seed)

    for meeting in MEETINGS:
        text = generate_meeting(meeting, rng)
        path = out_dir / meeting["filename"]
        path.write_text(text, encoding="utf-8")
        print(f"  wrote {path} ({len(text.splitlines())} lines)")


if __name__ == "__main__":
    main()
