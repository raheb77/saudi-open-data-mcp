"""Shared parsing for stats.gov.sa news/release-card HTML pages."""

from __future__ import annotations

from dataclasses import dataclass, field
from html.parser import HTMLParser


@dataclass(slots=True)
class StatsGovSaReleaseCard:
    """Parsed stats.gov.sa release-card fragments used by narrow dataset extractors."""

    title_chunks: list[str] = field(default_factory=list)
    date_chunks: list[str] = field(default_factory=list)
    summary_chunks: list[str] = field(default_factory=list)
    release_url: str | None = None

    @property
    def title(self) -> str:
        return " ".join(self.title_chunks).strip()

    @property
    def release_date_text(self) -> str:
        return " ".join(self.date_chunks).strip()

    @property
    def summary_text(self) -> str:
        return " ".join(self.summary_chunks).strip()


class StatsGovSaReleaseCardParser(HTMLParser):
    """Parse the repeated release-card HTML structure used by stats.gov.sa news pages."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.cards: list[StatsGovSaReleaseCard] = []
        self._current_card: StatsGovSaReleaseCard | None = None
        self._card_div_depth = 0
        self._capture_title = False
        self._capture_date = False
        self._summary_div_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = {name: value or "" for name, value in attrs}
        class_names = _class_names(attributes.get("class"))

        if tag == "div" and {"card", "card-box", "media-card"}.issubset(class_names):
            if self._current_card is None:
                self._current_card = StatsGovSaReleaseCard()
                self._card_div_depth = 1
            else:
                self._card_div_depth += 1
            return

        if self._current_card is None:
            return

        if tag == "div":
            self._card_div_depth += 1
            if "card-text" in class_names:
                self._summary_div_depth += 1
            return

        if tag == "h3" and "card-title" in class_names:
            self._capture_title = True
            return

        if tag == "p" and "card-date" in class_names:
            self._capture_date = True
            return

        if tag == "a":
            href = attributes.get("href", "").strip()
            if href.startswith("http") and "/en/w/" in href:
                self._current_card.release_url = href

    def handle_data(self, data: str) -> None:
        if self._current_card is None:
            return

        text = " ".join(data.split())
        if not text:
            return

        if self._capture_title:
            self._current_card.title_chunks.append(text)
        elif self._capture_date:
            self._current_card.date_chunks.append(text)
        elif self._summary_div_depth > 0:
            self._current_card.summary_chunks.append(text)

    def handle_endtag(self, tag: str) -> None:
        if self._current_card is None:
            return

        if tag == "h3":
            self._capture_title = False
            return

        if tag == "p":
            self._capture_date = False
            return

        if tag == "div":
            if self._summary_div_depth > 0:
                self._summary_div_depth -= 1
            self._card_div_depth -= 1
            if self._card_div_depth == 0:
                self.cards.append(self._current_card)
                self._current_card = None


def _class_names(class_value: str | None) -> set[str]:
    if not class_value:
        return set()
    return {name for name in class_value.split() if name}
