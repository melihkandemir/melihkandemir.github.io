#!/usr/bin/env python3
"""Flag bibliography entries that are missing an abs/url or html link.

This is a manual/CI lint helper, not part of the Scholar citation-refresh
automation: Google Scholar's author page does not expose per-publication
links without an extra per-entry fetch for each of the ~90 publications,
which would multiply request volume and risk of being rate-limited/blocked
for a single citation-count refresh run. So link coverage stays a manual
bibliography-maintenance check, run via this script, rather than something
update_scholar_citations.py can safely infer or fetch.
"""

import re
import sys

BIB_FILE = "_bibliography/papers.bib"


def split_entries(text: str) -> list[str]:
    entries = []
    i = 0
    while True:
        start = text.find("@", i)
        if start == -1:
            break
        brace_start = text.find("{", start)
        if brace_start == -1:
            break
        depth = 1
        j = brace_start + 1
        while j < len(text) and depth > 0:
            if text[j] == "{":
                depth += 1
            elif text[j] == "}":
                depth -= 1
            j += 1
        entries.append(text[start:j])
        i = j
    return entries


def entry_key(entry: str) -> str:
    match = re.match(r"@\w+\{([^,]+),", entry)
    return match.group(1) if match else "?"


def has_field(entry: str, field: str) -> bool:
    return re.search(rf"\b{field}\s*=", entry) is not None


def main() -> int:
    with open(BIB_FILE) as f:
        text = f.read()

    entries = split_entries(text)
    missing = []
    for entry in entries:
        # Only flag entries that read as an actual paper (has an abstract),
        # so patents/awards without a public write-up aren't false positives.
        if not has_field(entry, "abstract"):
            continue
        if has_field(entry, "url") and has_field(entry, "html"):
            continue
        missing.append((entry_key(entry), has_field(entry, "url"), has_field(entry, "html")))

    if not missing:
        print(f"All {len(entries)} entries with an abstract have both url and html links.")
        return 0

    print(f"{len(missing)} entrie(s) with an abstract are missing a link:")
    for key, has_url, has_html in missing:
        flags = []
        if not has_url:
            flags.append("url")
        if not has_html:
            flags.append("html")
        print(f"  - {key}: missing {', '.join(flags)}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
