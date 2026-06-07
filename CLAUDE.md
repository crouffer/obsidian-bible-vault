# Bible Vault Builder

## What this is

A toolchain that transforms the MetaV biblical metadata database into an Obsidian vault of
structured Markdown notes — one file per person, place, and book in the Bible. The vault is
designed for personal Bible study, cross-reference research, and agent-assisted enrichment.

## Quick start

```bash
python3 scripts/metav_transformer.py --download   # first run: downloads CSVs + generates vault
python3 scripts/metav_transformer.py              # subsequent runs: regenerate from cached CSVs
```

Then open the `vault/` directory in Obsidian. Install the **Dataview** plugin.

## Project structure

```
bible-vault-builder/
  CLAUDE.md                   ← you are here
  README.md
  ATTRIBUTION.md
  scripts/
    metav_transformer.py      ← main transformer
  vault/                      ← generated output (gitignored until you decide to publish)
    people/                   ← one .md per biblical person
    places/                   ← one .md per biblical place
    books/                    ← one .md per Bible book
    _validation-report.md     ← review queue after each run
  metav_csv/                  ← cached source CSVs (gitignored)
  metav.db                    ← SQLite working database (gitignored)
```

## Data sources

| Source | What it provides | License |
|--------|-----------------|---------|
| MetaV (viz.bible / robertrouse) | People, places, relationships, verse tags | CC BY-SA 3.0 |
| openscriptures/strongs | Strong's Hebrew/Greek concordance | CC BY-SA 3.0 |
| OpenBible.info/geo | Place coordinates and modern names | CC BY |
| KJV text (1769 Cambridge) | Verse text | Public domain |

**Vault content license: CC BY-SA 3.0** (required by Share-Alike on MetaV and Strong's).
**Script license: MIT** (original work).

## Note schemas

### Person note (`vault/people/*.md`)

```yaml
---
type: person
name: Seth                          # canonical display name
also_known_as: ["Sheth"]           # all aliases from MetaV PeopleAliases

name_hebrew: ""                     # ← enrichment needed
name_greek_lxx: ""                  # ← enrichment needed
name_latin: ""                      # ← enrichment needed
name_meaning: ""                    # ← enrichment needed
translation_variants:
  kjv: Seth
  esv: ""                           # ← enrichment needed
  niv: ""                           # ← enrichment needed
  nkjv: ""                          # ← enrichment needed

strongs:
  hebrew: ""                        # e.g. H8352 — enrichment needed
  greek: ""                         # e.g. G4589 — enrichment needed

father: "[[Adam]]"                  # wikilink to parent note
mother: "[[Eve]]"
spouse: []
children:
  - "[[Enos]]"
siblings:
  - "[[Abel]]"
  - "[[Cain]]"

gender: male                        # male | female | unknown
role: []                            # e.g. [prophet, king, priest, apostle]
testament: OT                       # OT | NT | both | unknown
era: antediluvian                   # see era list below

birth_year: "3811 BC"
death_year: "2899 BC"
birth_place: Eden
death_place: null

first_appearance: "Genesis 4:25"
places_associated: []               # ← enrichment needed
groups_associated: ["Genealogy of Jesus"]

confidence: medium                  # high | medium | low
disambiguation_note: ""             # explain if name is ambiguous
metav_id: 2504                      # source ID — do not edit
---
```

**Era values:** antediluvian | post-flood | patriarchal | exodus | judges | monarchy |
exile | post-exile | second-temple | new-testament | unknown

### Place note (`vault/places/*.md`)

```yaml
---
type: place
name: Beersheba
also_known_as: ["Beer-sheba", "Bersabee"]

name_hebrew: ""                     # ← enrichment needed
name_greek_lxx: ""                  # ← enrichment needed
name_meaning: ""                    # ← enrichment needed
modern_name: "Tel Be'er Sheva, Israel"
root_name: ""                       # original name if changed over time

place_type: unknown                 # city | region | mountain | river | sea |
                                    # wilderness | country | district | unknown
testament: OT                       # OT | NT | both | unknown
first_mention: "Genesis 21:14"

region: null                        # wikilink, e.g. "[[Negev]]"
country: null                       # wikilink, e.g. "[[Canaan]]"
people_associated: []               # ← enrichment needed

coordinates: "31.24, 34.79"

confidence: medium
disambiguation_note: ""
metav_id: 1234
---
```

### Book note (`vault/books/*.md`)

```yaml
---
type: book
name: Genesis
book_id: 1
also_known_as: ["Gen", "Ge", "Bereshit"]
testament: OT
division: Pentateuch
chapters: 50
author: Moses
osis_name: Gen
short_name: Ge
---
```

## Key design decisions

**Disambiguation naming:** When two people share a name, the script appends the MetaV PersonID
in parentheses: `Zechariah (23).md`. These are placeholders. Replace the numeric suffix with a
meaningful descriptor: `Zechariah (prophet of Iddo).md`. All placeholders are listed in
`_validation-report.md`.

**Parent gender split:** MetaV does not distinguish father from mother in its relationships
table. The transformer assigns the first listed parent to `father` and the second to `mother`.
This is wrong in some cases. Enrichment pass needed — use gender field to sort correctly.

**Verse text:** KJV only (that is what MetaV provides). Other translation variants are empty
fields awaiting enrichment.

**Confidence field:** `medium` is the default for all generated notes. Set to `high` once
a note has been reviewed. Set to `low` for uncertain identifications (e.g. which Zechariah
is referenced in Matthew 23:35).

**wikilinks:** Every `[[Link]]` in the frontmatter must resolve to a file in the vault.
Broken links indicate a data gap or a disambiguation rename that wasn't propagated.

## Enrichment priorities (in order)

1. **Rename disambiguated entries** — see `_validation-report.md`. Required before links work.
2. **Strong's numbers** — H/G numbers unlock Hebrew/Greek lexical data.
3. **Name meanings** — derivable from Strong's descriptions once numbers are filled.
4. **Place types** — classify each place (city, mountain, river, etc.).
5. **Translation variants** — ESV/NIV/NKJV name forms for major figures.
6. **Parent disambiguation** — fix father/mother assignments using gender data.

## Dataview queries (useful starting points)

```dataview
TABLE father, mother, testament, era
FROM "people"
WHERE type = "person" AND confidence = "low"
```

```dataview
TABLE first_appearance, groups_associated
FROM "people"
WHERE type = "person" AND era = "antediluvian"
```

```dataview
TABLE modern_name, coordinates
FROM "places"
WHERE type = "place" AND place_type = "unknown"
```

## Transformer flags

```bash
--download          Download CSVs from GitHub (first run only)
--output ./vault    Output directory (default: ./vault)
--csv-dir ./metav_csv   CSV cache directory
--db ./metav.db     SQLite working database
```

## Known limitations

- KJV text only; no multi-translation verse body
- MainIndex tags at word level — some implied references (pronouns) are not captured
- Father/mother assignment is approximate for some entries
- Strong's numbers not yet auto-populated (enrichment pass needed)
- MetaV people data sourced from complete-bible-genealogy.com and marshallgenealogy.org;
  minor figures may have sparse or missing data
