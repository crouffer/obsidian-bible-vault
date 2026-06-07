# Bible Vault

An [Obsidian](https://obsidian.md) vault for Bible study — **4,427 interlinked notes**, one
for every person, place, and book in the King James Bible. Genealogies, verse references,
aliases, coordinates, and timelines, all as plain Markdown you can read, search, link, and
query.

The data is the point. The vault lives in [`vault/`](vault/) and is ready to use — no build
step required. (A Python script to regenerate it from source is included for the curious; see
[Regenerating from source](#regenerating-from-source).)

## What's inside

| | Count | Each note has |
|---|---|---|
| 👤 **People** | 3,085 | parents, spouse, children, siblings (as wikilinks), gender, era, birth/death years and places, group memberships, every verse they appear in |
| 📍 **Places** | 1,276 | coordinates, modern name, aliases, testament, first mention, every verse it appears in |
| 📖 **Books** | 66 | author, division, chapter count, OSIS/short names, aliases |

Plus [`vault/_validation-report.md`](vault/_validation-report.md) — a review queue flagging
ambiguous names and data gaps.

Every relationship is a real Obsidian link, so the graph view shows the genealogy of Scripture,
and clicking through `father` / `children` / `siblings` walks you up and down family trees.

## Quick start

You don't need Python or any build tools to *use* the vault.

1. **Get the files** — clone this repo, or download it as a ZIP and unzip it:
   ```bash
   git clone <repo-url>
   ```
2. **Open in Obsidian** — *Open folder as vault* → select the `vault/` folder.
3. **Trust plugins when prompted** — the [Dataview](https://github.com/blacksmithgu/obsidian-dataview)
   plugin is bundled and pre-configured, so the queries below work immediately.

That's it. Start at [`vault/books/Genesis.md`](vault/books/Genesis.md) or open the **graph view**
and explore.

> New to Obsidian? It's a free, local, offline Markdown app — your notes stay on your machine.
> The vault is just a folder of `.md` files, so it also works in VS Code, on GitHub, or any
> editor. Obsidian simply makes the links and queries come alive.

## Anatomy of a note

Each note is human-readable Markdown with a structured YAML header. For example,
`people/Seth.md`:

```yaml
---
type: person
name: Seth
also_known_as: ["Sheth"]
father: "[[Adam]]"
mother: "[[Eve]]"
children:
  - "[[Enos]]"
siblings:
  - "[[Abel]]"
  - "[[Cain]]"
gender: male
testament: OT
era: antediluvian
birth_year: 3811 BC
death_year: 2899 BC
first_appearance: "Genesis 4:25"
metav_id: 2504
---

## Verse References
### [[Genesis]]
- **4:25** — And Adam knew his wife again; and she bare a son, and called his name Seth...
```

The structured header means you can ask the vault questions. The note body gives you the KJV
text in context.

## Using it

**Navigate by link.** Click any `[[name]]` to jump. Open the graph view to see clusters —
genealogies, the people of a city, the figures of a book.

**Filter the graph view.** Open the graph, click the **Filters** control (top-left), and type a
query in the search box. It uses Obsidian's search syntax — including frontmatter properties in
`["key":"value"]` form — so you can carve the 4,400-node graph down to exactly what you want:

| Query | Shows |
|-------|-------|
| `path:people` | only people |
| `-path:books` | everything except book notes |
| `path:places OR path:people` | people and the places, no books |
| `["testament":"NT"]` | only New Testament entities |
| `["era":"monarchy"]` | people who lived during the monarchy |
| `["gender":"female"]` | women of the Bible |
| `["place_type"] -["place_type":"unknown"]` | places that have been classified |
| `["confidence":"low"]` | flagged uncertain identifications |
| `path:people ["era":"new-testament"]` | combine path + property (space = AND) |
| `["groups_associated":"Genealogy of Jesus"]` | the line of Christ |

**Color-code with graph groups.** In the graph's **Groups** panel, click *New group*, enter one
of the same queries, and pick a color. Each group repaints matching nodes — great for seeing
structure at a glance:

| Group query | Suggested color |
|-------------|-----------------|
| `path:people` | green |
| `path:places` | blue |
| `path:books` | orange |
| `["testament":"OT"]` | amber |
| `["testament":"NT"]` | teal |

**Focus one note (local graph).** Open any person's note and run *Open local graph* (command
palette, or the ⋮ menu). Use the **depth** slider to show just direct relations or extend
outward, and apply the same filters (e.g. `path:people`) to isolate a single family tree. Tip:
in *Display*, size nodes by number of links so hubs like `[[Jesus]]`, `[[David]]`, and
`[[Jerusalem]]` stand out.

**Query with Dataview.** Drop these into any note (in a ` ```dataview ` block):

```dataview
TABLE birth_year, death_year, era
FROM "people"
WHERE era = "antediluvian"
SORT birth_year ASC
```

```dataview
TABLE modern_name, coordinates
FROM "places"
WHERE coordinates != ""
```

```dataview
LIST
FROM "people"
WHERE contains(groups_associated, "Genealogy of Jesus")
```

**Search full text.** Every verse a person or place appears in is in the note body, so
Obsidian's search finds them instantly.

## A note on data quality

This vault is a strong, honest foundation — not a finished scholarly reference. Be aware:

- **Some fields are intentionally empty**, awaiting enrichment: `name_hebrew`, `name_greek_lxx`,
  `name_meaning`, `strongs` (Hebrew/Greek concordance numbers), and the ESV/NIV/NKJV
  translation variants. They're present in every note as placeholders so the structure is
  consistent and contributions are easy.
- **`confidence: medium`** is the default on generated notes. It is not a claim of verification.
- **Disambiguated names** carry a numeric suffix (e.g. `Zechariah (23)`) where several people
  share a name. These are placeholders meant to be renamed to descriptors like
  `Zechariah (prophet of Iddo)`.
- **Father/mother may be swapped** in some entries — the source doesn't distinguish parents by
  role, so the generator guesses. The `gender` field lets you correct these.
- **KJV text only** (that's what the source provides).

See [`vault/_validation-report.md`](vault/_validation-report.md) for the specific entries that
need attention, and [`CLAUDE.md`](CLAUDE.md) for the full field schema and enrichment priorities.

## Contributing

Improvements are welcome and the license encourages sharing them back. The highest-value work:

1. **Rename disambiguated entries** (numeric suffix → meaningful descriptor) so links resolve cleanly.
2. **Add Strong's numbers** — these unlock Hebrew/Greek lexical data and name meanings.
3. **Classify place types** (city, mountain, river, region…).
4. **Add translation variants** for major figures.
5. **Fix father/mother assignments** using the `gender` field.

You can edit notes directly in Obsidian or in any text editor. If you regenerate the vault from
source, note that it overwrites the `vault/` files — so enrichment is best done on the committed
notes, or by improving the transformer itself.

**See [`CONTRIBUTING.md`](CONTRIBUTING.md)** for the full enrichment workflow — field
conventions, how to validate changes, and how to submit a pull request. The field-by-field
schema is in [`CLAUDE.md`](CLAUDE.md).

## Regenerating from source

The vault is produced from the [MetaV biblical database](https://github.com/theonize/KJV-bible-database-with-metadata-MetaV-)
by [`scripts/metav_transformer.py`](scripts/metav_transformer.py) (Python 3.8+, standard library
only — no dependencies).

```bash
# First run — download source CSVs, then build the vault
python3 scripts/metav_transformer.py --download

# Rebuild from cached CSVs
python3 scripts/metav_transformer.py

# Build to a custom location (leaves the committed vault untouched)
python3 scripts/metav_transformer.py --output ./my-vault
```

> macOS note: if `--download` fails with an SSL certificate error, fetch the CSVs with `curl`
> first (the script will then use the cache):
> ```bash
> mkdir -p metav_csv && BASE="https://raw.githubusercontent.com/theonize/KJV-bible-database-with-metadata-MetaV-/master/CSV"
> for f in Books BookAliases Writers People PeopleAliases PeopleRelationships PeopleGroups Places PlaceAliases Verses MainIndex; do curl -fsSL "$BASE/$f.csv" -o "metav_csv/$f.csv"; done
> python3 scripts/metav_transformer.py
> ```

## Sources & licenses

| Source | Provides | License |
|--------|----------|---------|
| [MetaV](https://github.com/theonize/KJV-bible-database-with-metadata-MetaV-) (viz.bible / robertrouse) | People, places, relationships, verse tags | CC BY-SA 3.0 |
| KJV (1769 Cambridge) | Verse text | Public domain |
| [OpenBible.info](https://www.openbible.info/geo/) | Place coordinates | CC BY |

- **Vault content:** [CC BY-SA 3.0](LICENSE-content.md) — you may share and adapt it, with
  attribution, under the same license.
- **Scripts:** [MIT](LICENSE-code.md).

Required source credits are in [`ATTRIBUTION.md`](ATTRIBUTION.md). If you publish a derivative
vault, please keep that attribution and apply the same Share-Alike license.
