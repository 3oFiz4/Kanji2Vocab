# file: kanji2vocab/services/stroke.py
import aiohttp
from bs4 import BeautifulSoup

from .utils import uni
from .logger import Logger


class StrokeScraper:
    """Fetches kanji stroke SVG from kvg."""
    def __init__(self, logger: Logger) -> None:
        # Store logger instance for optional error reporting.
        self.logger = logger

    async def fetch_svg(self, kanji: str) -> str | None:
        """Fetch and slightly modify the kanji stroke SVG."""
        # Build the URL using unicode hex.
        code = uni(kanji)
        if not code:
            return None
        url = f"https://www.lemoda.net/kvg/{code.lower()}.svg"

        # Open an aiohttp session to fetch SVG.
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                # Return None if the request failed.
                if response.status != 200:
                    return None

                # Read SVG content as text.
                svg_content = await response.text()

                # Extract the first SVG element.
                start_index = svg_content.find("<svg")
                end_index = svg_content.find("</svg>", start_index) + len("</svg>")
                first_svg_element = svg_content[start_index:end_index]

                # Parse and tweak the SVG style.
                soup = BeautifulSoup(first_svg_element, "xml")
                g_element = soup.find("g", id=lambda x: x and x.startswith("kvg:StrokePaths"))
                if g_element:
                    g_element["style"] = "stroke:#fff; background:#000"

                # Return the modified SVG string.
                return str(soup)