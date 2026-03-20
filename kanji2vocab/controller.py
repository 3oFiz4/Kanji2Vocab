# file: kanji2vocab/controller.py
import re
import time
import asyncio

from rich.live import Live

from .models import AppConfig, KanjiInfo, VocabItem, PaginationResult, CLIArgs
from .config import ConfigManager
from .services.logger import Logger
from .services.formatter import Formatter
from .services.ui import ConsoleUI
from .services.scraper import JishoScraper, VocabFilter
from .services.pagination import PaginationHandler
from .services.stroke import StrokeScraper
from .services.ai import AIClient
from .services.anki import AnkiClient
from .services.utils import strip_prefix


class AppController:
    """Main application controller that orchestrates all workflows."""
    def __init__(
        self,
        config_manager: ConfigManager,
        logger: Logger,
        formatter: Formatter,
        ui: ConsoleUI,
        scraper: JishoScraper,
        paginator: PaginationHandler,
        stroke_scraper: StrokeScraper,
        ai_client: AIClient,
        anki_client: AnkiClient,
        vocab_filter: VocabFilter,
        clipboard,
        initial_config: AppConfig,
    ) -> None:
        # Store dependencies.
        self.config_manager = config_manager
        self.logger = logger
        self.formatter = formatter
        self.ui = ui
        self.scraper = scraper
        self.paginator = paginator
        self.stroke_scraper = stroke_scraper
        self.ai_client = ai_client
        self.anki_client = anki_client
        self.vocab_filter = vocab_filter
        self.clipboard = clipboard

        # Store config and apply settings.
        self.config = initial_config
        self._apply_config(self.config)

    def _apply_config(self, config: AppConfig) -> None:
        """Apply configuration changes to dependent components."""
        # Update stored config.
        self.config = config
        # Update learned set in vocab filter.
        self.vocab_filter.set_learned_set(set(config.has_learned))
        # Update scraper settings.
        self.scraper.update_settings(
            base_url_template=config.base_url,
            is_tag_shortened=config.is_tag_shortened,
            is_meaning_shortened=config.is_meaning_shortened,
            is_colored=config.is_colored,
        )
        # Update Anki deck.
        self.anki_client.update_deck(config.anki_deck)

    def reload_config(self) -> None:
        """Reload configuration from disk and apply it."""
        # Load config from file.
        config = self.config_manager.load()
        # Apply updated settings.
        self._apply_config(config)

    def _update_learned(self, kanji: str) -> None:
        """Update hasLearned with a new kanji and refresh config."""
        # Update config via manager and apply changes.
        updated = self.config_manager.update_learned(self.config, kanji)
        self._apply_config(updated)

    def _dedupe_items(self, items: list[VocabItem]) -> list[VocabItem]:
        """Remove duplicate vocab items by vocab string."""
        # Track seen vocab strings.
        seen = set()
        # Accumulate unique items.
        unique = []
        for item in items:
            if item.vocab not in seen:
                unique.append(item)
                seen.add(item.vocab)
        # Return unique list.
        return unique

    def _build_prompt(self, vocab_list: list[str]) -> str:
        """Build the AI prompt for the given vocab list."""
        # Join vocab list using # as separator.
        joined = "#".join(vocab_list)

        # Compose prompt text (kept close to original).
        # Conf: This is the prompt that will be POST to the LLM API. 
        # The reason I did not add this into config.json is due to limitation of how .json does not accept multi-line string like this for better-reading. Although it may soon be re-configured so this can be shown in clarity.
        # TODO: Revamp config.json, therefore supports multi-line for prompt_text
        prompt_text = (
            "For each Vocabulary in the list (separated by #), output only in the EXACT format below. "
            "No extra text, no deviations, no missing sections.\n\n"
            "=== OUTPUT TEMPLATE START {DO NOT INCLUDE THIS LINE, THIS EXIST AS AN SHOWCASE HOW IT SHOULD BE DONE, NOT AS A PART OF THE TEMPLATE}===\n"
            "# <Vocabulary {BY EACH # IN VOCABULARY LIST, DO NOT CONFUSE THIS AS EACH KANJI IN A SINGLE VOCABULARY}>\n"
            "[Semantic]\n"
            "<Exact two-paragraph explanation of the core meaning, "
            "including subtle distinctions/difference from similar Vocabulary compound and vocabulary with close meanings (Example: The differences between '返答' and '応答'). This is required. "
            "Mention how it differs in nuance, strength, or scope compared to at least 3-10 similar words if applicable.>\n"
            "[Context]\n"
            "<Exact two-paragraph explanation of typical usage and nuance in modern Japanese, "
            "including when it is chosen over synonyms. Provide 1–2 short example sentences with Furigana and Meaning. "
            "If the Kanji (of the Vocabulary) often appears in other compounds kanji, explain how the combined kanji meanings form the compound makes sense."
            "Example: 受 (accept) + 取 (fetch) = 受け取る (to receive, to accept physically or figuratively).>\n"
            "[Component]\n"
            "<Exact two-paragraph explanation of (each) kanji component of the Vocabulary, "
            "including the derivation from Hanzi if possible, and how each component relate to each other in order to create the meaning, and an analogy of how to memorize it with mnemonics (visualization)>\n"
            "=== OUTPUT TEMPLATE END {DO NOT FUCKING INCLUDE THIS LINE, THIS EXIST AS AN SHOWCASE HOW IT SHOULD BE DONE, NOT AS A PART OF THE TEMPLATE. FUCKING NOTE THIS PIECE OF SHIT.}===\n\n"
            "Rules:\n"
            "- The Vocabulary in the given list (separated by #) sometimes can be only 2, to 3 vocabularies. THAT DOES NOT MEAN THAT YOU ONLY ADD ONE VOCABULARY. ADD EACH OF THEM, SEPARATED BY #. NO MATTER, HOW MANY VOCABULARIES INSIDE.`"
            "- Keep each [Semantic] and [Context] section concise but complete.\n"
            "- Always compare with at least one near-synonym if relevant. This is a must. You need to find other compound kanji or vocabulary with a similar meaning, or a meaning that learner often confused.\n"
            "- USE ENGLISH\n"
            "- Always explain compound meaning formation in a 'make sense' way, if the kanji (of the vocabulary) appears in common compounds. Analogy may be used otherwise.\n"
            "- Maintain section order, headings, and formatting for every kanji.\n"
            "- Concise, To the Point\n"
            "- THERE CANNOT AND SHOULD NOT BE SAME KANJI IN '# <Vocabulary>'. AVOID THIS\n"
            "- IN EVERY KANJI IN '# <Vocabulary>' IT SHOULD BE ACCORDINGLY WITHIN VOCABULARY LIST\n"
            "- Explain each kanji's component (of the Vocabulary), if it's a single kanji (non-compound), and retain the same explanation (copy and paste) in every other compound kanji's explanation"
            "Shorten (each and other) explanation, just because the information in other explanation is needed"
            "- Never skip sections even if information overlaps.\n\n"
            "Vocabulary list: " + joined
        )
        # Return composed prompt.
        return prompt_text

    def _fix_ai_response(self, response: str) -> str:
        """Apply model output cleanup rules."""
        # Detect and remove useless labels like <Vocabulary ...>.
        useless_label = r"<(?:Vocabulary\s*)+(.+?)>"
        if re.findall(useless_label, response, flags=re.MULTILINE) or re.search(
            r"Vocabulary\s+.+?", response
        ):
            response = re.sub(useless_label, r"\1", response, flags=re.DOTALL)
            response = re.sub(
                r"^(?:Vocabulary\s*)+(.+?)$", r"\1", response, flags=re.MULTILINE
            )
            self.logger.log("[#af0][MODEL CORRECTION]: Removing useless label.[/]", "_")

        # Remove outlier template lines.
        if re.findall(r"===(.+)", response, flags=re.MULTILINE) or re.findall(
            r"{(.+)", response, flags=re.MULTILINE
        ):
            response = re.sub(r"===(.+)", "", response, flags=re.DOTALL)
            response = re.sub(r" {(.+)", "", response, flags=re.DOTALL)
            self.logger.log("[#af0][MODEL CORRECTION]: Outlier.[/]", "_")

        # Return cleaned response.
        return response

    def _is_alignment_ok(self, response: str, expected: list[str]) -> bool:
        """Check if response # headings match expected vocab list."""
        # Extract vocab headings from response.
        aligned = re.findall(r"^#\s*([^\n]+)", response, flags=re.MULTILINE)
        # Compare with expected vocab list.
        return aligned == expected

    async def _request_ai_explanations(self, vocab_list: list[str]) -> str:
        """Request AI explanations and enforce formatting constraints."""
        # Build prompt and expected list.
        prompt_text = self._build_prompt(vocab_list)
        expected = vocab_list
        joined = "#".join(vocab_list)

        # Prepare rich Live log.
        with Live(console=self.logger.console, screen=False) as live:
            while True:
                # Request AI response.
                api_response = await self.ai_client.request_chat(
                    joined, prompt=prompt_text
                )

                # Handle quota errors by rotating key.
                if "402" in str(api_response):
                    self.logger.log(
                        "[#f00][API ERROR] (0 Kuota). Rotating to next key...[/]", "_"
                    )
                    self.ai_client.rotate_key()
                    continue

                # Log fatal API errors.
                if str(api_response).startswith("?!"):
                    self.logger.log(
                        f"[#f00][FATAL API ERROR]:\n{api_response}\n---[/]", "_"
                    )

                # Convert to string for processing.
                response_text = str(api_response)

                # Update live status.
                live.update("Output checking...")

                # Apply response fixes.
                response_text = self._fix_ai_response(response_text)

                # Validate alignment.
                if self._is_alignment_ok(response_text, expected):
                    live.update("\n\n[#0f0] Error Fixed.[/]", refresh=True)
                    return response_text
                else:
                    live.update(
                        f"\n\n[#f00][FATAL ERROR]: Disaligned. (Expecting {expected} got {re.findall(r'^#\\s*([^\\n]+)', response_text, flags=re.MULTILINE)} instead[/])"
                    )

    def _format_explanation_sections(self, explanation: str) -> str:
        """Apply HTML color styles to AI explanation sections."""
        # Colorize [Semantic] section.
        explanation = re.sub(
            r"(\[Semantic\])\s+(.+)",
            r'<p style="color:red;text-shadow: #ff0000aa 0 0 25px">\1<br>\2</p>',
            explanation,
            flags=re.DOTALL,
        )
        # Colorize [Context] section.
        explanation = re.sub(
            r"(\[Context\])\s+(.+)",
            r'<p style="color:#ff00ff;text-shadow: #ff00ffaa 0 0 25px">\1<br>\2</p>',
            explanation,
            flags=re.DOTALL,
        )
        # Colorize [Component] section.
        explanation = re.sub(
            r"(\[Component\])\s+(.+)",
            r'<p style="color:lime;text-shadow: #00ff00aa 0 0 25px">\1<br>\2</p>',
            explanation,
            flags=re.DOTALL,
        )
        # Return formatted explanation.
        return explanation

    def _censor_vocab_in_text(self, text: str, vocab: str) -> str:
        """Replace occurrences of vocab with a fixed placeholder sequence."""
        # Determine replacement pattern length.
        vocab_len = len(vocab)
        # Build a deterministic censor string.
        censor_letters = "XYZABCDEFGHIJKLMNOPQRSTUVW"[0:vocab_len]
        # Replace all occurrences of vocab.
        return re.sub(re.escape(vocab), censor_letters, text)

    def _color_vocab_by_verb_type(self, vocab: str, meaning: str) -> str:
        """Color the last character based on v5/v1 tags in meaning."""
        # Extract the last parenthetical group.
        parens = re.findall(r"\(([^)]*)\)", meaning)
        last_par = parens[-1] if parens else ""

        # Apply coloring based on verb type.
        if re.search(r"v5", last_par, re.IGNORECASE):
            return (
                vocab[:-1] + f'<span style="color:cyan">{vocab[-1]}</span>'
                if vocab
                else vocab
            )
        if re.search(r"v1", last_par, re.IGNORECASE):
            return (
                vocab[:-1] + f'<span style="color:red">{vocab[-1]}</span>'
                if vocab
                else vocab
            )
        return vocab

    async def _create_kanji_note(self, kanji: str, kanji_info: KanjiInfo) -> None:
        """Create a kanji note in clipboard or Anki."""
        # Build fields for the kanji template.
        formatted_template = self.config.template_kanji.format(
            KANJI=kanji,
            MEANING=kanji_info.meaning,
            ONYOMI=" " + strip_prefix(kanji_info.onyomi, "On:"),
            KUNYOMI=" " + strip_prefix(kanji_info.kunyomi, "Kun:"),
            INFO=kanji_info.info,
        )

        # Decide output method based on config.
        if self.config.vocab_method == "m":
            self.clipboard.copy(formatted_template)
            self.logger.log("Recorded to clipboard", "s")
        else:
            await self.anki_client.add_note(
                {
                    "Kanji": kanji,
                    "Keyword": kanji_info.meaning.replace(f"({kanji})", ""),
                    "Story": formatted_template,
                },
                self.config.anki_model_kanji,
            )
            self.logger.log("Recorded to Anki (AnkiConnect)", "s")

    async def run_for_kanji(
        self, kanji: str, total_pages: int = 20, method: str = "c"
    ) -> None:
        """Run the full pipeline for a single kanji."""
        # Update learned set and config.
        self._update_learned(kanji)

        # Fetch stroke SVG asynchronously.
        raw_svg = await self.stroke_scraper.fetch_svg(kanji)

        # Scrape vocab with timing.
        start_time = time.time()
        if method == "c":
            pagination_result = self.paginator.concurrent(kanji, total_pages)
        else:
            pagination_result = self.paginator.sequential(kanji, total_pages)
        end_time = time.time()
        scraper_time_elapsed = end_time - start_time

        # Stop if no results.
        if not pagination_result.items:
            self.logger.log("Nil.", "f")
            return

        # Use kanji info from scraper result.
        kanji_info = pagination_result.kanji_info or KanjiInfo.empty()

        # Dedupe items.
        items = self._dedupe_items(pagination_result.items)

        # Display kanji info once after scraping.
        if kanji_info and (
            kanji_info.onyomi
            or kanji_info.kunyomi
            or kanji_info.meaning
            or kanji_info.info
        ):
            self.logger.log(
                f"""Target Kanji: {kanji}
{kanji_info.onyomi}
{kanji_info.kunyomi}
Meaning: {kanji_info.meaning}
Info: {kanji_info.info}
""",
                "_",
            )

        # Select items either automatically or interactively.
        if self.config.is_automatic:
            selected_indices = set(range(len(items)))
        else:
            # Define callback for kanji template creation.
            def on_kanji_template():
                asyncio.create_task(self._create_kanji_note(kanji, kanji_info))

            selected_indices = self.ui.select_vocabulary(
                items=items,
                pagination_limit=self.config.pagination_limit,
                kanji_info=kanji_info,
                scraper_time_elapsed=scraper_time_elapsed,
                target_kanji=kanji,
                on_kanji_template=on_kanji_template,
            )

        # Exit if nothing selected.
        if not selected_indices:
            self.logger.log("No vocabulary selected. Exiting.", "c")
            return

        # Build vocab list for AI prompt.
        sorted_indices = sorted(selected_indices)
        selected_vocab_list = [items[i].vocab for i in sorted_indices]

        # Request AI explanations. Only if self.config.is_automatic is TRUE.. oh cmon its not that expensive for a cheap AI api 😂
        if self.config.is_automatic:
            api_response = await self._request_ai_explanations(selected_vocab_list)
        
            # Log and give time to abort if needed.
            self.logger.log(api_response)
            self.logger.log(
                "If there is something wrong with the AI response, quickly press <C-c> to disband and reset AI response, else ignore.\nProgram will continue in 3 seconds",
                "i",
            )
            await asyncio.sleep(5)

            # Split explanations by #.
            explanation_list = [
                piece.strip() for piece in api_response.split("#") if piece.strip()
            ]
        else:
            # fallback: no AI → empty explanations. Faking as if explanation_list exist.
            explanation_list = [""] * len(sorted_indices)

        # Collect Anki tasks if needed.
        anki_tasks = []

        # Process each selected vocab with its explanation.
        for idx, explanation in zip(sorted_indices, explanation_list):
            item = items[idx]

            # Convert furigana markup to HTML.
            html_furigana = self.formatter.cv_html(item.furigana)

            # Format meaning with line breaks before numbering.
            formatted_meaning = re.sub(r"(\d+\.)", r"<br>\1", item.meaning)

            # Colorize explanation sections.
            formatted_explanation = self._format_explanation_sections(explanation)

            # Build final meaning with AI content.
            updated_meaning = formatted_meaning + "<br><br>" + formatted_explanation

            # Censor original vocab in meaning.
            updated_meaning = self._censor_vocab_in_text(updated_meaning, item.vocab)

            # Color vocab by verb type.
            colored_vocab = self._color_vocab_by_verb_type(
                item.vocab, formatted_meaning
            )

            # Build the final template.
            formatted_template = self.config.template.format(
                KANJI=kanji,
                KANJI_ONYOMI=" " + strip_prefix(kanji_info.onyomi, "On:"),
                KANJI_KUNYOMI=" " + strip_prefix(kanji_info.kunyomi, "Kun:"),
                KANJI_MEANING=kanji_info.meaning,
                VOCAB=r"{{c1::" + colored_vocab + r"}}",
                MEANING=r"{{c2::" + updated_meaning + r"}}",
                FURIGANA=r"{{c1::" + html_furigana + r"}}",
                TAG=item.tag,
                STROKE=raw_svg or "",
            )

            # Output via clipboard or Anki.
            if self.config.vocab_method == "m":
                self.clipboard.copy(formatted_template)
                self.logger.log(f"VBX #{idx} COPIED successfully (Confirmed)", "s")
            else:
                task = asyncio.create_task(
                    self.anki_client.add_note(
                        {"Content": formatted_template},
                        self.config.anki_model_vocab,
                    )
                )
                anki_tasks.append(task)
                self.logger.log(f"VBX #{idx + 1} recorded", "s")

        # Await all Anki tasks to finish.
        if anki_tasks:
            await asyncio.gather(*anki_tasks, return_exceptions=True)

    async def dispatch(self, args: CLIArgs) -> None:
        """Dispatch CLI actions to the correct workflow."""
        # Handle config editor action.
        if args.action == "config":
            saved = self.ui.edit_config(self.config_manager)
            if saved:
                self.reload_config()
            return

        # Handle help action.
        if args.action == "help":
            self.logger.log(
                "Command list:\n"
                "1. -c/--config | To modify config.json\n"
                "2. Kanji2Vocab.py [KANJI] [TOTAL_PAGINATION] [PAGE_SCRAPE_METHOD]\n"
                " | [KANJI] = Requires any Kanji\n"
                " | [TOTAL_PAGINATION] = Require an integer\n"
                " | [PAGE_SCRAPE_METHOD] = Either s or c, s = Sequential (one-by-one), c = Concurrent (all-together), default = s\n\n"
                "Credit:[#00ffff bold]3oFiz4[/] (Discord, Instagram)",
                "_",
            )
            return

        # Handle multi-kanji default run.
        if args.action == "multi" and args.kanji:
            for ch in args.kanji:
                await self.run_for_kanji(ch, total_pages=20, method="c")
            return

        # Handle explicit run.
        if args.action == "run" and args.kanji:
            method = args.method if args.method in ("s", "c") else "c"
            await self.run_for_kanji(
                args.kanji, total_pages=args.total_pages or 20, method=method
            )
            return

        # Handle interactive mode.
        if args.action == "interactive":
            kanji = self.ui.input_kanji()
            total = int(input("Total page: ").strip())
            await self.run_for_kanji(kanji, total_pages=total, method="c")
            return

