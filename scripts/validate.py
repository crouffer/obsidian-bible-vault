#!/usr/bin/env python3
"""
Bible Vault Validator
=====================
Deterministic integrity checks for the generated Obsidian vault. This is the
mechanical backbone the `vault-validator` agent builds on — it catches the
exact, rule-based problems (bad YAML, invalid enum values, broken wikilinks,
filename/name mismatches, leftover disambiguation placeholders) so the agent
can focus on judgment calls.

Dependencies: PyYAML (`pip install pyyaml`). Everything else is stdlib.

Usage:
  python3 scripts/validate.py                 # validate ./vault, human report
  python3 scripts/validate.py ./my-vault      # validate a different directory
  python3 scripts/validate.py --json          # machine-readable output (for agents/CI)
  python3 scripts/validate.py --strict        # treat warnings as failures too

Exit code: 0 if no errors, 1 if any errors (or any warnings under --strict).
Disambiguation placeholders and empty enrichment fields are reported but are
NOT errors — they are expected, known work, not data corruption.
"""

import sys
import re
import json
import argparse
from pathlib import Path
from collections import defaultdict

try:
    import yaml
except ImportError:
    print("ERROR: PyYAML is required. Install it with:  pip install pyyaml", file=sys.stderr)
    sys.exit(2)

# ── Schema ───────────────────────────────────────────────────────────────────

# folder name → expected `type` value
FOLDER_TYPE = {"people": "person", "places": "place", "books": "book"}

ENUMS = {
    "gender":     {"male", "female", "unknown"},
    "testament":  {"OT", "NT", "both", "unknown"},
    "era": {
        "antediluvian", "post-flood", "patriarchal", "exodus", "judges",
        "monarchy", "exile", "post-exile", "second-temple", "new-testament",
        "unknown",
    },
    "place_type": {
        "city", "region", "mountain", "river", "sea", "wilderness",
        "country", "district", "unknown",
    },
    "confidence": {"high", "medium", "low"},
}

# which enums apply to which note type
ENUM_FIELDS = {
    "person": ["gender", "testament", "era", "confidence"],
    "place":  ["testament", "place_type", "confidence"],
    "book":   ["testament"],
}

# fields that must be present and non-empty (error if missing)
REQUIRED = {
    "person": ["type", "name", "metav_id"],
    "place":  ["type", "name", "metav_id"],
    "book":   ["type", "name", "book_id"],
}

WIKILINK_RE = re.compile(r"\[\[([^\]|#]+)")        # captures target of [[Target]], [[Target|alias]], [[Target#heading]]
DISAMBIG_RE = re.compile(r"\s\(\d+\)$")             # trailing " (123)" placeholder suffix

# mirrors safe_filename() in metav_transformer.py
def safe_filename(name):
    return re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", str(name)).strip()


# ── Note parsing ─────────────────────────────────────────────────────────────

def split_frontmatter(text):
    """Return (frontmatter_str, body_str). Raises ValueError if no valid block."""
    if not text.startswith("---"):
        raise ValueError("file does not start with a '---' frontmatter block")
    parts = text.split("---", 2)
    if len(parts) < 3:
        raise ValueError("frontmatter block is not closed with '---'")
    return parts[1], parts[2]


def extract_links(value):
    """Recursively pull [[wikilink]] targets from any frontmatter value."""
    out = []
    if value is None:
        return out
    if isinstance(value, str):
        out.extend(WIKILINK_RE.findall(value))
    elif isinstance(value, list):
        for item in value:
            out.extend(extract_links(item))
    elif isinstance(value, dict):
        for item in value.values():
            out.extend(extract_links(item))
    return out


# ── Validation ───────────────────────────────────────────────────────────────

class Report:
    def __init__(self):
        self.issues = []   # (severity, relpath, field, message)
        self.stats = {}

    def error(self, path, field, msg):   self.issues.append(("error", path, field, msg))
    def warning(self, path, field, msg): self.issues.append(("warning", path, field, msg))

    @property
    def n_errors(self):   return sum(1 for s, *_ in self.issues if s == "error")
    @property
    def n_warnings(self): return sum(1 for s, *_ in self.issues if s == "warning")


def validate(vault_dir: Path) -> Report:
    rep = Report()
    notes = {}        # relpath -> {"type","data","body","stem"}
    valid_targets = set()   # every note's filename stem — what wikilinks resolve against

    # ── Pass 1: parse every note, collect link targets
    for folder, expected_type in FOLDER_TYPE.items():
        d = vault_dir / folder
        if not d.is_dir():
            rep.error(folder + "/", "", f"expected folder '{folder}' is missing")
            continue
        for path in sorted(d.glob("*.md")):
            rel = f"{folder}/{path.name}"
            valid_targets.add(path.stem)
            try:
                text = path.read_text(encoding="utf-8")
            except Exception as e:
                rep.error(rel, "", f"could not read file: {e}")
                continue
            try:
                fm, body = split_frontmatter(text)
                data = yaml.safe_load(fm)
            except ValueError as e:
                rep.error(rel, "frontmatter", str(e))
                continue
            except yaml.YAMLError as e:
                rep.error(rel, "frontmatter", f"invalid YAML: {str(e).splitlines()[0]}")
                continue
            if not isinstance(data, dict):
                rep.error(rel, "frontmatter", "frontmatter did not parse to a mapping")
                continue
            notes[rel] = {"type": expected_type, "data": data, "body": body, "stem": path.stem}

    # ── Pass 2: per-note checks
    coverage = defaultdict(lambda: defaultdict(int))   # type -> metric -> count
    disambig = []
    for rel, note in notes.items():
        data, expected_type, stem = note["data"], note["type"], note["stem"]
        coverage[expected_type]["total"] += 1

        # required fields
        for field in REQUIRED[expected_type]:
            val = data.get(field)
            if val is None or (isinstance(val, str) and not val.strip()):
                rep.error(rel, field, f"required field '{field}' is missing or empty")

        # type matches folder
        if data.get("type") and data["type"] != expected_type:
            rep.error(rel, "type", f"type is '{data['type']}' but note is in the {expected_type} folder")

        # name must be a string — bare words like On/No/Yes/True coerce to bool/null/number
        name = data.get("name")
        if name is not None and not isinstance(name, str):
            rep.error(rel, "name", f"name parsed as {type(name).__name__} ({name!r}) — a bare "
                                   f"YAML keyword (e.g. On/No/Yes/True); it must be quoted in the frontmatter")
            name = None  # don't also emit a confusing filename-mismatch below
        # filename matches name (a mismatch is what silently breaks [[wikilinks]])
        if name and safe_filename(name) != stem:
            rep.error(rel, "name", f"filename stem '{stem}' does not match name '{name}'")

        # enum values (only checked when present)
        for field in ENUM_FIELDS[expected_type]:
            val = data.get(field)
            if val is not None and str(val) not in ENUMS[field]:
                allowed = ", ".join(sorted(ENUMS[field]))
                rep.error(rel, field, f"value '{val}' not in allowed set ({allowed})")

        # list-shaped fields really are lists
        for field in ("also_known_as", "spouse", "children", "siblings", "role",
                      "places_associated", "groups_associated", "people_associated"):
            if field in data and data[field] is not None and not isinstance(data[field], list):
                rep.error(rel, field, f"'{field}' should be a list, got {type(data[field]).__name__}")

        # disambiguation placeholder (warning — known, expected work)
        if name and DISAMBIG_RE.search(str(name)):
            disambig.append(rel)
            rep.warning(rel, "name", f"disambiguation placeholder '{name}' — rename to a descriptor")

        # wikilink resolution (frontmatter + body)
        targets = set(extract_links(data))
        targets.update(WIKILINK_RE.findall(note["body"]))
        for t in sorted(targets):
            if t.strip() and t.strip() not in valid_targets:
                rep.error(rel, "wikilink", f"broken link [[{t.strip()}]] — no matching note")

        # enrichment coverage (informational, not an issue)
        if expected_type == "person":
            s = data.get("strongs") or {}
            if isinstance(s, dict) and (str(s.get("hebrew") or "").strip() or str(s.get("greek") or "").strip()):
                coverage["person"]["has_strongs"] += 1
            if str(data.get("name_meaning") or "").strip():
                coverage["person"]["has_meaning"] += 1
            if str(data.get("confidence") or "") == "high":
                coverage["person"]["confidence_high"] += 1
        elif expected_type == "place":
            if str(data.get("place_type") or "unknown") != "unknown":
                coverage["place"]["classified"] += 1

    rep.stats = {
        "notes_total": len(notes),
        "by_type": {t: coverage[t]["total"] for t in FOLDER_TYPE.values()},
        "errors": rep.n_errors,
        "warnings": rep.n_warnings,
        "disambiguation_placeholders": len(disambig),
        "people_with_strongs": coverage["person"]["has_strongs"],
        "people_with_name_meaning": coverage["person"]["has_meaning"],
        "people_confidence_high": coverage["person"]["confidence_high"],
        "places_classified": coverage["place"]["classified"],
    }
    return rep


# ── Output ───────────────────────────────────────────────────────────────────

def print_human(rep: Report, strict: bool):
    by_sev = defaultdict(list)
    for sev, path, field, msg in rep.issues:
        by_sev[sev].append((path, field, msg))

    if by_sev["error"]:
        print(f"\n✗ ERRORS ({len(by_sev['error'])})")
        for path, field, msg in sorted(by_sev["error"]):
            loc = f"{path}" + (f" [{field}]" if field else "")
            print(f"  • {loc}: {msg}")

    if by_sev["warning"]:
        # Collapse the (often numerous) disambiguation warnings into a count.
        disambig = [w for w in by_sev["warning"] if "disambiguation placeholder" in w[2]]
        other = [w for w in by_sev["warning"] if "disambiguation placeholder" not in w[2]]
        print(f"\n⚠ WARNINGS ({len(by_sev['warning'])})")
        for path, field, msg in sorted(other):
            loc = f"{path}" + (f" [{field}]" if field else "")
            print(f"  • {loc}: {msg}")
        if disambig:
            print(f"  • {len(disambig)} disambiguation placeholders to rename "
                  f"(see vault/_validation-report.md)")

    s = rep.stats
    print("\n── Summary ─────────────────────────────")
    print(f"  Notes:        {s['notes_total']:,}  "
          f"(people {s['by_type'].get('person',0):,}, "
          f"places {s['by_type'].get('place',0):,}, "
          f"books {s['by_type'].get('book',0):,})")
    print(f"  Errors:       {s['errors']:,}")
    print(f"  Warnings:     {s['warnings']:,}")
    print("── Enrichment coverage ─────────────────")
    print(f"  Disambiguation placeholders: {s['disambiguation_placeholders']:,}")
    print(f"  People with Strong's:        {s['people_with_strongs']:,}")
    print(f"  People with name meaning:    {s['people_with_name_meaning']:,}")
    print(f"  People confidence=high:      {s['people_confidence_high']:,}")
    print(f"  Places classified:           {s['places_classified']:,}")

    ok = rep.n_errors == 0 and (not strict or rep.n_warnings == 0)
    print()
    print("✓ PASS" if ok else "✗ FAIL")


def main():
    ap = argparse.ArgumentParser(description="Validate the Bible Vault for format and integrity.")
    ap.add_argument("vault", nargs="?", default="./vault", help="Vault directory (default: ./vault)")
    ap.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    ap.add_argument("--strict", action="store_true", help="Treat warnings as failures")
    args = ap.parse_args()

    vault_dir = Path(args.vault)
    if not vault_dir.is_dir():
        print(f"ERROR: vault directory not found: {vault_dir}", file=sys.stderr)
        sys.exit(2)

    rep = validate(vault_dir)

    if args.json:
        print(json.dumps({"stats": rep.stats,
                          "issues": [{"severity": s, "file": p, "field": f, "message": m}
                                     for s, p, f, m in rep.issues]}, indent=2))
    else:
        print_human(rep, args.strict)

    failed = rep.n_errors > 0 or (args.strict and rep.n_warnings > 0)
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
