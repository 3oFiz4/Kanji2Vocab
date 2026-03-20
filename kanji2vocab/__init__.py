# file: kanji2vocab/__init__.py
"""
Design reasoning (OOP layout):

Data Objects:
- AppConfig: configuration and persistence mapping.
- KanjiInfo: kanji metadata scraped once per search.
- VocabItem: vocabulary entry (vocab, furigana, meaning, tag).
- ScrapePageResult / PaginationResult / CLIArgs: transport structures.

Logic Classes:
- Formatter: meaning/tag/markup normalization and color conversion.
- VocabFilter + JishoScraper: fetch and parse data from Jisho.
- PaginationHandler: sequential/concurrent scraping orchestration.
- StrokeScraper: fetch kanji stroke SVG.
- APIKeyRotator + AIClient: AI request and key rotation.
- AnkiInteractor + AnkiClient: AnkiConnect API wrapper.
- ConsoleUI: input/output and selection workflows.
- ConfigManager: config I/O and mutations.

Controller:
- AppController: application orchestration and state management.
- CLI parser and main entry points route user intents to controller.

Files are organized around these objects to keep state localized and
responsibilities separated (Data → Logic → Controller).
"""
__all__ = ["__version__"]
__version__ = "2.0.0"