"""Saudi Arabic content handling tests."""

from __future__ import annotations

import json
import unicodedata

from saudi_open_data_mcp.normalization import normalize_arabic_text


def test_arabic_content_normalization_outputs_nfc_and_preserves_diacritics() -> None:
    raw_text = "المملكة  العربية  ا\u0653لسُّعُودِيَّة"
    expected = unicodedata.normalize("NFC", "المملكة العربية آلسُّعُودِيَّة")

    normalized = normalize_arabic_text(raw_text)

    assert unicodedata.is_normalized("NFC", normalized)
    assert normalized == expected
    assert _combining_marks(normalized) == _combining_marks(expected)


def test_arabic_content_json_serialization_preserves_rtl_text() -> None:
    title = normalize_arabic_text("مؤشر  أسعار  المستهلك")
    payload = {
        "dataset_id": "stats-gov-sa-cpi-headline-monthly",
        "title": title,
        "source": "GASTAT",
    }

    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    restored = json.loads(serialized)

    assert "مؤشر أسعار المستهلك" in serialized
    assert "\\u" not in serialized
    assert restored["title"] == title


def _combining_marks(value: str) -> list[str]:
    return [character for character in value if unicodedata.combining(character)]
