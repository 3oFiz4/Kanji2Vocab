# file: kanji2vocab/services/scraper.py
import random
import requests
from bs4 import BeautifulSoup

from ..models import KanjiInfo, ScrapePageResult, VocabItem
from .formatter import Formatter
from .logger import Logger


class VocabFilter:
    """Filters vocab entries based on learned characters."""
    def __init__(self, learned_set: set[str]) -> None:
        # Store the learned character set.
        self.learned_set = learned_set

    def set_learned_set(self, learned_set: set[str]) -> None:
        """Update the learned character set."""
        # Replace internal set with new one.
        self.learned_set = learned_set

    def is_valid(self, vocab: str, target_kanji: str) -> bool:
        """Check if vocab contains target kanji and uses learned chars."""
        # Reject empty vocab.
        if not vocab:
            return False
        # Ensure target kanji exists in vocab.
        if target_kanji not in vocab:
            return False
        # Verify all other characters are learned.
        for ch in vocab:
            if ch != target_kanji and ch not in self.learned_set:
                return False
        # All checks passed.
        return True


class JishoScraper:
    """Scrapes Jisho.org for kanji vocab and metadata."""
    def __init__(
        self,
        base_url_template: str,
        formatter: Formatter,
        logger: Logger,
        vocab_filter: VocabFilter,
        is_tag_shortened: bool = True,
        is_meaning_shortened: bool = True,
        is_colored: bool = True,
    ) -> None:
        # Store base URL template.
        self.base_url_template = base_url_template
        # Store formatter for parsing/formatting.
        self.formatter = formatter
        # Store logger for error reporting.
        self.logger = logger
        # Store vocab filter.
        self.vocab_filter = vocab_filter
        # Store formatting flags.
        self.is_tag_shortened = is_tag_shortened
        self.is_meaning_shortened = is_meaning_shortened
        self.is_colored = is_colored
        # Prepare a list of user agents for rotation.
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.93 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.4389.82 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/88.0.4324.150 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/87.0.4280.141 Safari/537.36",
        ]

    def update_settings(
        self,
        base_url_template: str | None = None,
        is_tag_shortened: bool | None = None,
        is_meaning_shortened: bool | None = None,
        is_colored: bool | None = None,
    ) -> None:
        """Update scraper settings without rebuilding the object."""
        # Update base URL template if provided.
        if base_url_template is not None:
            self.base_url_template = base_url_template
        # Update flags if provided.
        if is_tag_shortened is not None:
            self.is_tag_shortened = is_tag_shortened
        if is_meaning_shortened is not None:
            self.is_meaning_shortened = is_meaning_shortened
        if is_colored is not None:
            self.is_colored = is_colored

    def _build_url(self, kanji: str, page: int) -> str:
        """Build the Jisho search URL for a given page."""
        # Insert kanji into the base URL template.
        base = self.base_url_template.format(Kanji=kanji)
        # Append pagination parameter.
        return f"{base}?page={page}"

    def _parse_kanji_info(self, soup: BeautifulSoup) -> KanjiInfo:
        """Parse kanji metadata from the first page."""
        # Locate the kanji content container.
        target = soup.select_one("div.kanji_light_content")
        # Return empty info if not found.
        if not target:
            return KanjiInfo.empty()

        # Select specific kanji info elements.
        scr_onyomi = target.select_one("div.on.readings")
        scr_kunyomi = target.select_one("div.kun.readings")
        scr_meaning = target.select_one("div.meanings.english.sense")
        scr_info = target.select_one("div.info.clearfix")

        # Remove <a> tags to simplify text.
        if scr_onyomi:
            for a in scr_onyomi.find_all("a", recursive=True):
                a.unwrap()
        if scr_kunyomi:
            for a in scr_kunyomi.find_all("a", recursive=True):
                a.unwrap()

        # Extract text fields.
        kanji_onyomi = scr_onyomi.get_text(strip=True, separator="") if scr_onyomi else ""
        kanji_kunyomi = scr_kunyomi.get_text(strip=True, separator="") if scr_kunyomi else ""
        kanji_meaning = scr_meaning.get_text(strip=True, separator="") if scr_meaning else ""
        kanji_info = scr_info.get_text(strip=True, separator="") if scr_info else ""

        # Return structured KanjiInfo.
        return KanjiInfo(
            info=kanji_info,
            onyomi=kanji_onyomi,
            kunyomi=kanji_kunyomi,
            meaning=kanji_meaning,
        )

    def scrape_page(self, kanji: str, page: int) -> ScrapePageResult:
        """Scrape a single Jisho page for vocab entries."""
        # Build request headers with a random user agent.
        headers = {"User-Agent": random.choice(self.user_agents)}

        # Build URL for the requested page.
        url = self._build_url(kanji, page)

        # Execute the HTTP request.
        response = requests.get(url, headers=headers, timeout=20)
        response.raise_for_status()

        # Parse the HTML document.
        try:
            soup = BeautifulSoup(response.content, "lxml")
        except Exception:
            soup = BeautifulSoup(response.content, "html.parser")

        # Detect next-page availability.
        has_next = bool(soup.select_one("a.more"))

        # Collect the vocab-related elements.
        characters = soup.select(
            "div.concept_light-readings.japanese.japanese_gothic > div.concept_light-representation"
        )
        meanings = soup.select("div.meanings-wrapper")
        tags = soup.select("div.concept_light-status")

        # Parse kanji info on the first page only.
        kanji_info = self._parse_kanji_info(soup) if page == 1 else None

        # Prepare results list and counters.
        items: list[VocabItem] = []
        total_scraped = 0

        # Iterate through vocab blocks together.
        for char_el, meaning_el, tag_el in zip(characters, meanings, tags):
            # Extract vocab text and furigana.
            text_el = char_el.select_one("span.text")
            furi_el = char_el.select_one("span.furigana")

            scr_vocab = text_el.get_text(strip=True) if text_el else None
            scr_furi = furi_el.get_text(strip=True) if furi_el else None

            # Count all scraped entries.
            total_scraped += 1

            # Skip invalid or missing entries.
            if not scr_vocab or not scr_furi:
                continue

            # Filter by learned set and target kanji.
            if not self.vocab_filter.is_valid(scr_vocab, kanji):
                continue

            # Extract tag contents.
            tag_contents = [t.get_text(strip=True) for t in tag_el.select(".concept_light-tag.label") if t]
            tag_contents = [t for t in tag_contents if t]

            # Join tags and optionally shorten.
            tag_text = ", ".join(tag_contents)
            if self.is_tag_shortened:
                tag_text = self.formatter.shortify_tag(tag_text)

            # Format meanings and optionally shorten.
            meaning_list = self.formatter.format_meaning(meaning_el)
            if self.is_meaning_shortened:
                meaning_text = self.formatter.shortify_meaning(meaning_list)
            else:
                meaning_text = self.formatter.join_meanings(meaning_list)

            # Colorize furigana if enabled and kanji info available.
            furi_colored = self.formatter.parse_color(scr_furi, kanji_info, self.is_colored)

            # Append vocab item.
            items.append(
                VocabItem(
                    vocab=scr_vocab,
                    furigana=furi_colored,
                    meaning=meaning_text,
                    tag=tag_text,
                )
            )

        # Return page scrape result.
        return ScrapePageResult(
            items=items,
            has_next=has_next,
            total_scraped=total_scraped,
            kanji_info=kanji_info,
        )