# file: kanji2vocab/services/ui.py
from rich.table import Table
from rich.console import Console

from ..models import KanjiInfo, VocabItem
from .logger import Logger
from .formatter import Formatter
from ..config import ConfigManager


class ConsoleUI:
    """Handles all console I/O and interactive selection logic."""
    def __init__(self, logger: Logger, formatter: Formatter) -> None:
        # Store logger and formatter.
        self.logger = logger
        self.formatter = formatter
        # Use logger's console for consistent output.
        self.console = logger.console

    def input_kanji(self) -> str:
        """Prompt the user to input a single kanji character."""
        # Keep asking until valid input is provided.
        while True:
            # Use rich console input for styling.
            kanji = self.console.input("[bold #00ff00]Target Kanji[/]: ").strip()
            # Validate input: must be single non-digit character.
            if len(kanji) == 1 and not kanji.isdigit() and not kanji.isspace():
                return kanji
            # Notify user on invalid input.
            self.logger.log("Invalid input. Enter exactly one kanji character without spaces or digits.", "f")

    def edit_config(self, config_manager: ConfigManager) -> bool:
        """Interactive config editor; returns True if saved."""
        # Load raw config to preserve unknown keys.
        current_config = config_manager.load_raw()

        # Loop until user exits.
        while True:
            # Build a rich table for config display.
            config_table = Table(title="Configuration (config.json)", show_header=True, header_style="bold cyan")
            config_table.add_column("Key", style="orange3", justify="right")
            config_table.add_column("Value", style="yellow")

            # Populate table rows.
            for key, value in current_config.items():
                if isinstance(value, bool):
                    formatted_value = "✓" if value else "✗"
                elif isinstance(value, list):
                    formatted_value = ", ".join(str(x) for x in value[:5]) + ("..." if len(value) > 5 else "")
                else:
                    formatted_value = str(value)
                config_table.add_row(key, formatted_value)

            # Display config table.
            self.logger.log(config_table, "_")

            # Display options menu.
            self.logger.log("\nOptions:", "_")
            self.logger.log("1. Edit value", "_")
            self.logger.log("2. Add new key-value (dev only)", "_")
            self.logger.log("3. Remove key-value (dev only)", "_")
            self.logger.log("4. Save & Exit", "_")
            self.logger.log("5. Exit", "_")

            # Read user choice.
            choice = input("\nEnter choice (1-5): ").strip()

            if choice == "1":
                # Prompt for key to edit.
                key = input("Enter key to edit: ").strip()
                if key in current_config:
                    # Display current value and prompt for new one.
                    current_value = current_config[key]
                    self.logger.log(f"Current value: {current_value}", "i")

                    # Convert input based on existing type.
                    if isinstance(current_value, bool):
                        new_value = input("Enter new value (true/false): ").lower() == "true"
                    elif isinstance(current_value, int):
                        new_value = int(input("Enter new value: "))
                    elif isinstance(current_value, list):
                        new_value = input("Enter new values (comma separated): ").split(",")
                        new_value = [v.strip() for v in new_value]
                    else:
                        new_value = input("Enter new value: ")

                    # Save the updated value.
                    current_config[key] = new_value
                    self.logger.log(f"Updated {key} to {new_value}", "s")
                else:
                    # Inform user if key is missing.
                    self.logger.log("Key not found", "f")

            elif choice == "2":
                # Prompt for new key and value.
                key = input("Enter new key: ").strip()
                if key not in current_config:
                    value = input("Enter value: ")
                    # Try to evaluate as Python literal, fallback to string.
                    try:
                        value = eval(value)
                    except Exception:
                        pass
                    current_config[key] = value
                    self.logger.log(f"Added {key}: {value}", "s")
                else:
                    self.logger.log("Key already exists", "f")

            elif choice == "3":
                # Prompt for key removal.
                key = input("Enter key to remove: ").strip()
                if key in current_config:
                    del current_config[key]
                    self.logger.log(f"Removed {key}", "s")
                else:
                    self.logger.log("Key not found", "f")

            elif choice == "4":
                # Save to file and exit.
                config_manager.save_raw(current_config)
                self.logger.log("Configuration saved", "s")
                return True

            elif choice == "5":
                # Exit without saving.
                self.logger.log("Exiting without saving", "w")
                return False

            else:
                # Handle invalid choices.
                self.logger.log("Invalid choice", "f")

    def select_vocabulary(
        self,
        items: list[VocabItem],
        pagination_limit: int,
        kanji_info: KanjiInfo,
        scraper_time_elapsed: float,
        target_kanji: str,
        on_kanji_template,
    ) -> set[int]:
        """Interactive selection of vocab items with pagination."""
        # Compute pagination statistics.
        total_items = len(items)
        current_page = 0
        total_pages = (total_items + pagination_limit - 1) // pagination_limit

        # Track selected indices.
        selected = set()

        # Continue until user finishes selection.
        while True:
            # Compute page bounds.
            start_idx = current_page * pagination_limit
            end_idx = min(start_idx + pagination_limit, total_items)

            # Build the vocab table for the current page.
            table = Table(
                caption=(
                    f"Scraped Vocabulary\nPage {current_page + 1} of {total_pages}"
                    f"\nItems {start_idx + 1}-{end_idx} of {total_items}"
                    f"\nTime Taken: {scraper_time_elapsed}"
                ),
                show_lines=True,
            )
            table.add_column("Vocab", justify="center", style="cyan bold")
            table.add_column("Furigana", style="#00ffff i")
            table.add_column("Tag", justify="center", style="purple")
            table.add_column("Meaning", justify="center", style="#00ff00 bold")

            # Populate table rows.
            for i in range(start_idx, end_idx):
                item = items[i]
                meaning = self.formatter.color_to_rich(item.meaning)
                if i in selected:
                    table.add_row(
                        f"[blue]{i + 1}. {item.vocab}[/]",
                        f"[blue]{item.furigana}[/]",
                        f"[blue]{item.tag}[/]",
                        f"[blue]{meaning}[/]",
                    )
                else:
                    table.add_row(
                        f"{i + 1}. {item.vocab}",
                        f"{item.furigana}",
                        f"{item.tag}",
                        f"{meaning}",
                    )

            # Print the table and a separator.
            self.console.print(table)
            self.logger.rule("[bold #00ff00]Separator")

            # Show navigation instructions and kanji info.
            self.logger.log("\nNavigation: < (previous) | > (next) | _ (finish selection)", "_")
            self.logger.log("To select a vocabulary item for batch processing, enter its number", "i")
            self.logger.log(
                f"""Target Kanji: {target_kanji}
Onyomi: {kanji_info.onyomi}
Kunyomi: {kanji_info.kunyomi}
Meaning: {kanji_info.meaning}
Info: {kanji_info.info}
""",
                "_",
            )

            # Read user command.
            command = input("Enter command or number: ").strip()

            if command == "<":
                # Move to previous page.
                current_page = max(0, current_page - 1)
            elif command == ">":
                # Move to next page.
                current_page = min(total_pages - 1, current_page + 1)
            elif command.lower() in ["k", "kanji"]:
                # Trigger kanji template action.
                on_kanji_template()
            elif command == "_":
                # Finish selection.
                break
            elif command in [".", "all"]:
                # Select all and finish.
                selected = set(range(total_items))
                break
            elif command.isdigit():
                # Add a single item by index.
                index = int(command) - 1
                if 0 <= index < total_items:
                    selected.add(index)
                    self.logger.log(f"Vocabulary {index + 1} selected for batch processing", "s")
                else:
                    self.logger.log("Invalid number. Enter a valid vocabulary number.", "c")
            else:
                # Handle invalid commands.
                self.logger.log("Use <, >, _ to navigate or enter a number", "c")

        # Return the final selection set.
        return selected