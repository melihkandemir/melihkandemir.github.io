#!/usr/bin/env python
"""Refresh Google Scholar citation data and add any papers missing from bib.

Unlike a lab site, this personal site tracks a single author, so we screen
one Scholar profile (the scholar_userid in _data/socials.yml).

For every publication it finds:
  - It always records title/year/citation-count into _data/citations.yml,
    keyed by Scholar's own author_pub_id. This part is one bulk request -
    cheap regardless of how many papers there are.
  - If the paper's title doesn't match (exactly or fuzzily) anything already
    in _bibliography/papers.bib AND its year is at or after the earliest
    year already curated there, it is treated as missing from the
    bibliography and gets ONE extra scholarly.fill() call to pull its full
    author list, abstract and venue, which is used to append a new BibTeX
    entry. This extra request only happens for genuinely new/missing papers
    (typically zero to a handful per run), not for the full publication
    list, to keep Scholar request volume low. The year cutoff matters: the
    Scholar profile includes an entire career, and without it the first run
    would dump decades of early publications into the curated bibliography
    instead of just catching genuinely new output.
"""

from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime
from difflib import SequenceMatcher

import yaml

from _bibtex_utils import (
    BIB_FILE,
    earliest_bib_year,
    format_authors,
    guess_abbr,
    is_junk_title,
    known_string_macros,
    load_bib_titles,
    slugify_key,
    split_entries,
    venue_from_citation,
)
from _bibtex_utils import best_title_match as match_title
from scholarly import scholarly

CONFIG_FILE = "_data/socials.yml"
OUTPUT_FILE = "_data/citations.yml"

CONFERENCE_HINTS = (
    "conference",
    "workshop",
    "symposium",
    "proceedings",
    "advances in neural",
    "international",
)


def load_scholar_user_id() -> str:
    if not os.path.exists(CONFIG_FILE):
        print(f"Configuration file {CONFIG_FILE} not found.")
        sys.exit(1)
    try:
        with open(CONFIG_FILE) as f:
            config = yaml.safe_load(f)
        scholar_user_id = config.get("scholar_userid")
        if not scholar_user_id:
            print("No 'scholar_userid' found in the configuration file.")
            sys.exit(1)
        return scholar_user_id
    except yaml.YAMLError as e:
        print(f"Error parsing YAML file {CONFIG_FILE}: {e}.")
        sys.exit(1)


SCHOLAR_USER_ID: str = load_scholar_user_id()


def crossref_lookup(title: str) -> dict | None:
    """Query Crossref for the cleanest published record matching a title.

    Scholar's scraped metadata is frequently mangled: diacritics are dropped
    (Çelikok -> Gelikok), surnames merge into one token (Goncalvez Braz ->
    Goncalvezbraz), venues truncate with a literal ellipsis, and pub_url can
    point at the whole proceedings volume rather than the paper. Crossref's
    curated records don't have these problems, so when it returns a
    confident bibliographic match we prefer it.
    """
    try:
        import urllib.parse
        import urllib.request

        q = urllib.parse.urlencode({"query.bibliographic": title, "rows": "3"})
        req = urllib.request.Request(
            f"https://api.crossref.org/works?{q}",
            headers={"User-Agent": "adinlab-site-daemon/1.0 (mailto:kandemir@imada.sdu.dk)"},
        )
        with urllib.request.urlopen(req, timeout=20) as r:
            data = json.loads(r.read().decode("utf-8"))
    except Exception as e:
        print(f"    Crossref lookup failed for '{title[:40]}...': {e}")
        return None

    norm = lambda t: re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", "", t.lower())).strip()
    want = norm(title)
    for item in data.get("message", {}).get("items", []):
        got = norm(item.get("title", [""])[0] if item.get("title") else "")
        if got and (got == want or SequenceMatcher(None, want, got).ratio() >= 0.9):
            return item
    return None
def build_new_entry(filled: dict, existing_keys: set[str], defined_macros: set[str]) -> tuple[str, str] | None:
    """Return (key, bibtex_text) for a newly-discovered publication, or None."""
    bib = filled.get("bib", {})
    title = bib.get("title")
    author_str = bib.get("author")
    year = str(bib.get("pub_year") or "").strip()
    if not title or not author_str or not year:
        print(f"    Missing title/author/year in filled record for '{title}'. Skipping auto-add.")
        return None

    # Prefer Crossref's curated record when one matches the title confidently.
    cr = crossref_lookup(title)
    if cr:
        cr_authors = [f"{a.get('given', '').strip()} {a.get('family', '').strip()}".strip() for a in cr.get("author", [])]
        cr_authors = [a for a in cr_authors if a]
        if len(cr_authors) >= 2:
            author_str = " and ".join(cr_authors)
        cr_title = (cr.get("title") or [""])[0]
        if cr_title:
            title = cr_title
        cr_year = (cr.get("issued", {}).get("date-parts") or [[None]])[0][0]
        if cr_year:
            year = str(cr_year)
        doi = (cr.get("DOI") or "").lower()
        cr_url = f"https://doi.org/{doi}" if doi else ""
        print(f"    Crossref match found: DOI {doi or 'n/a'} - using curated metadata.")

    authors = format_authors(author_str)
    first_author = author_str.split(" and ")[0]
    key = slugify_key(first_author, year, title)
    if key in existing_keys:
        suffix = 2
        while f"{key}{suffix}" in existing_keys:
            suffix += 1
        key = f"{key}{suffix}"

    citation = bib.get("citation", "")
    venue = venue_from_citation(citation)
    if cr:
        containers = cr.get("container-title") or []
        if containers:
            # Crossref lists the series first and the actual venue last; prefer
            # the most specific (last) container.
            venue = containers[-1]
    abstract = (bib.get("abstract") or "").replace("\n", " ").strip()
    if cr and cr_url:
        url = cr_url
    else:
        url = filled.get("pub_url") or filled.get("eprint_url") or ""

    lines = []
    abbr = guess_abbr(venue) if venue else "arXiv"
    if venue:
        is_conference = any(hint in venue.lower() for hint in CONFERENCE_HINTS)
        macro = abbr.lower() if abbr and abbr.lower() in defined_macros else None
        venue_ref = macro if macro else f"{{{venue}}}"
        entry_type = "inproceedings" if is_conference else "article"
        venue_field = "booktitle" if is_conference else "journal"
        lines.append(f"@{entry_type}{{{key},")
        lines.append(f"\tabbr         = {{{abbr or 'arXiv'}}},")
        lines.append(f"\ttitle        = {{{title}}},")
        lines.append(f"\tauthor       = {{{authors}}},")
        lines.append(f"\tyear         = {{{year}}},")
        lines.append(f"\t{venue_field}    = {venue_ref},")
    else:
        lines.append(f"@article{{{key},")
        lines.append("\tabbr         = {arXiv},")
        lines.append(f"\ttitle        = {{{title}}},")
        lines.append(f"\tauthor       = {{{authors}}},")
        lines.append(f"\tyear         = {{{year}}},")
        lines.append("\tjournal      = arxiv,")

    if url:
        lines.append(f"\turl          = {{{url}}},")
        lines.append(f"\thtml         = {{{url}}},")
    lines.append("\tselected     = {false},")
    lines.append("\tbibtex_show  = {true},")
    if abstract:
        lines.append(f"\tabstract     = {{{abstract}}},")
    lines.append("}\n")
    return key, "\n".join(lines)


def get_scholar_citations() -> None:
    """Fetch and update Google Scholar citation data."""
    print(f"Fetching citations for Google Scholar ID: {SCHOLAR_USER_ID}")
    today = datetime.now().strftime("%Y-%m-%d")

    existing_data = None
    if os.path.exists(OUTPUT_FILE):
        try:
            with open(OUTPUT_FILE) as f:
                existing_data = yaml.safe_load(f)
        except Exception as e:
            print(f"Warning: could not read existing citation data from {OUTPUT_FILE}: {e}.")

    with open(BIB_FILE) as f:
        bib_text = f.read()
    bib_titles = load_bib_titles(bib_text)
    existing_keys = {m.group(1) for m in (re.match(r"@\w+\{([^,]+),", e) for _s, _e, e in split_entries(bib_text)) if m}
    defined_macros = known_string_macros(bib_text)
    min_year = earliest_bib_year(bib_text)
    print(f"Only screening for missing publications from {min_year} onward (earliest year already in {BIB_FILE}).")

    citation_data = {"metadata": {"last_updated": today}, "papers": {}}
    new_entries = []  # (key, bibtex_text)

    scholarly.set_timeout(15)
    scholarly.set_retries(3)
    try:
        author = scholarly.search_author_id(SCHOLAR_USER_ID)
        author_data = scholarly.fill(author, sections=["publications"])
    except Exception as e:
        print(f"Error fetching author data from Google Scholar for user ID '{SCHOLAR_USER_ID}': {e}.")
        sys.exit(1)

    if not author_data or "publications" not in author_data:
        print(f"No publications found for user ID '{SCHOLAR_USER_ID}'.")
        sys.exit(1)

    for pub in author_data.get("publications", []):
        try:
            pub_id = pub.get("author_pub_id") or pub.get("pub_id")
            if not pub_id:
                continue
            title = pub.get("bib", {}).get("title", "Unknown Title")
            year = pub.get("bib", {}).get("pub_year", "Unknown Year")
            citations = pub.get("num_citations", 0)
            venue_citation = pub.get("bib", {}).get("citation", "")
            citation_data["papers"][pub_id] = {
                "title": title,
                "year": year,
                "citations": citations,
                "venue_citation": venue_citation,
            }

            if match_title(title, bib_titles) is not None:
                continue  # already in papers.bib (exactly or fuzzily)

            if is_junk_title(title):
                print(f"  '{title[:60]}' looks like a Scholar pseudo-entry. Skipping auto-add.")
                continue

            try:
                year_int = int(str(year).strip())
            except ValueError:
                year_int = None
            if year_int is not None and year_int < min_year:
                continue  # predates the curated era; not our scope to auto-add

            print(f"  '{title}' ({year}) is not in {BIB_FILE} yet. Fetching full record...")
            try:
                filled = scholarly.fill(pub)
            except Exception as e:
                print(f"    Error fetching full record: {e}. Skipping auto-add.")
                continue

            result = build_new_entry(filled, existing_keys, defined_macros)
            if result:
                key, entry_text = result
                existing_keys.add(key)
                bib_titles.append(title.lower())
                new_entries.append((key, entry_text))
                print(f"    Added new entry '{key}'.")
        except Exception as e:
            print(f"Error processing a publication: {e}. Skipped.")

    if new_entries:
        # Insert right after the last @string{...} definition line.
        last_string_end = 0
        for m in re.finditer(r"@string\{[^\n]*\}\n", bib_text):
            last_string_end = m.end()
        insertion = "\n" + "\n".join(text for _key, text in new_entries)
        bib_text = bib_text[:last_string_end] + insertion + bib_text[last_string_end:]
        with open(BIB_FILE, "w") as f:
            f.write(bib_text)
        print(f"Appended {len(new_entries)} new publication(s) to {BIB_FILE}: " + ", ".join(k for k, _t in new_entries))

    if not citation_data["papers"]:
        print("No publications were fetched. Not overwriting existing data.")
        return

    if existing_data and existing_data.get("papers") == citation_data["papers"]:
        print("No changes in citation data.")
        return

    try:
        with open(OUTPUT_FILE, "w") as f:
            yaml.dump(citation_data, f, width=1000, sort_keys=True)
        print(f"Citation data saved to {OUTPUT_FILE}")
    except Exception as e:
        print(f"Error writing citation data to {OUTPUT_FILE}: {e}.")
        sys.exit(1)


if __name__ == "__main__":
    try:
        get_scholar_citations()
    except Exception as e:
        print(f"Unexpected error: {e}")
        sys.exit(1)
