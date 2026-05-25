"""Detection de langue basée sur l'alphabet (AR vs FR).

Robuste car les deux alphabets ne se chevauchent pas. Pas de dépendance externe.
"""

# Arabic Unicode block U+0600..U+06FF (couvre l'arabe standard + diacritiques)
_AR_START = "؀"
_AR_END = "ۿ"


def detect_lang(text: str) -> str:
    """Retourne 'ar' ou 'fr'. Défaut 'ar' si ambigu (préserve le comportement actuel)."""
    ar_count = sum(1 for c in text if _AR_START <= c <= _AR_END)
    latin_count = sum(1 for c in text if c.isascii() and c.isalpha())
    if latin_count > ar_count:
        return "fr"
    return "ar"
