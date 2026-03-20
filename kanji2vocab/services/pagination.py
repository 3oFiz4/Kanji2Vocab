# file: kanji2vocab/services/pagination.py
import time
import threading
import concurrent.futures
from rich.table import Table
from rich.live import Live

from ..models import KanjiInfo, PaginationResult
from .logger import Logger
from .scraper import JishoScraper


class PaginationHandler:
    """Handles sequential and concurrent pagination for scraping."""
    def __init__(self, scraper: JishoScraper, logger: Logger) -> None:
        # Store scraper instance.
        self.scraper = scraper
        # Store logger instance.
        self.logger = logger

    def sequential(self, kanji: str, pages: int) -> PaginationResult:
        """Scrape pages sequentially and merge results."""
        # Initialize the live table for progress display.
        table = Table()
        table.add_column("Pagination Step", justify="center", style="#00ffff bold")
        table.add_column("Total Scraped", justify="center", style="#ffffff bold")
        table.add_column("Next Pagination", justify="center", style="#00ff00 bold")

        # Initialize results and kanji info.
        merged = []
        kanji_info = KanjiInfo.empty()

        # Use Live to update the table in-place.
        with Live(table, refresh_per_second=1):
            # Iterate through each page.
            for page in range(1, pages + 1):
                try:
                    # Scrape the current page.
                    result = self.scraper.scrape_page(kanji, page)
                except Exception as e:
                    # Log the error and stop sequential scraping.
                    self.logger.log(f"Failure.\nError: {str(e)}", "f")
                    break

                # Store kanji info if present.
                if result.kanji_info:
                    kanji_info = result.kanji_info

                # Update table with counts.
                table.add_row(
                    f"{page}",
                    f"[green]{len(result.items)}[/]/[red]{result.total_scraped}[/]",
                    f"{result.has_next}",
                )

                # Merge results.
                merged.extend(result.items)

                # Stop if no next pagination.
                if not result.has_next:
                    break

        # Return combined results.
        return PaginationResult(items=merged, kanji_info=kanji_info)

    def concurrent(self, kanji: str, pages: int, max_workers: int = 10) -> PaginationResult:
        """Scrape pages concurrently with retries and merge results."""
        # Initialize the live table for progress display.
        table = Table()
        table.add_column("Pagination Step", justify="center", style="#00ffff bold")
        table.add_column("Total Scraped", justify="center", style="#ffffff bold")
        table.add_column("Next Pagination", justify="center", style="#00ff00 bold")

        # Thread-safe lock for table updates.
        lock = threading.Lock()

        # Store merged results and kanji info.
        merged = []
        kanji_info = KanjiInfo.empty()

        # Event to request stopping remaining tasks.
        stop_event = threading.Event()

        def scrape_with_retry(page: int, retries: int = 3, backoff_factor: int = 1):
            """Wrapper to scrape a page with exponential backoff retries."""
            # Retry up to the configured number of attempts.
            for attempt in range(retries):
                try:
                    # Attempt to scrape the page.
                    return (page, self.scraper.scrape_page(kanji, page))
                except Exception:
                    # If not the last attempt, sleep before retrying.
                    if attempt < retries - 1:
                        time.sleep(backoff_factor * (2 ** attempt))
                    else:
                        # Return a sentinel for failure.
                        return (page, None)

        # Initialize state variables to prevent UnboundLocalError and track progress
        kanji_info = None
        successful_pages = set()
        max_required_page = pages  # Defaults to the max requested pages

        # Use Live to update the table in-place.
        with Live(table, refresh_per_second=2):
            # Launch concurrent tasks.
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_to_page = {
                    executor.submit(scrape_with_retry, page): page for page in range(1, pages + 1)
                }

                # Collect results as tasks complete.
                for future in concurrent.futures.as_completed(future_to_page):
                    page = future_to_page[future]

                    try:
                        # Unpack future result.
                        page_num, result = future.result()
                    except concurrent.futures.CancelledError:
                        # Future was successfully cancelled (likely out of bounds), safely ignore.
                        continue
                    except Exception:
                        # Handle unexpected errors.
                        with lock:
                            table.add_row(str(page), "[red]Timeout![/]", "Unknown")
                        continue

                    # Handle failed scrape attempts.
                    if result is None:
                        with lock:
                            table.add_row(str(page_num), "[red]Timeout![/]", "Unknown")
                        continue

                    # Update shared state under lock.
                    with lock:
                        # Ignore results from pages that are beyond the known last page
                        if page_num > max_required_page:
                            continue

                        # Mark this page as successfully scraped
                        successful_pages.add(page_num)

                        # Store kanji info if present.
                        if result.kanji_info:
                            kanji_info = result.kanji_info

                        # Update the live table.
                        table.add_row(
                            str(page_num),
                            f"[green]{len(result.items)}[/]/[red]{result.total_scraped}[/]",
                            "Yes" if result.has_next else "No",
                        )

                        # Merge items.
                        merged.extend(result.items)

                        # If no further pages, request stop and cancel remaining futures.
                        if not result.has_next:
                            stop_event.set()
                            # Cap the max pages we care about so we don't retry beyond this point
                            max_required_page = min(max_required_page, page_num)
                            for f in future_to_page:
                                f.cancel()

            # FINAL PASS: Replicating Code 2's intent to catch missed/timed-out pages.
            # Ensure all pages up to the last valid page are successfully scraped.
            for page in range(1, max_required_page + 1):
                if page not in successful_pages:
                    # Retry synchronously for missing pages
                    page_num, result = scrape_with_retry(page)
                    
                    if result is not None:
                        successful_pages.add(page_num)
                        if result.kanji_info and not kanji_info:
                            kanji_info = result.kanji_info
                        
                        table.add_row(
                            str(page_num),
                            f"[green]{len(result.items)}[/]/[red]{result.total_scraped}[/]",
                            "Yes" if result.has_next else "No",
                        )
                        merged.extend(result.items)
                    else:
                        table.add_row(str(page), "[red]Timeout (Retry Failed)![/]", "Unknown")

        # Return combined results.
        return PaginationResult(items=merged, kanji_info=kanji_info)