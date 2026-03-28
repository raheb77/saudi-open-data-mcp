"""Arabic text helpers for normalization."""


def normalize_arabic_text(text: str) -> str:
    """Normalize whitespace without changing semantic content."""

    return " ".join(text.split())
