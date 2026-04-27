"""Arabic text helpers for normalization."""

import unicodedata


def normalize_arabic_text(text: str) -> str:
    """Normalize Arabic text without changing semantic content."""

    return unicodedata.normalize("NFC", " ".join(text.split()))
