"""Citation formatting for Primo records.

Supports APA 7th, Harvard, Chicago, IEEE, and Vancouver styles.
"""

from __future__ import annotations

import re
import unicodedata

from primo_mcp_server.models import PrimoRecord


_CJK_RE = re.compile(r"[\u3400-\u9fff\uf900-\ufaff]")
# Combining marks that join a letter to the next one, as ALA-LC romanisation
# writes Cyrillic "Yu" as I + U+FE20 + U + U+FE21, or as I + U+0361 + U: the
# double diacritics U+035C-U+0362 and the left halves of the half marks.
_JOINING_MARKS = frozenset(
    [chr(code) for code in range(0x035C, 0x0363)] + ["\ufe20", "\ufe22", "\ufe24", "\ufe26"]
)


def _has_cjk(value: str) -> bool:
    """Return true when a name contains CJK characters."""
    return bool(_CJK_RE.search(value))


def _initial(word: str, keep_case: bool = False) -> str:
    """The initial of one given-name word, in capitals unless keep_case.

    A letter keeps the combining marks after it, and a joining mark pulls in
    the next letter too: Posudin's romanised given name (alma9963964836008249
    at Towson), I + U+FE20 + U + U+FE21 + "rii", gives the whole I-U ligature
    as its initial rather than "I".
    """
    letters: list[str] = []
    i = 0
    take_next = True
    while i < len(word) and take_next:
        letters.append(word[i] if keep_case else word[i].upper())
        i += 1
        take_next = False
        while i < len(word) and unicodedata.combining(word[i]):
            letters.append(word[i])
            take_next = take_next or word[i] in _JOINING_MARKS
            i += 1
    return "".join(letters)


def _given_initials(given: str, compact: bool = False) -> str:
    """Initials of a given name, as "J. M." or, when compact, "JM".

    Periods separate names as spaces do, so "J.M." (Lyu in
    cdi_crossref_citationtrail_10_1016_j_compfluid_2020_104786) keeps both
    initials. A hyphenated name keeps its hyphen and the case of its later
    parts, as APA and IEEE write it: "Ken-ichi" gives "K.-i." (Tsubota in
    cdi_crossref_citationtrail_10_1016_j_jmps_2021_104345); compact
    (Vancouver) initials drop the hyphen: "KI".
    """
    names = [name for name in re.split(r"[\s.]+", given) if name]
    if compact:
        return "".join(
            _initial(part) for name in names for part in name.split("-") if part
        )
    initials: list[str] = []
    for name in names:
        parts = [part for part in name.split("-") if part]
        if parts:
            letters = [_initial(parts[0])] + [_initial(p, keep_case=True) for p in parts[1:]]
            initials.append("-".join(f"{letter}." for letter in letters))
    return " ".join(initials)


def _authors_last_initials(creators: list[str]) -> list[str]:
    """Convert 'Last, First' to 'Last, F.' format."""
    result = []
    for c in creators:
        if _has_cjk(c):
            result.append(c.strip())
            continue
        parts = c.split(",", 1)
        if len(parts) == 2:
            last = parts[0].strip()
            initials = _given_initials(parts[1].strip())
            result.append(f"{last}, {initials}" if initials else last)
        else:
            result.append(c.strip())
    return result


def _authors_apa(creators: list[str]) -> str:
    """Format authors in APA 7th style.

    APA puts a comma before the ampersand even for two authors
    ("Li, G., & Koch, D. L.").
    """
    formatted = _authors_last_initials(creators)
    if not formatted:
        return "Unknown author"
    if len(formatted) == 1:
        return formatted[0]
    if len(formatted) <= 20:
        return ", ".join(formatted[:-1]) + ", & " + formatted[-1]
    # 20+ authors: first 19, ..., last
    return ", ".join(formatted[:19]) + ", ... " + formatted[-1]


def _authors_harvard(creators: list[str]) -> str:
    """Format authors in Harvard style: "and" before the last, no serial comma."""
    formatted = _authors_last_initials(creators)
    if not formatted:
        return "Unknown author"
    if len(formatted) == 1:
        return formatted[0]
    if len(formatted) <= 20:
        return ", ".join(formatted[:-1]) + " and " + formatted[-1]
    return ", ".join(formatted[:19]) + ", ... " + formatted[-1]


# Minor words that APA 7 title case keeps in lower case (three letters or
# fewer), plus Latin "et" (Biochimica et Biophysica Acta).
_MINOR_WORDS = frozenset(
    "a an and as at but by et for if in nor of off on or per so the to up via yet".split()
)


def _capitalise(word: str) -> str:
    """Capitalise the first letter of each hyphen-separated part."""
    parts = []
    for part in word.split("-"):
        for i, char in enumerate(part):
            if char.isalpha():
                part = part[:i] + char.upper() + part[i + 1:]
                break
        parts.append(part)
    return "-".join(parts)


def _title_case(text: str) -> str:
    """Title case for a journal name; CDI often stores them in sentence case.

    Only all-lower-case words change, so acronyms and brand forms ("IEEE",
    "PLoS ONE", "eLife") stay as the record has them. Minor words stay in
    lower case except first and after a colon or full stop.
    """
    words = []
    capitalise_next = True
    for word in text.split(" "):
        minor = word.strip(",;:.()").lower() in _MINOR_WORDS
        if word.islower() and (capitalise_next or not minor):
            word = _capitalise(word)
        words.append(word)
        if word:
            capitalise_next = word.endswith((":", ".", "?", "!"))
    return " ".join(words)


def _terminate(text: str) -> str:
    """End text with one period: names ending in an initial already have it."""
    return text if text.endswith((".", "?", "!")) else f"{text}."


def _publisher_with_place(r: PrimoRecord) -> str:
    """Return "Place: Publisher" for the styles that give the place (not APA 7)."""
    place, name = r.place_of_publication, r.publisher_without_place
    if place and name:
        return f"{place}: {name}"
    return name or place


def _authors_chicago(creators: list[str]) -> str:
    """Format authors in Chicago style."""
    formatted = _authors_last_initials(creators)
    if not formatted:
        return "Unknown author"
    if len(formatted) == 1:
        return formatted[0]
    if len(formatted) == 2:
        return f"{formatted[0]} and {formatted[1]}"
    if len(formatted) == 3:
        return ", ".join(formatted[:-1]) + ", and " + formatted[-1]
    return formatted[0] + " et al."


def _authors_ieee(creators: list[str]) -> list[str]:
    """Format authors in IEEE style (F. Last)."""
    result = []
    for c in creators:
        if _has_cjk(c):
            result.append(c.strip())
            continue
        parts = c.split(",", 1)
        if len(parts) == 2:
            last = parts[0].strip()
            initials = _given_initials(parts[1].strip())
            result.append(f"{initials} {last}" if initials else last)
        else:
            result.append(c.strip())
    return result


def _authors_vancouver(creators: list[str]) -> str:
    """Format authors in Vancouver style."""
    formatted = []
    for c in creators:
        if _has_cjk(c):
            formatted.append(c.strip())
            continue
        parts = c.split(",", 1)
        if len(parts) == 2:
            last = parts[0].strip()
            initials = _given_initials(parts[1].strip(), compact=True)
            formatted.append(f"{last} {initials}" if initials else last)
        else:
            formatted.append(c.strip())
    if not formatted:
        return "Unknown author"
    if len(formatted) <= 6:
        return ", ".join(formatted)
    return ", ".join(formatted[:6]) + ", et al"


def _year(record: PrimoRecord) -> str:
    """Extract 4-digit year from creation date."""
    return record.year or "n.d."


def _cite_article_apa(r: PrimoRecord) -> str:
    """APA 7 article citation."""
    authors = _authors_apa(r.display_authors)
    year = _year(r)
    title = r.title.rstrip(".")
    journal = _title_case(r.journal_title)

    parts = [f"{authors} ({year}). {title}."]
    if journal:
        vol_info = f"*{journal}*"
        if r.volume:
            vol_info += f", *{r.volume}*"
        if r.issue:
            vol_info += f"({r.issue})"
        if r.cited_article_number:
            vol_info += f", Article {r.cited_article_number}"
        elif r.start_page:
            vol_info += f", {r.start_page}"
            if r.end_page:
                vol_info += f"-{r.end_page}"
        parts.append(f"{vol_info}.")
    if r.doi:
        parts.append(f"https://doi.org/{r.doi}")
    return " ".join(parts)


def _cite_book_apa(r: PrimoRecord) -> str:
    """APA 7 book citation (APA 7 omits the place of publication)."""
    authors = _authors_apa(r.display_authors)
    year = _year(r)
    title = r.title.rstrip(".")
    publisher = r.publisher_without_place

    parts = [f"{authors} ({year}). *{title}*."]
    if publisher:
        parts.append(f"{publisher}.")
    if r.doi:
        parts.append(f"https://doi.org/{r.doi}")
    return " ".join(parts)


def _cite_article_harvard(r: PrimoRecord) -> str:
    """Harvard article citation."""
    authors = _authors_harvard(r.display_authors)
    year = _year(r)
    title = r.title.rstrip(".")
    journal = _title_case(r.journal_title)

    parts = [f"{authors} ({year}) '{title}',"]
    if journal:
        vol_info = f"*{journal}*"
        if r.volume:
            vol_info += f", vol. {r.volume}"
        if r.issue:
            vol_info += f", no. {r.issue}"
        if r.cited_article_number:
            vol_info += f", article {r.cited_article_number}"
        elif r.start_page:
            vol_info += f", pp. {r.start_page}"
            if r.end_page:
                vol_info += f"-{r.end_page}"
        parts.append(f"{vol_info}.")
    if r.doi:
        parts.append(f"https://doi.org/{r.doi}")
    return " ".join(parts)


def _cite_book_harvard(r: PrimoRecord) -> str:
    """Harvard book citation."""
    authors = _authors_harvard(r.display_authors)
    year = _year(r)
    title = r.title.rstrip(".")
    publisher = _publisher_with_place(r)

    parts = [f"{authors} ({year}) *{title}*,"]
    if publisher:
        parts.append(f"{publisher}.")
    return " ".join(parts)


def _cite_article_chicago(r: PrimoRecord) -> str:
    """Chicago article citation."""
    authors = _authors_chicago(r.display_authors)
    year = _year(r)
    title = r.title.rstrip(".")
    journal = _title_case(r.journal_title)

    parts = [f'{_terminate(authors)} "{title}."']
    if journal:
        vol_info = f"*{journal}*"
        if r.volume:
            vol_info += f" {r.volume}"
        if r.issue:
            vol_info += f", no. {r.issue}"
        parts.append(f"{vol_info} ({year})")
        if r.cited_article_number:
            parts[-1] += f": {r.cited_article_number}"
        elif r.start_page:
            start = r.start_page
            if r.end_page:
                start += f"-{r.end_page}"
            parts[-1] += f": {start}"
        parts[-1] += "."
    else:
        # Without a journal title the year was previously dropped entirely,
        # since it was only emitted inside the journal block.
        parts.append(f"{year}.")
    if r.doi:
        parts.append(f"https://doi.org/{r.doi}")
    return " ".join(parts)


def _cite_book_chicago(r: PrimoRecord) -> str:
    """Chicago book citation."""
    authors = _authors_chicago(r.display_authors)
    year = _year(r)
    title = r.title.rstrip(".")
    publisher = _publisher_with_place(r)

    parts = [f"{_terminate(authors)} *{title}*."]
    if publisher:
        parts.append(f"{publisher}, {year}.")
    else:
        parts.append(f"{year}.")
    return " ".join(parts)


def _join_ieee(authors_list: list[str]) -> str:
    """Join IEEE-style names: "A and B", "A, B, and C", "A et al."."""
    if not authors_list:
        return "Unknown author"
    if len(authors_list) == 1:
        return authors_list[0]
    if len(authors_list) == 2:
        return f"{authors_list[0]} and {authors_list[1]}"
    if len(authors_list) == 3:
        return ", ".join(authors_list[:-1]) + ", and " + authors_list[-1]
    return authors_list[0] + " et al."


def _cite_article_ieee(r: PrimoRecord) -> str:
    """IEEE article citation."""
    authors_str = _join_ieee(_authors_ieee(r.display_authors))

    title = r.title.rstrip(".")
    journal = _title_case(r.journal_title)
    year = _year(r)

    parts = [f'{authors_str}, "{title},"']
    if journal:
        vol_info = f"*{journal}*"
        if r.volume:
            vol_info += f", vol. {r.volume}"
        if r.issue:
            vol_info += f", no. {r.issue}"
        if r.cited_article_number:
            vol_info += f", Art. no. {r.cited_article_number}"
        elif r.start_page:
            vol_info += f", pp. {r.start_page}"
            if r.end_page:
                vol_info += f"-{r.end_page}"
        parts.append(f"{vol_info}, {year}.")
    else:
        # Without a journal title the year was previously dropped entirely,
        # since it was only emitted inside the journal block.
        parts.append(f"{year}.")
    if r.doi:
        parts.append(f"doi: {r.doi}.")
    return " ".join(parts)


def _cite_book_ieee(r: PrimoRecord) -> str:
    """IEEE book citation (authors joined as for articles)."""
    authors_str = _join_ieee(_authors_ieee(r.display_authors))

    title = r.title.rstrip(".")
    publisher = _publisher_with_place(r)
    year = _year(r)

    parts = [f"{authors_str}, *{title}*."]
    if publisher:
        parts.append(f"{publisher}, {year}.")
    else:
        parts.append(f"{year}.")
    return " ".join(parts)


def _cite_article_vancouver(r: PrimoRecord) -> str:
    """Vancouver article citation."""
    authors = _authors_vancouver(r.display_authors)
    title = r.title.rstrip(".")
    journal = r.journal_title or ""
    year = _year(r)

    parts = [f"{_terminate(authors)} {title}."]
    if journal:
        vol_info = f"{journal}. {year}"
        if r.volume:
            vol_info += f";{r.volume}"
        if r.issue:
            vol_info += f"({r.issue})"
        if r.cited_article_number:
            vol_info += f":{r.cited_article_number}"
        elif r.start_page:
            vol_info += f":{r.start_page}"
            if r.end_page:
                vol_info += f"-{r.end_page}"
        parts.append(f"{vol_info}.")
    else:
        # Without a journal title the year was previously dropped entirely,
        # since it was only emitted inside the journal block.
        parts.append(f"{year}.")
    if r.doi:
        parts.append(f"doi:{r.doi}")
    return " ".join(parts)


def _cite_book_vancouver(r: PrimoRecord) -> str:
    """Vancouver book citation."""
    authors = _authors_vancouver(r.display_authors)
    title = r.title.rstrip(".")
    publisher = _publisher_with_place(r)
    year = _year(r)

    parts = [f"{_terminate(authors)} {title}."]
    if publisher:
        parts.append(f"{publisher}; {year}.")
    else:
        parts.append(f"{year}.")
    return " ".join(parts)


_STYLE_MAP = {
    "apa7": {"article": _cite_article_apa, "book": _cite_book_apa},
    "harvard": {"article": _cite_article_harvard, "book": _cite_book_harvard},
    "chicago": {"article": _cite_article_chicago, "book": _cite_book_chicago},
    "ieee": {"article": _cite_article_ieee, "book": _cite_book_ieee},
    "vancouver": {"article": _cite_article_vancouver, "book": _cite_book_vancouver},
}

CITATION_STYLES = tuple(_STYLE_MAP)


def invalid_style_message(style: str) -> str | None:
    """Caller-facing error for an unsupported style, or None when valid."""
    if style.strip().lower() in _STYLE_MAP:
        return None
    return (
        f'Invalid citation style "{style}". '
        f"Use one of: {', '.join(sorted(CITATION_STYLES))}"
    )


def _record_type_key(resource_type: str) -> str:
    """Normalise Primo record type labels for citation routing."""
    return resource_type.strip().lower().replace("-", "_")


def format_citation(record: PrimoRecord, style: str = "apa7") -> str:
    """Format a citation for a record in the specified style."""
    style = style.strip().lower()
    style_funcs = _STYLE_MAP.get(style, _STYLE_MAP["apa7"])

    # Determine if article or book
    rtype = _record_type_key(record.resource_type)
    if rtype in (
        "article",
        "articles",
        "review",
        "reviews",
        "newspaper_article",
        "newspaper_articles",
    ):
        func = style_funcs["article"]
    else:
        func = style_funcs["book"]

    return func(record)
