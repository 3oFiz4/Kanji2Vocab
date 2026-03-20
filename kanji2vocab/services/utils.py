# file: kanji2vocab/services/utils.py
import re
from dotenv import load_dotenv


def load_env() -> None:
    """Load environment variables from .env if available."""
    # Trigger dotenv loader to populate os.environ.
    load_dotenv()


def uni(text: str) -> str | None:
    """Return the 5-digit uppercase hex codepoint of the last character."""
    # Initialize placeholder for unicode result.
    unicode_val = None
    # Iterate through characters and keep last codepoint.
    for char in text:
        unicode_number = ord(char)
        unicode_val = f"{unicode_number:05X}"
    # Return the computed value (or None if input empty).
    return unicode_val


def normalize_jp(s: str) -> str:
    """Normalize Japanese strings by removing HTML and furigana brackets."""
    # Remove HTML tags.
    s = re.sub(r"<[^>]+>", "", s)
    # Remove bracketed furigana [お].
    s = re.sub(r"\[[^\]]+\]", "", s)
    # Remove spaces between word characters.
    s = re.sub(r"(?<=\w)\s+(?=\w)", "", s)
    # Remove newlines.
    s = s.replace("\n", "")
    # Return normalized string.
    return s


def strip_prefix(text: str, prefix: str) -> str:
    """Remove a prefix if present, otherwise return the original text."""
    # Check prefix existence and strip accordingly.
    return text[len(prefix):] if text.startswith(prefix) else text