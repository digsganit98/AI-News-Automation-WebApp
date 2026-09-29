"""English only: items written in another language are dropped at collection.

A small, dependency-free check on the title and summary:
- mostly non-Latin letters (Devanagari, Chinese, Korean, Arabic, Cyrillic...) -> not English
- several letters English almost never uses (ñ, ç, ğ, ı, ü...) -> not English
- more common Spanish/Portuguese/French/German/Italian/Dutch/Turkish words than English
  ones -> not English
Short or ambiguous text (e.g. just a model name) counts as English.
"""

from __future__ import annotations

import re

from digest.dataModels import RawItem


def wordSet(text: str) -> set[str]:
    return set(text.split())


ENGLISH = wordSet(
    "the of and to in is are for with on that this from by as be at it its was were has have "
    "new how what why who which will can you your we our their not or an into about more than "
    "using based model models"
)
# Single letters (Spanish "y", Portuguese "o") and "com" are left out: "Y Combinator", ".com".
OTHER = (
    wordSet(
        # Spanish / Portuguese
        "el la los las del de en un una para por con que es se al lo como más pero sus "
        "os da das do dos em uma não são mais "
        # French
        "le les des du et est une pour dans sur avec qui ce cette sont au aux pas "
        # German
        "der die das und ist ein eine mit für auf nicht sich den dem zu von im "
        # Italian / Dutch
        "il gli della delle di che sono una nel het een van zijn voor niet "
        # Turkish / Indonesian
        "ve bir ile bu için olan daha yang dan di untuk dengan adalah"
    )
    - ENGLISH
)
# Letters that English text almost never uses (names aside).
_FOREIGN = "áàâãäåçéèêëíìîïñóòôõöúùûüýÿßıİğĞşŞœæøąęłńśźżčřšžőű"
# Upper case too, but never plain ASCII ("ı".upper() is "I", "ß".upper() is "SS").
FOREIGN_LETTERS = {c for letter in _FOREIGN for c in (letter, letter.upper()) if not c.isascii()}
WORD = re.compile(r"[a-zà-öø-ÿœß]+")


def isEnglish(text: str) -> bool:
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return True
    nonLatin = sum(1 for c in letters if ord(c) > 0x24F)
    if nonLatin / len(letters) > 0.2:
        return False
    accented = sum(1 for c in letters if c in FOREIGN_LETTERS)
    if accented >= 4 and accented / len(letters) > 0.02:
        return False
    words = WORD.findall(text.lower())
    english = sum(w in ENGLISH for w in words)
    other = sum(w in OTHER for w in words)
    return not (other >= 3 and other > english)


def keepEnglish(items: list[RawItem]) -> list[RawItem]:
    return [i for i in items if isEnglish(f"{i.title} {i.excerpt}")]
