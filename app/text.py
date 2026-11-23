"""Text helpers that keep the slugs the original produced.

``slugify`` reproduces the normalisation the previous stack applied when a
company, job or category saved itself, so stored slugs stay comparable.
"""
from __future__ import annotations

import re
import unicodedata

_NON_WORD = re.compile(r"[^\w\s-]")
_NON_WORD_UNICODE = re.compile(r"[^\w\s-]", re.UNICODE)
_SPACES = re.compile(r"[-\s]+")


def slugify(value, allow_unicode: bool = False) -> str:
    """Lower-case, strip accents and punctuation, and join words with hyphens."""
    value = str(value)
    if allow_unicode:
        value = unicodedata.normalize("NFKC", value)
        value = _NON_WORD_UNICODE.sub("", value).strip().lower()
    else:
        value = (
            unicodedata.normalize("NFKD", value)
            .encode("ascii", "ignore")
            .decode("ascii")
        )
        value = _NON_WORD.sub("", value).strip().lower()
    return _SPACES.sub("-", value)
