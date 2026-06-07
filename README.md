# Bible Vault Builder

Transforms the [MetaV biblical database](https://github.com/theonize/KJV-bible-database-with-metadata-MetaV-)
into an Obsidian vault of structured Markdown notes — one file per person, place, and book in the Bible.

**4,427 notes. ~10 seconds. Python stdlib only.**

## Requirements

- Python 3.8+
- Internet connection (first run only)
- [Obsidian](https://obsidian.md) with the [Dataview plugin](https://github.com/blacksmithgu/obsidian-dataview)

## Usage

```bash
# First run — downloads source data and generates vault
python3 scripts/metav_transformer.py --download

# Subsequent runs — regenerate from cached data
python3 scripts/metav_transformer.py

# Custom output location
python3 scripts/metav_transformer.py --download --output ./my-vault
```

Then open the `vault/` folder as an Obsidian vault.

## What you get

- **3,085 person notes** — relationships, verse references, aliases, birth/death data
- **1,276 place notes** — coordinates, aliases, verse references
- **66 book notes** — metadata, author, division
- **`_validation-report.md`** — review queue for disambiguation and data gaps

## After generation

1. Review `vault/_validation-report.md`
2. Rename disambiguated entries (numeric suffixes → meaningful descriptors)
3. Begin enrichment: Strong's numbers, name meanings, place types

See `CLAUDE.md` for full schema documentation and enrichment priorities.

## Licenses

- **Vault content:** [CC BY-SA 3.0](LICENSE-content.md) — required by source data
- **Scripts:** [MIT](LICENSE-code.md) — original work

See `ATTRIBUTION.md` for required source credits.
