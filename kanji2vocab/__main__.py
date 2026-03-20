# file: kanji2vocab/__main__.py
import os
import sys
import asyncio
import pyperclip

from .services.utils import load_env
from .services.logger import Logger
from .services.formatter import Formatter
from .services.scraper import JishoScraper, VocabFilter
from .services.pagination import PaginationHandler
from .services.stroke import StrokeScraper
from .services.ai import APIKeyRotator, AIClient
from .services.anki import AnkiInteractor, AnkiClient
from .services.ui import ConsoleUI
from .config import ConfigManager
from .cli import parse_cli
from .controller import AppController


async def main() -> None:
    """Main entry point for the application."""
    # Load environment variables from .env.
    load_env()

    # Initialize logger and config manager.
    logger = Logger()
    config_manager = ConfigManager("config.json", logger)

    # Load initial config.
    config = config_manager.load()

    # Initialize formatter and UI.
    formatter = Formatter()
    ui = ConsoleUI(logger, formatter)

    # Initialize vocab filter and scraper.
    vocab_filter = VocabFilter(set(config.has_learned))
    scraper = JishoScraper(
        base_url_template=config.base_url,
        formatter=formatter,
        logger=logger,
        vocab_filter=vocab_filter,
        is_tag_shortened=config.is_tag_shortened,
        is_meaning_shortened=config.is_meaning_shortened,
        is_colored=config.is_colored,
    )

    # Initialize pagination handler.
    paginator = PaginationHandler(scraper, logger)

    # Initialize stroke scraper.
    stroke_scraper = StrokeScraper(logger)

    # Initialize AI client with rotating keys.
    ai_rotator = APIKeyRotator([0, 1], logger)
    ai_client = AIClient(ai_rotator, os.getenv("AI_URL"), os.getenv("AI_MODEL"), logger)

    # Initialize Anki client.
    anki_interactor = AnkiInteractor(logger=logger)
    anki_client = AnkiClient(anki_interactor, config.anki_deck, logger)
    logger.log("AnkiAPI Connected", "s")

    # Build controller.
    controller = AppController(
        config_manager=config_manager,
        logger=logger,
        formatter=formatter,
        ui=ui,
        scraper=scraper,
        paginator=paginator,
        stroke_scraper=stroke_scraper,
        ai_client=ai_client,
        anki_client=anki_client,
        vocab_filter=vocab_filter,
        clipboard=pyperclip,
        initial_config=config,
    )

    # Parse CLI arguments and dispatch.
    args = parse_cli(sys.argv)
    await controller.dispatch(args)


if __name__ == "__main__":
    # Run the async main entry point.
    asyncio.run(main())