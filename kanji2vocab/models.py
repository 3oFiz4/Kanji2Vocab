# file: kanji2vocab/models.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class AppConfig:
    """Holds application configuration and preserves unknown keys."""
    base_url: str = ""
    has_learned: list[str] = field(default_factory=list)
    template: str = ""
    template_kanji: str = ""
    pagination_limit: int = 10
    is_template: bool = True
    is_tag_shortened: bool = True
    is_meaning_shortened: bool = True
    anki_deck: str = ""
    anki_model_vocab: str = ""
    anki_model_kanji: str = ""
    vocab_method: str = "a"
    is_colored: bool = True
    is_automatic: bool = False
    is_ai: bool = True
    extra: dict[str, Any] = field(default_factory=dict)
    
    #TODO: Add additional configuration for others. e.g., isAI

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AppConfig":
        """Build AppConfig from a raw dict while preserving unknown keys."""
        # Copy data to avoid mutating caller state.
        raw = dict(data)

        # Extract known keys with defaults.
        base_url = raw.pop("BaseUrl", "")
        has_learned = raw.pop("hasLearned", "")
        template = raw.pop("Template", "")
        template_kanji = raw.pop("TemplateKanji", "")
        pagination_limit = raw.pop("PaginationLimit", 10)
        is_template = raw.pop("isTemplate", True)
        is_tag_shortened = raw.pop("isTagShortened", True)
        is_meaning_shortened = raw.pop("isMeaningShortened", True)
        anki_deck = raw.pop("AnkiDeck", "")
        anki_model_vocab = raw.pop("AnkiModelVocabulary", "")
        anki_model_kanji = raw.pop("AnkiModelKanji", "")
        vocab_method = raw.pop("VocabularyMethod", "a")
        is_colored = raw.pop("isColored", True)
        is_automatic = raw.pop("isAutomatic", False)
        is_ai = raw.pop("isAi", True)

        # Normalize has_learned into a list of characters.
        if isinstance(has_learned, list):
            learned_list = [str(x) for x in has_learned]
        else:
            learned_list = list(str(has_learned))

        # Store remaining keys as extras.
        extra = raw

        # Return structured config.
        return cls(
            base_url=base_url,
            has_learned=learned_list,
            template=template,
            template_kanji=template_kanji,
            pagination_limit=pagination_limit,
            is_template=is_template,
            is_tag_shortened=is_tag_shortened,
            is_meaning_shortened=is_meaning_shortened,
            anki_deck=anki_deck,
            anki_model_vocab=anki_model_vocab,
            anki_model_kanji=anki_model_kanji,
            vocab_method=vocab_method,
            is_colored=is_colored,
            is_automatic=is_automatic,
            is_ai=is_ai,
            extra=extra
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert AppConfig back to a dict while preserving unknown keys."""
        # Build the known-key payload.
        payload = {
            "BaseUrl": self.base_url,
            "hasLearned": "".join(self.has_learned),
            "Template": self.template,
            "TemplateKanji": self.template_kanji,
            "PaginationLimit": self.pagination_limit,
            "isTemplate": self.is_template,
            "isTagShortened": self.is_tag_shortened,
            "isMeaningShortened": self.is_meaning_shortened,
            "AnkiDeck": self.anki_deck,
            "AnkiModelVocabulary": self.anki_model_vocab,
            "AnkiModelKanji": self.anki_model_kanji,
            "VocabularyMethod": self.vocab_method,
            "isColored": self.is_colored,
            "isAutomatic": self.is_automatic,
            "isAi": self.is_ai
        }

        # Merge extra keys, letting known keys override if conflicts exist.
        return {**self.extra, **payload}


@dataclass
class KanjiInfo:
    """Represents kanji metadata from Jisho."""
    info: str = ""
    onyomi: str = ""
    kunyomi: str = ""
    meaning: str = ""

    @classmethod
    def empty(cls) -> "KanjiInfo":
        """Return an empty KanjiInfo object."""
        # Return a default instance with empty fields.
        return cls()


@dataclass
class VocabItem:
    """Represents a single vocabulary entry."""
    vocab: str
    furigana: str
    meaning: str
    tag: str


@dataclass
class ScrapePageResult:
    """Represents scrape results for a single page."""
    items: list[VocabItem]
    has_next: bool
    total_scraped: int
    kanji_info: Optional[KanjiInfo] = None


@dataclass
class PaginationResult:
    """Represents merged pagination results."""
    items: list[VocabItem]
    kanji_info: KanjiInfo


@dataclass
class CLIArgs:
    """Represents parsed command-line arguments."""
    action: str
    kanji: Optional[str] = None
    total_pages: Optional[int] = None
    method: Optional[str] = None