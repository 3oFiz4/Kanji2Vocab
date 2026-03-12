# file: kanji2vocab/services/logger.py
from rich.console import Console
from rich import print as rich_print


class Logger:
    """Rich-based logger with status-aware formatting."""
    def __init__(self) -> None:
        # Create a rich console for structured output.
        self.console = Console()

    def log(self, text, status: str = "s") -> None:
        """Print a log line with optional status styling."""
        # If the object is a rich renderable, print it directly.
        if hasattr(text, "__rich_console__"):
            self.console.print(text)
            return

        # Normalize text to string for safety.
        msg = str(text)

        # Apply status-based formatting.
        if status == "f":
            rich_print(f"[red bold][X] {msg}[/]")
        elif status == "s":
            rich_print(f"[green bold][V] {msg}[/]")
        elif status == "c":
            rich_print(f"[yellow bold][?] {msg}[/]")
        elif status == "w":
            rich_print(f"[orange bold][!] {msg}[/]")
        elif status == "i":
            rich_print(f"[blue]{msg}[/]")
        elif status == "_":
            rich_print(msg)
        else:
            rich_print(f"[green bold][V] {msg}[/]")

    def rule(self, title: str) -> None:
        """Print a horizontal rule with a title."""
        # Use rich console rule for visual separation.
        self.console.rule(title)