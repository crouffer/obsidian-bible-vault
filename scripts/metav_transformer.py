#!/usr/bin/env python3
"""
MetaV → Obsidian Bible Vault Transformer
=========================================
Converts the MetaV biblical metadata database into Obsidian-compatible
Markdown notes for people, places, and books.

Sources:
  MetaV database: github.com/theonize/KJV-bible-database-with-metadata-MetaV-
  License: Creative Commons Attribution Share-Alike 3.0

Usage:
  python metav_transformer.py --download           # fetch CSVs + generate vault
  python metav_transformer.py                      # use existing CSVs
  python metav_transformer.py --output ./my-vault  # custom output dir
"""

import sqlite3
import csv
import os
import re
import json
import argparse
import urllib.request
from pathlib import Path
from collections import defaultdict

# ── Configuration ──────────────────────────────────────────────────────────────

GITHUB_BASE = (
    "https://raw.githubusercontent.com/"
    "theonize/KJV-bible-database-with-metadata-MetaV-/master/CSV"
)

# Only the tables we actually need — skipping CrossRefIndex/TopicIndex (large, not needed yet)
CSV_FILES = [
    "Books.csv",
    "BookAliases.csv",
    "Writers.csv",
    "People.csv",
    "PeopleAliases.csv",
    "PeopleRelationships.csv",
    "PeopleGroups.csv",
    "Places.csv",
    "PlaceAliases.csv",
    "Verses.csv",
    "MainIndex.csv",
]

# PeopleRelationships.RelType values (lowercase in actual data)
REL_FATHER   = "father"           # Primary is the father of RelatedTo
REL_CHILD    = "child"            # Primary is the child of RelatedTo
REL_SPOUSE   = "spouseorconcubine"
REL_SIBLING  = "sibling"

# OT = BookID 1–39, NT = BookID 40–66
def get_testament(book_id):
    if book_id is None:
        return "unknown"
    return "OT" if int(book_id) <= 39 else "NT"

# Parse "1358 BC" → -1358, "30 AD" / "30" → 30
def parse_year(raw):
    if not raw or not raw.strip():
        return None
    raw = raw.strip()
    m = re.match(r"(\d+)\s*(BC|AD)?", raw, re.IGNORECASE)
    if not m:
        return None
    year = int(m.group(1))
    suffix = (m.group(2) or "AD").upper()
    return -year if suffix == "BC" else year

# Map birth year → era label
ERAS = [
    (-99999, -2300, "antediluvian"),
    (-2300,  -2000, "post-flood"),
    (-2000,  -1500, "patriarchal"),
    (-1500,  -1200, "exodus"),
    (-1200,  -1000, "judges"),
    (-1000,  -586,  "monarchy"),
    (-586,   -539,  "exile"),
    (-539,   -400,  "post-exile"),
    (-400,   -4,    "second-temple"),
    (-4,      100,  "new-testament"),
]

def get_era(birth_year_raw):
    year = parse_year(birth_year_raw)
    if year is None:
        return "unknown"
    for start, end, label in ERAS:
        if start <= year < end:
            return label
    return "unknown"


# ── Download ───────────────────────────────────────────────────────────────────

def download_csvs(csv_dir: Path):
    csv_dir.mkdir(parents=True, exist_ok=True)
    print("Downloading MetaV CSVs from GitHub...")
    for filename in CSV_FILES:
        dest = csv_dir / filename
        if dest.exists():
            print(f"  ✓ {filename} (cached)")
            continue
        url = f"{GITHUB_BASE}/{filename}"
        print(f"  ↓ {filename}")
        try:
            urllib.request.urlretrieve(url, dest)
        except Exception as e:
            print(f"  ✗ Failed {filename}: {e}")


# ── Database ───────────────────────────────────────────────────────────────────

def load_db(db_path: Path, csv_dir: Path) -> sqlite3.Connection:
    """Load all CSVs into SQLite. Re-creates tables each run."""
    print("Loading CSVs into SQLite...")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    for csv_file in sorted(csv_dir.glob("*.csv")):
        table_name = csv_file.stem
        if table_name + ".csv" not in CSV_FILES:
            continue
        with open(csv_file, encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            if not reader.fieldnames:
                continue
            # Quote column names to handle reserved words like "Primary"
            cols = ", ".join(f'"{c}" TEXT' for c in reader.fieldnames)
            conn.execute(f'DROP TABLE IF EXISTS "{table_name}"')
            conn.execute(f'CREATE TABLE "{table_name}" ({cols})')
            rows = list(reader)
            if rows:
                placeholders = ", ".join("?" * len(reader.fieldnames))
                conn.executemany(
                    f'INSERT INTO "{table_name}" VALUES ({placeholders})',
                    [list(r.values()) for r in rows],
                )
        print(f"  ✓ {table_name} ({len(rows):,} rows)")

    # Indexes that make the big MainIndex queries fast
    print("  Building indexes...")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_main_person ON MainIndex(PersonID)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_main_place  ON MainIndex(PlaceID)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_main_verse  ON MainIndex(VerseID)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_verses_id   ON Verses(VerseID)")
    conn.commit()
    return conn


# ── Disambiguation ─────────────────────────────────────────────────────────────

def build_name_maps(conn):
    """
    Returns:
      person_map  : PersonID (str) → display name
      place_map   : PlaceID  (str) → display name

    Duplicates get a numeric suffix and land in the validation report.
    """
    people = conn.execute('SELECT PersonID, Name FROM People').fetchall()
    name_counts = defaultdict(list)
    for p in people:
        name_counts[p["Name"]].append(p["PersonID"])

    person_map = {}
    for p in people:
        pid, name = p["PersonID"], p["Name"]
        if len(name_counts[name]) == 1:
            person_map[pid] = name
        else:
            person_map[pid] = f"{name} ({pid})"   # placeholder — review queue

    places = conn.execute('SELECT PlaceID, PlaceName FROM Places').fetchall()
    place_counts = defaultdict(list)
    for pl in places:
        place_counts[pl["PlaceName"]].append(pl["PlaceID"])

    place_map = {}
    for pl in places:
        plid, name = pl["PlaceID"], pl["PlaceName"]
        if len(place_counts[name]) == 1:
            place_map[plid] = name
        else:
            place_map[plid] = f"{name} ({plid})"

    return person_map, place_map


# ── Helpers ────────────────────────────────────────────────────────────────────

def safe_filename(name: str) -> str:
    return re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", name).strip()

# YAML 1.1 plain scalars that silently coerce to non-strings unless quoted.
# e.g. a person/place literally named "On" parses as the boolean True.
_YAML_BOOL = {"y", "yes", "n", "no", "true", "false", "on", "off"}
_YAML_NULL = {"null", "none", "~"}
_YAML_NUM_RE = re.compile(r"^[-+]?(\d+\.?\d*|\.\d+)([eE][-+]?\d+)?$")

def yaml_str(val):
    if not val:
        return "null"
    s = str(val)
    low = s.strip().lower()
    needs_quote = (
        any(c in s for c in ':#{}&*!|>\'"[]') or   # YAML indicator characters
        s != s.strip() or                          # leading/trailing whitespace
        low in _YAML_BOOL or                       # on/off/yes/no/true/false
        low in _YAML_NULL or                       # null/none/~
        bool(_YAML_NUM_RE.match(s))                # bare numbers
    )
    if needs_quote:
        return json.dumps(s)
    return s

def yaml_link(display_name):
    if not display_name:
        return "null"
    return f'"[[{display_name}]]"'

def yaml_link_list(names):
    clean = sorted({n for n in names if n})
    if not clean:
        return "[]"
    lines = "\n".join(f'  - "[[{n}]]"' for n in clean)
    return f"\n{lines}"

def verses_by_book(conn, id_field: str, entity_id: str):
    """
    Returns an OrderedDict: book_name → [(chapter, verse_num, verse_text), ...]
    Queries MainIndex for word-level person/place tags, deduplicates to verse level.
    """
    rows = conn.execute(f'''
        SELECT DISTINCT b.BookName, CAST(b.BookID AS INTEGER) AS bk,
               CAST(v.Chapter AS INTEGER) AS ch,
               CAST(v.VerseNum AS INTEGER) AS vn,
               v.VerseText
        FROM   MainIndex mi
        JOIN   Verses    v  ON mi.VerseID  = v.VerseID
        JOIN   Books     b  ON v.BookID    = b.BookID
        WHERE  mi."{id_field}" = ?
        ORDER BY bk, ch, vn
    ''', (entity_id,)).fetchall()
    by_book = defaultdict(list)
    for r in rows:
        by_book[r["BookName"]].append((r["ch"], r["vn"], r["VerseText"]))
    return by_book


# ── Person notes ───────────────────────────────────────────────────────────────

def build_person_notes(conn, people_dir: Path, person_map: dict):
    people_dir.mkdir(parents=True, exist_ok=True)
    people = conn.execute('SELECT * FROM People').fetchall()

    for person in people:
        pid        = person["PersonID"]
        disp_name  = person_map.get(pid, person["Name"])

        # ── Aliases
        aliases = [
            r["Alias"] for r in
            conn.execute('SELECT Alias FROM PeopleAliases WHERE PersonID = ?', (pid,))
            if r["Alias"] != person["Name"]   # skip if identical to canonical name
        ]

        # ── Relationships
        # RelType="father"  → Primary is father of RelatedTo
        # RelType="child"   → Primary is child of RelatedTo  (RelatedTo is the parent)
        rels_from = conn.execute(
            'SELECT RelatedTo, LOWER(RelType) AS rt FROM PeopleRelationships WHERE "Primary" = ?',
            (pid,)
        ).fetchall()
        rels_to = conn.execute(
            'SELECT "Primary" AS src, LOWER(RelType) AS rt FROM PeopleRelationships WHERE RelatedTo = ?',
            (pid,)
        ).fetchall()

        children = [
            person_map.get(r["RelatedTo"])
            for r in rels_from if r["rt"] == REL_FATHER
        ]
        # parent of this person: either via child→RelatedTo, or another row where RelType=father→this person
        parents_from_child = [
            person_map.get(r["RelatedTo"])
            for r in rels_from if r["rt"] == REL_CHILD
        ]
        parents_from_father = [
            person_map.get(r["src"])
            for r in rels_to if r["rt"] == REL_FATHER
        ]
        all_parents = list({p for p in parents_from_child + parents_from_father if p})

        spouses = [
            person_map.get(r["RelatedTo"])
            for r in rels_from if r["rt"] == REL_SPOUSE
        ]
        siblings = [
            person_map.get(r["RelatedTo"])
            for r in rels_from if r["rt"] == REL_SIBLING
        ]

        # Crude gender-based parent split — MetaV doesn't separate father/mother
        # Mark both as parents; human enrichment separates them
        father_val = all_parents[0] if len(all_parents) >= 1 else None
        mother_val = all_parents[1] if len(all_parents) >= 2 else None

        # ── Groups
        groups = [
            r["GroupName"] for r in
            conn.execute('SELECT GroupName FROM PeopleGroups WHERE PersonID = ?', (pid,))
        ]

        # ── Verses
        by_book = verses_by_book(conn, "PersonID", pid)
        first_app = None
        first_book_id = None
        if by_book:
            first_book = next(iter(by_book))
            ch, vn, _ = by_book[first_book][0]
            first_app = f"{first_book} {ch}:{vn}"
            book_row = conn.execute(
                'SELECT BookID FROM Books WHERE BookName = ?', (first_book,)
            ).fetchone()
            if book_row:
                first_book_id = book_row["BookID"]

        testament  = get_testament(first_book_id)
        era        = get_era(person["BirthYear"])

        # ── Frontmatter
        fm = f"""---
type: person
name: {yaml_str(disp_name)}
also_known_as: {json.dumps(aliases)}

name_hebrew: ""
name_greek_lxx: ""
name_latin: ""
name_meaning: ""
translation_variants:
  kjv: {yaml_str(person["Name"])}
  esv: ""
  niv: ""
  nkjv: ""

strongs:
  hebrew: ""
  greek: ""

father: {yaml_link(father_val)}
mother: {yaml_link(mother_val)}
spouse: {yaml_link_list(spouses)}
children: {yaml_link_list(children)}
siblings: {yaml_link_list(siblings)}

gender: {("male" if person["Gender"] == "M" else "female") if person["Gender"] else "unknown"}
role: []
testament: {testament}
era: {era}

birth_year: {yaml_str(person["BirthYear"])}
death_year: {yaml_str(person["DeathYear"])}
birth_place: {yaml_str(person["BirthPlace"])}
death_place: {yaml_str(person["DeathPlace"])}

first_appearance: {yaml_str(first_app)}
places_associated: []
groups_associated: {json.dumps(groups)}

confidence: medium
disambiguation_note: ""
metav_id: {pid}
---

"""

        # ── Verse body
        body = "## Verse References\n\n"
        if by_book:
            for book_name, verses in by_book.items():
                # Path-qualify so the link always points to the book note, not a
                # person/place that happens to share the name (Matthew, Luke, Ruth…).
                body += f"### [[books/{book_name}|{book_name}]]\n"
                for ch, vn, text in verses:
                    body += f"- **{ch}:{vn}** — {text.strip()}\n"
                body += "\n"
        else:
            body += "_No verse references found in MainIndex._\n"

        output = people_dir / f"{safe_filename(disp_name)}.md"
        output.write_text(fm + body, encoding="utf-8")

    print(f"  ✓ {len(people):,} person notes")


# ── Place notes ────────────────────────────────────────────────────────────────

def build_place_notes(conn, places_dir: Path, place_map: dict):
    places_dir.mkdir(parents=True, exist_ok=True)
    places = conn.execute('SELECT * FROM Places').fetchall()

    for place in places:
        plid      = place["PlaceID"]
        disp_name = place_map.get(plid, place["PlaceName"])

        aliases = [
            r["Alias"] for r in
            conn.execute('SELECT Alias FROM PlaceAliases WHERE PlaceID = ?', (plid,))
            if r["Alias"] != place["PlaceName"]
        ]

        by_book = verses_by_book(conn, "PlaceID", plid)
        first_mention = None
        first_book_id = None
        if by_book:
            first_book = next(iter(by_book))
            ch, vn, _ = by_book[first_book][0]
            first_mention = f"{first_book} {ch}:{vn}"
            book_row = conn.execute(
                'SELECT BookID FROM Books WHERE BookName = ?', (first_book,)
            ).fetchone()
            if book_row:
                first_book_id = book_row["BookID"]

        testament = get_testament(first_book_id)
        coords    = f"{place['Lat']}, {place['Lon']}" if place["Lat"] and place["Lon"] else ""

        fm = f"""---
type: place
name: {yaml_str(disp_name)}
also_known_as: {json.dumps(aliases)}

name_hebrew: ""
name_greek_lxx: ""
name_meaning: ""
modern_name: {yaml_str(place["Comment"])}
root_name: {yaml_str(place["Root"])}

place_type: unknown
testament: {testament}
first_mention: {yaml_str(first_mention)}

region: null
country: null
people_associated: []

coordinates: {yaml_str(coords)}

confidence: medium
disambiguation_note: ""
metav_id: {plid}
---

"""

        body = "## Verse References\n\n"
        if by_book:
            for book_name, verses in by_book.items():
                # Path-qualify so the link always points to the book note, not a
                # person/place that happens to share the name (Matthew, Luke, Ruth…).
                body += f"### [[books/{book_name}|{book_name}]]\n"
                for ch, vn, text in verses:
                    body += f"- **{ch}:{vn}** — {text.strip()}\n"
                body += "\n"
        else:
            body += "_No verse references found in MainIndex._\n"

        output = places_dir / f"{safe_filename(disp_name)}.md"
        output.write_text(fm + body, encoding="utf-8")

    print(f"  ✓ {len(places):,} place notes")


# ── Book notes ─────────────────────────────────────────────────────────────────

def build_book_notes(conn, books_dir: Path):
    books_dir.mkdir(parents=True, exist_ok=True)
    books = conn.execute(
        'SELECT * FROM Books ORDER BY CAST(BookID AS INTEGER)'
    ).fetchall()

    for book in books:
        bid       = book["BookID"]
        testament = get_testament(bid)

        writer_row = conn.execute(
            'SELECT Writer FROM Writers WHERE BookID = ?', (bid,)
        ).fetchone()
        writer = writer_row["Writer"] if writer_row else None

        aliases = [
            r["Alias"] for r in
            conn.execute('SELECT Alias FROM BookAliases WHERE BookID = ?', (bid,))
        ]

        fm = f"""---
type: book
name: {yaml_str(book["BookName"])}
book_id: {bid}
also_known_as: {json.dumps(aliases)}
testament: {testament}
division: {yaml_str(book["BookDiv"])}
chapters: {book["NumOfChapters"] or "null"}
author: {yaml_str(writer)}
osis_name: {yaml_str(book["OsisName"])}
short_name: {yaml_str(book["ShortName"])}
---

"""
        output = books_dir / f"{safe_filename(book['BookName'])}.md"
        output.write_text(fm, encoding="utf-8")

    print(f"  ✓ {len(books)} book notes")


# ── Validation report ──────────────────────────────────────────────────────────

def build_validation_report(conn, output_dir: Path, person_map: dict, place_map: dict):
    # Disambiguated entries (numeric suffix = needs human review)
    ambiguous_people = [
        (pid, name) for pid, name in person_map.items()
        if re.search(r'\s\(\d+\)$', name)
    ]
    ambiguous_places = [
        (plid, name) for plid, name in place_map.items()
        if re.search(r'\s\(\d+\)$', name)
    ]

    # People with no verse references
    no_verse_people = conn.execute('''
        SELECT PersonID, Name FROM People
        WHERE PersonID NOT IN (
            SELECT DISTINCT PersonID FROM MainIndex
            WHERE PersonID IS NOT NULL AND PersonID != "0"
        )
    ''').fetchall()

    # Places with no verse references
    no_verse_places = conn.execute('''
        SELECT PlaceID, PlaceName FROM Places
        WHERE PlaceID NOT IN (
            SELECT DISTINCT PlaceID FROM MainIndex
            WHERE PlaceID IS NOT NULL AND PlaceID != "0"
        )
    ''').fetchall()

    def checked_list(items, label_fn):
        if not items:
            return "_None_\n"
        return "\n".join(f"- [ ] {label_fn(i)}" for i in sorted(items, key=label_fn))

    report = f"""# Validation Report

## Summary

| Check | Count |
|-------|-------|
| Disambiguated people (need descriptive names) | {len(ambiguous_people)} |
| Disambiguated places (need descriptive names) | {len(ambiguous_places)} |
| People with no verse references | {len(no_verse_people)} |
| Places with no verse references | {len(no_verse_places)} |

---

## Disambiguated People
These share a name with at least one other person. Replace the numeric suffix with a
meaningful descriptor, e.g. `Zechariah (23)` → `Zechariah (prophet of Iddo)`.

{checked_list(ambiguous_people, lambda x: f"`{x[1]}` — MetaV ID {x[0]}")}

---

## Disambiguated Places
{checked_list(ambiguous_places, lambda x: f"`{x[1]}` — MetaV ID {x[0]}")}

---

## People with No Verse References
These were in the MetaV People table but had no MainIndex entries. May be minor
figures, spelling mismatches, or data gaps.

{checked_list(no_verse_people, lambda x: f"`{x['Name']}` (ID {x['PersonID']})")}

---

## Places with No Verse References
{checked_list(no_verse_places, lambda x: f"`{x['PlaceName']}` (ID {x['PlaceID']})")}

---

## Fields Requiring Manual Enrichment (all notes)
- `name_hebrew` / `name_greek_lxx` / `name_latin`
- `name_meaning`
- `translation_variants` (esv / niv / nkjv)
- `strongs.hebrew` / `strongs.greek`
- `place_type` on all place notes
- `role` on person notes
- Parent disambiguation (father vs mother — currently first/second parent only)
"""

    report_path = output_dir / "_validation-report.md"
    report_path.write_text(report, encoding="utf-8")
    print(f"  ✓ Validation report → {report_path}")


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="MetaV → Obsidian vault transformer")
    parser.add_argument("--download", action="store_true",
                        help="Download CSVs from GitHub before transforming")
    parser.add_argument("--output",  default="./vault",     help="Output directory (default: ./vault)")
    parser.add_argument("--csv-dir", default="./metav_csv", help="CSV source directory")
    parser.add_argument("--db",      default="./metav.db",  help="SQLite database path")
    args = parser.parse_args()

    csv_dir    = Path(args.csv_dir)
    output_dir = Path(args.output)
    db_path    = Path(args.db)

    if args.download:
        download_csvs(csv_dir)

    missing = [f for f in CSV_FILES if not (csv_dir / f).exists()]
    if missing:
        print(f"\n✗ Missing CSVs in {csv_dir}:")
        for f in missing:
            print(f"  {f}")
        print("\nRun with --download to fetch them, or place them in the csv-dir manually.")
        return

    conn = load_db(db_path, csv_dir)

    print("Building name maps...")
    person_map, place_map = build_name_maps(conn)

    print("Generating notes...")
    build_book_notes(conn,   output_dir / "books")
    build_person_notes(conn, output_dir / "people", person_map)
    build_place_notes(conn,  output_dir / "places", place_map)

    print("Generating validation report...")
    build_validation_report(conn, output_dir, person_map, place_map)

    conn.close()

    total = (
        len(list((output_dir / "people").glob("*.md"))) +
        len(list((output_dir / "places").glob("*.md"))) +
        len(list((output_dir / "books").glob("*.md")))
    )
    print(f"\nDone. {total:,} notes → {output_dir.resolve()}")
    print("\nNext steps:")
    print("  1. Review _validation-report.md")
    print("  2. Rename disambiguated entries (numeric suffixes)")
    print("  3. Install Obsidian Dataview plugin for frontmatter queries")
    print("  4. Enrich: Strong's numbers, name meanings, place types")


if __name__ == "__main__":
    main()
