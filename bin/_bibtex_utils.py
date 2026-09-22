"""Shared helpers for reading/matching/rewriting _bibliography/papers.bib.

Used by update_scholar_citations.py (to detect papers missing from the
bibliography and append them) and update_publication_venues.py (to detect
when an existing arXiv-only entry has since been published). Kept in one
place so both scripts match titles the same way.
"""

from __future__ import annotations

import difflib
import re

BIB_FILE = "_bibliography/papers.bib"

# A paper is treated as the "same" paper if its title matches an existing
# entry closely enough - titles do drift (e.g. an arXiv v2 revision renaming
# "Adaptive Ensemble Aggregation for Actor-Critics" to "Directional Ensemble
# Aggregation for Actor-Critics"), and Scholar's cached title can lag behind
# such a rename, so an exact-match-only comparison silently fails to link
# the two. This threshold is intentionally conservative.
FUZZY_MATCH_THRESHOLD = 0.85


def split_entries(text: str) -> list[tuple[int, int, str]]:
    """Return (start, end, entry_text) for every top-level @entry{...} block."""
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
        entries.append((start, j, text[start:j]))
        i = j
    return entries


def entry_key(entry: str) -> str:
    match = re.match(r"@\w+\{([^,]+),", entry)
    return match.group(1) if match else "?"


def extract_field(entry: str, field: str) -> str | None:
    match = re.search(rf"\b{field}\s*=\s*\{{(.*?)\}}\s*,", entry, re.DOTALL)
    return match.group(1).strip() if match else None


def known_string_macros(text: str) -> set[str]:
    return set(re.findall(r"@string\{(\w+)\s*=", text))


def normalize_title(title: str) -> str:
    """Strip BibTeX brace-protection/accent macros so titles compare as plain text."""
    plain = re.sub(r"\{\\[a-zA-Z]\{?([a-zA-Z])\}?\}", r"\1", title)
    plain = plain.replace("{", "").replace("}", "")
    plain = re.sub(r"\s+", " ", plain).strip().lower()
    return plain


def best_title_match(title: str, candidate_titles: list[str]) -> str | None:
    """Return the candidate title matching closely enough, or None."""
    norm = normalize_title(title)
    if norm in candidate_titles:
        return norm
    best, best_ratio = None, 0.0
    for candidate in candidate_titles:
        ratio = difflib.SequenceMatcher(None, norm, candidate).ratio()
        if ratio > best_ratio:
            best, best_ratio = candidate, ratio
    return best if best_ratio >= FUZZY_MATCH_THRESHOLD else None


def load_bib_titles(text: str) -> list[str]:
    titles = []
    for _start, _end, entry in split_entries(text):
        title = extract_field(entry, "title")
        if title:
            titles.append(normalize_title(title))
    return titles


def earliest_bib_year(text: str, default: int = 2000) -> int:
    """Earliest publication year already curated in papers.bib.

    Used to bound automatic "missing publication" detection to the lab's
    actual active era, rather than pulling in a member's entire pre-lab
    Scholar history (old PhD-era papers, unrelated prior affiliations, etc.)
    the first time their profile is screened.
    """
    years = []
    for _start, _end, entry in split_entries(text):
        year = extract_field(entry, "year")
        if year and re.fullmatch(r"\d{4}", year.strip()):
            years.append(int(year.strip()))
    return min(years) if years else default


def guess_abbr(venue: str) -> str | None:
    """Pull a short acronym (e.g. "ICML") off the front of a venue string, if any."""
    first_word = re.match(r"([A-Za-z][A-Za-z&]*)", venue)
    if not first_word:
        return None
    word = first_word.group(1)
    if word.lower() in {"the", "proceedings", "advances", "international", "forensic"}:
        return None  # noise prefix, not an acronym
    if 2 <= len(word) <= 10 and sum(c.isupper() for c in word) >= len(word) // 2:
        return word
    return None


def venue_from_citation(citation: str) -> str | None:
    """Turn Scholar's "Venue Name, 2026" citation string into a venue name."""
    if not citation or "arxiv" in citation.lower():
        return None
    venue = re.sub(r",?\s*\d{4}\s*\.?$", "", citation).strip().rstrip(",").strip()
    return venue or None


def format_authors(scholar_author_str: str) -> str:
    """Convert Scholar's "First Last and First2 Last2" into "Last, F. and Last2, F2."."""
    formatted = []
    for person in scholar_author_str.split(" and "):
        tokens = person.strip().split()
        if len(tokens) < 2:
            formatted.append(person.strip())
            continue
        last = tokens[-1]
        initials = "".join(f"{t[0]}." for t in tokens[:-1] if t)
        formatted.append(f"{last}, {initials}")
    return " and ".join(formatted)


def slugify_key(first_author: str, year: str, title: str) -> str:
    last_name = re.sub(r"[^a-zA-Z]", "", first_author.split()[-1]).lower()
    stopwords = {"a", "an", "the", "on", "of", "for", "in", "to", "with"}
    words = re.findall(r"[a-zA-Z]+", title.lower())
    first_word = next((w for w in words if w not in stopwords), words[0] if words else "paper")
    return f"{last_name}{year}{first_word}"
