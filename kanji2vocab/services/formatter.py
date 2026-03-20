# file: kanji2vocab/services/formatter.py
import re
from bs4 import BeautifulSoup
from typing import Iterable, Optional

from ..models import KanjiInfo


class Formatter:
    """Provides utilities for meaning/tag formatting and color conversions."""
    def color_span(self, text: str, hex_color: str) -> str:
        """Wrap text in an HTML span with a color tag."""
        # Build a consistent HTML span marker for later conversion.
        return f'<span id="k2v-colored" style="color:#{hex_color}">{text}</span>'

    def color_to_rich(self, text: str) -> str:
        """Convert HTML color spans to Rich markup."""
        # Define pattern for our custom HTML span.
        pattern = r'<span id="k2v-colored" style="color:#(\w{6})">(.*?)<\/span>'
        # Replace with Rich markup syntax.
        return re.sub(pattern, r'[#\1]\2[/]', text, flags=re.DOTALL | re.IGNORECASE)

    def shortify_tag(self, tag: str) -> str:
        """Shorten known tag phrases (e.g., JLPT N5 -> N5)."""
        # Define regex replacements for tag shortening.
        patterns = [
            (r"\bJLPT N(\d+)\b", r"N\1"),
            (r"\bWanikani level (\d+)\b", r"WN\1"),
            (r"\bCommon word\b", "CMN"),
        ]
        # Apply all replacements in order.
        for pattern, replacement in patterns:
            tag = re.sub(pattern, replacement, tag)
        # Return trimmed tag.
        return tag.strip()

    def shortify_meaning(self, meanings: Iterable[str] | str) -> str:
        """Shorten meaning labels and format with numbering."""
        # Normalize input into a list of strings.
        if isinstance(meanings, str):
            meaning_list = [meanings]
        else:
            meaning_list = list(meanings)

        # Replace semicolons with commas.
        meaning_list = [m.replace(";", ",") for m in meaning_list]

        # Mapping of long labels to short labels.
        pattern_map = {
            "Adverb (fukushi)": self.color_span("adv", "00ff7f"),
            "Noun which may take the genitive case particle 'no'": "adjの",
            "Noun": "n",
            "Suru verb": self.color_span("vする", "216bd6"),
            "Transitive verb": "vt",
            "Intransitive verb": "vi",
            "Ichidan verb": self.color_span("v1", "ff0000"),
            "Godan verb": self.color_span("v5", "00ffff"),
            "Na-adjective (keiyodoshi)": self.color_span("adjな", "ff00ff"),
            "I-adjective (keiyoushi)": self.color_span("adjい", "00ff00"),
            "Wikipedia definition": self.color_span("wk", "c0c0c0"),
            "Expressions (phrases, clauses, etc.)": self.color_span("exp", "6a5acd"),
            "(Other forms)": self.color_span("alt", "708090"),
            "Conjunction": "conj",
            "------": "-------",
            "Usually written using kana alone , usu. as": self.color_span("KANA usu. AS:", "ff1493"),
            "Usually written using kana alone , as": self.color_span("KANA AS:", "ff1493"),
            "Usually written using kana alone": self.color_span("KANA", "ff1493"),
            "Antonym:": "ANT:",
            "esp.": "ESP:",
            "Auxiliary verb": self.color_span("v-AUX", "ff0094"),
            "after the -masu stem of a verb": self.color_span("v-ます", "ff0094"),
            "after the -te form of a verb": self.color_span("v-て", "ff0094"),
        }

        processed = []
        # Process each meaning entry.
        for i, meaning in enumerate(meaning_list, 1):
            # Apply direct string replacements.
            for pattern, replacement in pattern_map.items():
                meaning = meaning.replace(pattern, replacement)

            # Split by commas and trim whitespace.
            parts = [p.strip() for p in meaning.split(",")]

            # Remove repeated "to " after the first occurrence.
            for j in range(len(parts)):
                if j > 0 and parts[j].startswith("to ") and any(p.startswith("to ") for p in parts[:j]):
                    parts[j] = parts[j][3:]

            # Rebuild numbered meaning line.
            processed.append(f"{i}. " + ", ".join(parts))

        # Join all meanings with newlines.
        return "\n".join(processed)

    def join_meanings(self, meanings: Iterable[str] | str) -> str:
        """Join meanings into a single string if needed."""
        # If already a string, return as-is.
        if isinstance(meanings, str):
            return meanings
        # Otherwise, join list items with newlines.
        return "\n".join(meanings)

    def format_meaning(self, html) -> list[str]:
        """Convert Jisho meaning HTML into readable strings."""
        # Parse the HTML with BeautifulSoup.
        soup = BeautifulSoup(str(html), "html.parser")
        # Locate meaning blocks and their tag blocks.
        meanings = soup.find_all("div", class_="meaning-wrapper")
        tags = soup.find_all("div", class_="meaning-tags")

        formatted_meanings: list[str] = []

        def _filter(raw) -> str:
            """Keep text and <a href> tags while stripping other elements."""
            # Build result parts incrementally.
            result = []
            # Traverse all descendants to extract text and links.
            for elem in raw.descendants:
                if isinstance(elem, str):
                    result.append(elem.strip())
                elif elem.name == "a" and elem.has_attr("href"):
                    result.append(str(elem))
            # Join and normalize spacing.
            return " ".join(result).strip()

        def _process_sentence(sentence) -> str:
            """Convert example sentence HTML into kanji[furigana] format."""
            # Convert sentence soup to raw HTML.
            sentence_html = str(sentence)

            # Replace list items with kanji[furigana] pairs.
            def replacer(match):
                furigana = match.group("f")
                kanji = match.group("k_hit") or match.group("k_normal")
                return f"{kanji}[{furigana}]"

            pattern = re.compile(
                r'<li class="clearfix">\s*'
                r'<span class="furigana">(?P<f>.*?)</span>\s*'
                r'<span class="unlinked">(?:<span class="hit">(?P<k_hit>.*?)</span>|(?P<k_normal>.*?))</span>\s*'
                r"</li>",
                re.DOTALL,
            )

            # Apply regex substitution.
            sentence_html = re.sub(pattern, replacer, sentence_html)

            # Parse back to soup and return text.
            sentence_soup = BeautifulSoup(sentence_html, "html.parser")
            return sentence_soup.get_text(separator=" ", strip=True)

        # Build formatted meanings with tags, info, and examples.
        for i, meaning in enumerate(meanings):
            # Extract main meaning text.
            meaning_text = meaning.find("span", class_="meaning-meaning")
            meaning_text = _filter(meaning_text) if meaning_text else None

            # Extract supplemental info.
            meaning_info = meaning.find("span", class_="supplemental_info")
            meaning_info = _filter(meaning_info) if meaning_info else None

            # Extract example sentence.
            meaning_ex = meaning.find("div", class_="sentence")
            meaning_ex = _process_sentence(meaning_ex) if meaning_ex else None

            # Build colored info and example blocks.
            ex_exist = self.color_span(f"\n「{meaning_ex}」", "424242") if meaning_ex else ""
            info_exist = (
                self.color_span("\n【 ", "e39a0c") + meaning_info + self.color_span("】", "e39a0c")
                if meaning_info
                else ""
            )

            # Capture the tag text for this meaning.
            tag_text = tags[i].text.strip() if i < len(tags) else None

            # Combine the final meaning line.
            if meaning_text:
                if tag_text:
                    formatted = f"{meaning_text} ({tag_text}){info_exist}{ex_exist}"
                else:
                    formatted = meaning_text
                formatted_meanings.append(formatted)

        # Return the list of formatted meaning strings.
        return formatted_meanings

    def parse_color(self, value: str, kanji: Optional[KanjiInfo], enable_color: bool = True) -> str:
        """Colorize furigana by matching onyomi/kunyomi readings."""
        # If coloring is disabled or no kanji info, return raw value.
        if not enable_color or not kanji or not value:
            return value or ""

        # Prepare onyomi and kunyomi lists.
        onyomi_list = []
        kunyomi_list = []

        # Extract onyomi readings if available.
        if kanji.onyomi:
            onyomi_list = [r.replace("On:", "").strip() for r in kanji.onyomi.split("、")]

        # Extract kunyomi readings if available.
        if kanji.kunyomi:
            kunyomi_list = [r.replace("Kun:", "").replace("-", "").strip() for r in kanji.kunyomi.split("、")]

        result = value

        def kata_to_hira(text: str) -> str:
            """Convert Katakana characters to Hiragana for matching."""
            return "".join(chr(ord(c) - 0x60) if "ァ" <= c <= "ヶ" else c for c in text)

        # Replace onyomi matches with colored katakana.
        for onyomi in onyomi_list:
            onyomi_hiragana = kata_to_hira(onyomi)
            if onyomi_hiragana in result:
                result = result.replace(onyomi_hiragana, f"[#00aaff]{onyomi}[/]")

        # Replace kunyomi matches with colored kana.
        for kunyomi in kunyomi_list:
            kunyomi_hiragana = kata_to_hira(kunyomi)
            if kunyomi_hiragana in result:
                result = result.replace(kunyomi_hiragana, f"[#ffff00]{kunyomi}[/]")

        # Return the colorized string.
        return result

    def cv_html(self, meaning: str) -> str:
        """Convert Rich color markup into HTML spans."""
        # Pattern to detect Rich color markup.
        pattern = r"\[#([0-9A-Fa-f]{6})\](.*?)\[/\]"
        # Replace with HTML span tags.
        return re.sub(pattern, r'<span style="color:#\1">\2</span>', meaning)