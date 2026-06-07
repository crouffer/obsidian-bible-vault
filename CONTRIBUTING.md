# Contributing

Thank you for helping improve the Bible Vault. The vault ships as a strong but unfinished
foundation: the structure and relationships are in place, but many scholarly fields are empty
placeholders awaiting enrichment. Filling them — accurately and with sources — is the most
valuable contribution you can make.

This guide explains **what to work on**, **how to edit notes correctly**, and **how to submit
changes**.

## Ground rules

- **Cite your sources.** Every factual addition (a Strong's number, a name meaning, a date)
  should be verifiable. Note your source in the PR description, or in the `disambiguation_note`
  field when it clarifies an ambiguous identification.
- **Edit the committed notes in `vault/`.** That folder is the published product. Hand
  enrichment lives there. (The transformer *regenerates* `vault/` and will overwrite hand edits
  — see [Regeneration](#a-note-on-regeneration) before running it.)
- **Keep the YAML valid.** The frontmatter is parsed by Obsidian's Dataview. A broken header
  silently drops a note from queries. Validate before committing (see [Validating](#validating-your-changes)).
- **Don't touch `metav_id` / `book_id`.** These link a note back to its source record. Leave
  them as-is.
- **Preserve attribution and license.** Content is CC BY-SA 3.0; contributions are accepted
  under the same terms. Keep `ATTRIBUTION.md` intact.

## Where to start (enrichment priorities)

In rough order of impact:

1. **Rename disambiguated entries.** Notes whose name ends in a numeric suffix — e.g.
   `Zechariah (23)` — are placeholders for people/places who share a name. Rename the file and
   the `name:` field to a meaningful descriptor: `Zechariah (prophet of Iddo)`. **Then fix every
   wikilink that points at the old name** so links don't break. The full list is in
   [`vault/_validation-report.md`](vault/_validation-report.md).
2. **Add Strong's numbers** (`strongs.hebrew`, `strongs.greek`). These unlock lexical data and
   are the basis for name meanings. Format: `H8352`, `G4589`.
3. **Add name meanings** (`name_meaning`) — typically derivable from the Strong's entry.
4. **Classify place types** (`place_type`): one of `city`, `region`, `mountain`, `river`, `sea`,
   `wilderness`, `country`, `district`. Replace the default `unknown`.
5. **Add translation variants** (`translation_variants.esv` / `.niv` / `.nkjv`) for major
   figures.
6. **Fix father/mother assignments.** The source doesn't distinguish parents by role, so the
   generator assigns the first parent to `father` and the second to `mother` — sometimes
   wrongly. Use the parents' `gender` to correct them.

Smaller but welcome: original-language names (`name_hebrew`, `name_greek_lxx`, `name_latin`),
`role` tags on people, `region` / `country` wikilinks on places, and `people_associated` /
`places_associated` cross-links.

## Field conventions

- **Wikilinks must resolve.** Any `[[Name]]` in frontmatter must match an existing note's
  filename. If you rename a target, update the links that reference it. Broken links signal a
  data gap or an incomplete rename.
- **`confidence`** — set to `high` once you've reviewed and sourced a note; `low` for uncertain
  identifications (e.g. which Zechariah is meant in Matthew 23:35). Default generated value is
  `medium`.
- **`disambiguation_note`** — use this to explain an ambiguous or contested identification.
- **`gender`** — `male` | `female` | `unknown`.
- **`testament`** — `OT` | `NT` | `both` | `unknown`.
- **`era`** (people) — one of: `antediluvian`, `post-flood`, `patriarchal`, `exodus`, `judges`,
  `monarchy`, `exile`, `post-exile`, `second-temple`, `new-testament`, `unknown`.
- **Years** — keep the `"3811 BC"` / `"30 AD"` string format.
- **Empty vs. null** — leave enrichment string fields as `""` until filled; use `null` only
  where the schema already does (e.g. `death_place: null`).

The authoritative field-by-field schema lives in [`CLAUDE.md`](CLAUDE.md#note-schemas).

## Two ways to contribute

**Improve the data (most common).** Edit notes directly in `vault/` — in Obsidian or any text
editor — following the conventions above. Best for filling enrichment fields, renaming
disambiguated entries, and fixing relationships.

**Improve the generator.** If a problem is systematic (affects many notes the same way), fix it
in [`scripts/metav_transformer.py`](scripts/metav_transformer.py) instead of editing thousands
of files by hand, then regenerate. Best for schema changes, new derived fields, or correcting a
transformation rule.

## A note on regeneration

Running `python3 scripts/metav_transformer.py` **overwrites every file in `vault/`**. If you've
hand-enriched notes, a rebuild will discard those edits unless they came from the transformer.
So:

- Doing data enrichment? Edit `vault/` and **don't** regenerate.
- Doing a generator change? Regenerate, and expect hand edits to be lost — coordinate first.
- Always commit your work before regenerating, so nothing is lost irrecoverably.

## Validating your changes

Before opening a PR, run the validator — it catches malformed YAML, invalid field values,
filename/name mismatches, and broken `[[wikilinks]]`:

```bash
pip install pyyaml          # one-time; the validator's only dependency
python3 scripts/validate.py # exit code 0 = clean, 1 = errors found
```

Then, for anything the script can't check:

1. **Open the vault in Obsidian** and confirm your edited notes render with no YAML errors
   (a malformed header shows as raw text or breaks Dataview).
2. **Check for broken links** — Obsidian flags unresolved `[[links]]`; a renamed note shouldn't
   leave any dangling.
3. **Spot-check a Dataview query** that touches the field you changed (see the README examples)
   to confirm the value is picked up.

## Submitting a pull request

1. Fork the repo and create a branch: `git checkout -b enrich/strongs-genesis`.
2. Make focused changes — one theme per PR (e.g. "Strong's numbers for Genesis genealogy")
   reviews far more easily than a sweeping mixed change.
3. In the PR description, summarize **what** you changed and **cite the sources** you used.
4. Reference any `_validation-report.md` items you resolved.

Questions or a correction you're unsure how to model? Open an issue first — it's a fine way to
discuss before investing in edits.
