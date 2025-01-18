import requests
import pyperclip as copier
from bs4 import BeautifulSoup
import sys
import json 
import re
import time
import threading
from queue import Queue
from concurrent.futures import ThreadPoolExecutor, as_completed
from multiprocessing import Value
from rich.console import Console
from rich.table import Table
from rich.live import Live
from rich import print as color_print
from threading import Lock
import concurrent.futures
import random

class Config:
    def __init__(self, config_file='config.json'):
        with open(config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)
        self.base_url = config['BaseUrl']
        self.has_learned = list(config['hasLearned'])
        self.template = config['Template']
        self.template_kanji = config['TemplateKanji']
        self.is_template = config['isTemplate']
        self.is_tag_shortened = config['isTagShortened']
        self.is_meaning_shortened = config['isMeaningShortened']
        self.pagination_limit = config['PaginationLimit']

class Logger:
    @staticmethod
    def log(text, status=0):
        status_map = {
            'f': '[red bold][X]{}[/]',
            's': '[green bold][V]{}[/]',
            'c': '[yellow bold][?]{}[/]',
            'w': '[orange bold][!]{}[/]',
            'i': '[blue]{}[/]',
            '_': '{}',
            0: '[green bold]{}[/]'
        }
        color_print(status_map.get(status, '[green bold]{}[/]').format(text))

class KanjiScraper:
    def __init__(self, kanji, config):
        self.kanji = kanji
        self.config = config
        self.base_url = config.base_url.format(Kanji=kanji)
        self.kanji_data = None
        self.logger = Logger()

    def is_valid_vocab(self, vocab):
        if self.kanji not in vocab:
            return False
        for char in vocab:
            if char != self.kanji and char not in self.config.has_learned:
                return False
        return True

    @staticmethod
    def shortify_tag(tag):
        patterns = [
            (r'\bJLPT N(\d+)\b', r'N\1'),
            (r'\bWanikani level (\d+)\b', r'WN\1'),
            (r'\bCommon word\b', 'CMN')
        ]
        for pattern, replacement in patterns:
            tag = re.sub(pattern, replacement, tag)
        return tag.strip()

    @staticmethod
    def shortify_meaning(meaning):
        # First replace semicolons with commas
        meaning = [m.replace(';', ',') for m in meaning]
        
        # Replace specific patterns
        pattern_map = {
            'Adverb (fukushi)': 'adv',
            'Noun which may take the genitive case particle \'no\'': 'adjの',
            'Noun': 'n',
            'Suru verb': 'vs',
            'Transitive verb': 'vt', 
            'Intransitive verb': 'vi',
            'Ichidan verb': 'v1',
            'Godan verb': 'v5',
            'Na-adjective (keiyodoshi)': 'adjな',
            'I-adjective (keiyoushi)': 'adjい',
            'Wikipedia definition': 'wk',
            'Expressions (phrases, clauses, etc.)': 'exp',
            '(Other forms)': 'alt'
        }
        
        processed = []
        for i, meaning in enumerate(meaning, 1):
            for pattern, replacement in pattern_map.items():
                meaning = meaning.replace(pattern, replacement)
                
            parts = meaning.split(',')
            for j in range(len(parts)):
                parts[j] = parts[j].strip()
                if j > 0 and parts[j].startswith('to ') and any(p.startswith('to ') for p in parts[:j]):
                    parts[j] = parts[j][3:]
            
            meaning = f"{i}. " + ', '.join(parts)
            processed.append(meaning)
        
        # Join with newlines
        return '\n'.join(processed)

    def to_onyomi(self, value):
        '''
        Convert only matching onyomi parts from hiragana to katakana
        For example: にんげん -> ニンげん (because にん matches the onyomi ニン)
        '''
        # Clean up onyomi readings - remove 'On:' prefix and get clean list
        onyomi_list = [reading.replace('On:', '').strip() for reading in self.kanji_data['Onyomi'].split('、')]
        
        result = value
        for onyomi in onyomi_list:
            # Convert onyomi to hiragana for comparison
            onyomi_hiragana = ''.join(
                chr(ord(char) - 0x60) if 'ァ' <= char <= 'ヶ' else char 
                for char in onyomi
            )
            
            # If this onyomi reading exists in hiragana form, replace it with katakana
            if onyomi_hiragana in result:
                result = result.replace(onyomi_hiragana, f"[#008888]{onyomi}[/]")
        
        return result

    def scrape_page(self, page_num):
        """
        Scrape a single page of vocabulary for the target kanji.
        """
        # Session for connection pooling
        session = requests.Session()
        
        # Add timeout and headers for better reliability
        user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.93 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.4389.82 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/88.0.4324.150 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/87.0.4280.141 Safari/537.36'
        ]
        headers = {
            'User-Agent': random.choice(user_agents)
        }
        
        try:
            r = session.get(self.base_url + f'?page={page_num}', headers=headers)
            r.raise_for_status()
        except requests.RequestException as e:
            self.logger.log(f"Failure.\nError: {str(e)}", "f")
            return []

        p = BeautifulSoup(r.content, 'lxml')  # lxml parser for better performance

        results = []
        total_scraped = 0

        # Check if "More Words" exist
        is_next_pagination = bool(p.select_one('a.more'))

        # CSS selectors to get all elements at once
        target_element_character = p.select("div.concept_light-readings.japanese.japanese_gothic > div.concept_light-representation")
        target_element_meaning = p.select("div.meanings-wrapper") 
        target_element_tag = p.select("div.concept_light-status")

        if is_next_pagination or (target_element_character, target_element_meaning, target_element_tag):
            # Regex patterns
            text_pattern = "span.text"
            furigana_pattern = "span.furigana"
            tag_pattern = ".concept_light-tag.label"

            if page_num == 1: # It is only available at first page.
                target_element_kanji = p.select_one("div.kanji_light_content")
                # Regex patterns (Kanji Only)
                kanji_onyomi_pattern = "div.on.readings" # This only returns the div header
                kanji_kunyomi_pattern = "div.kun.readings" # This only returns the div header
                kanji_meaning_pattern = "div.meanings.english.sense" # This only returns the div header
                kanji_info_pattern = "div.info.clearfix" # This only returns the div header

                # Kanji Element (they're accessed only one time, when a second loop happen *in the sense of page is non-default*, this process are ignored.)
                scr_kanji_onyomi = target_element_kanji.select_one(kanji_onyomi_pattern)
                scr_kanji_kunyomi = target_element_kanji.select_one(kanji_kunyomi_pattern)
                scr_kanji_meaning = target_element_kanji.select_one(kanji_meaning_pattern)
                scr_kanji_info = target_element_kanji.select_one(kanji_info_pattern)

                # If one of them or both exist.
                if scr_kanji_onyomi and scr_kanji_kunyomi:
                    # Unwrap all <a> tags within Onyomi and Kunyomi
                    for onyomi, kunyomi in zip(scr_kanji_onyomi.find_all("a", recursive=True), scr_kanji_kunyomi.find_all("a", recursive=True)):
                        onyomi.unwrap()
                        kunyomi.unwrap()
                    kanji_onyomi = scr_kanji_onyomi.get_text(strip=True, separator="")
                    kanji_kunyomi = scr_kanji_kunyomi.get_text(strip=True, separator="")
                elif scr_kanji_onyomi:
                    # Unwrap all <a> tags within Onyomi
                    for onyomi in scr_kanji_onyomi.find_all("a", recursive=True):
                        onyomi.unwrap()
                    kanji_onyomi = scr_kanji_onyomi.get_text(strip=True, separator="")
                    kanji_kunyomi = ""
                elif scr_kanji_kunyomi:
                    # Unwrap all <a> tags within Kunyomi
                    for kunyomi in scr_kanji_kunyomi.find_all("a", recursive=True):
                        kunyomi.unwrap()
                    kanji_kunyomi = scr_kanji_kunyomi.get_text(strip=True, separator="")
                    kanji_onyomi = ""
                else:
                    kanji_onyomi = ""
                    kanji_kunyomi = ""

                kanji_meaning = scr_kanji_meaning.get_text(strip=True, separator="") if scr_kanji_meaning else ""
                kanji_info = scr_kanji_info.get_text(strip=True, separator="") if scr_kanji_info else ""

                self.kanji_data = {
                    "Info": kanji_info,
                    "Onyomi": kanji_onyomi,
                    "Kunyomi": kanji_kunyomi,
                    "Meaning": kanji_meaning
                }

            for e_target_element_character, e_target_element_meaning, e_target_element_tag in zip(target_element_character, target_element_meaning, target_element_tag):
                # Cache selector results
                text_elem = e_target_element_character.select_one(text_pattern)
                furigana_elem = e_target_element_character.select_one(furigana_pattern)
                
                scr_vocab = text_elem.get_text(strip=True) if text_elem else None
                scr_furi = furigana_elem.get_text(strip=True) if furigana_elem else None
                scr_tags = e_target_element_tag.select(tag_pattern)
                total_scraped += 1

                if self.is_valid_vocab(scr_vocab) and scr_furi:
                    # Build tag contents list more efficiently
                    tag_contents = [tag.get_text(strip=True) for tag in scr_tags if tag]
                    tag_contents = [content for content in tag_contents if content]

                    # Join tag contents into a single string
                    tag = self.shortify_tag(', '.join(tag_contents)) if self.config.is_tag_shortened else ', '.join(tag_contents)
                    
                    # Process meaning
                    meaning = self.shortify_meaning(self.format_meaning(e_target_element_meaning)) if self.config.is_meaning_shortened else self.format_meaning(e_target_element_meaning)
                    
                    results.append({
                        "Vocab": scr_vocab,
                        "Furi": self.to_onyomi(scr_furi),
                        "Meaning": meaning,
                        "Tag": tag
                    })

            return results, is_next_pagination, total_scraped
        else:
            return [], False, 0

    @staticmethod
    def format_meaning(html):
        """
        Format the raw HTML of a Vocabulary to be human-readable
        """
        f_p = BeautifulSoup(str(html), 'html.parser')
        meanings = f_p.find_all('div', class_='meaning-wrapper')
        tags = f_p.find_all('div', class_='meaning-tags')

        formatted_meanings = []

        for i, meaning in enumerate(meanings):
            meaning_text = meaning.find('span', class_='meaning-meaning')
            meaning_text = meaning_text.text.strip() if meaning_text else None
            tag_text = tags[i].text.strip() if i < len(tags) else None
            if meaning_text:
                formatted_meaning = f"{meaning_text} ({tag_text})" if tag_text else meaning_text
                formatted_meanings.append(formatted_meaning)
        
        return formatted_meanings

class PaginationHandler:
    def __init__(self, scraper):
        self.scraper = scraper
        self.table = Table()
        self.table.add_column("Pagination Step", justify="center", style="#00ffff bold")
        self.table.add_column("Total Scraped", justify="center", style="#ffffff bold")
        self.table.add_column("Next Pagination", justify="center", style="#00ff00 bold")

    def sequential(self, pages):
        results = []
        with Live(self.table, refresh_per_second=1):
            for page in range(1, pages):
                page_results, is_next_pagination, total_scraped = self.scraper.scrape_page(page)
                if self.scraper.kanji_data and page == 1:
                    self.scraper.logger.log(f"""Target Kanji: {self.scraper.kanji}
{self.scraper.kanji_data['Onyomi']}
{self.scraper.kanji_data['Kunyomi']}
Meaning: {self.scraper.kanji_data['Meaning']}
Info: {self.scraper.kanji_data['Info']}
                    """)

                self.table.add_row(f"{page}", f"[green]{len(page_results)}[/]/[red]{total_scraped}[/]", f"{is_next_pagination}")
                results.extend(page_results)
                if not is_next_pagination:
                    break 
        return results

    def concurrent(self, pages, max_workers=10):
        # Thread-safe
        lock = Lock()

        results_merge = []
        stop_event = threading.Event()

        def scrape_page(page, retries=3, backoff_factor=1):
            """
            Wrapper for the scrape function to handle each page with retries.
            """
            for attempt in range(retries):
                try:
                    results, is_next_pagination, total_scraped = self.scraper.scrape_page(page)
                    return (page, results, is_next_pagination, total_scraped)
                except Exception as e:
                    if attempt < retries - 1:
                        time.sleep(backoff_factor * (2 ** attempt))  # Exponential backoff
                    else:
                        return (page, None, None, f"Timeout after {retries} attempts!")

        with Live(self.table, refresh_per_second=2):
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                # Futures thread for each page
                future_to_page = {executor.submit(scrape_page, page): page for page in range(1, pages + 1)}

                for future in concurrent.futures.as_completed(future_to_page):
                    page = future_to_page[future]
                    try:
                        result = future.result()
                        if result is None:
                            continue  # If after many tries, page is still Timeout, then skip.
                        page_num, results, is_next_pagination, total_scraped = result

                        # Acquire lock and update shared resources
                        with lock:
                            if results is not None:
                                # Update the table
                                self.table.add_row(
                                    str(page_num),
                                    f"[green]{len(results)}[/]/[red]{total_scraped}[/]",
                                    "Yes" if is_next_pagination else "No"
                                )

                                results_merge.extend(results)

                                # If there is no next pagination, set the stop_event
                                if not is_next_pagination:
                                    stop_event.set()
                                    # For any remaining futures, is cancelled
                                    for future in future_to_page:
                                        future.cancel()
                            else:
                                # Update the table ONLY if return NULL
                                self.table.add_row(
                                    str(page_num),
                                    f"[red]Timeout![/]",
                                    "Yes" if is_next_pagination else "No"
                                )
                    except Exception as exc:
                        with lock:
                            self.table.add_row(
                                str(page_num),
                                f"[red]Timeout![/]",
                                "Yes" if is_next_pagination else "No"
                            )
                            stop_event.set()
                            # For any remaining futures, is cancelled
                            for future in future_to_page:
                                future.cancel()

        # Make sure all pages up to the last successful page are scraped
        last_page = max(future_to_page.values())
        for page in range(1, last_page + 1):
            if page not in [future_to_page[future] for future in future_to_page if future.done()]:
                # Retry fn:scrape() for missing pages.
                result = scrape_page(page)
                if result:
                    page_num, results, is_next_pagination, total_scraped = result
                    if results is not None:
                        results_merge.extend(results)

        return results_merge

class VocabDisplay:
    def __init__(self, vocab_list, config, scraper):
        self.vocab_list = vocab_list
        self.config = config
        self.scraper = scraper
        self.current_page = 0
        self.selected = set()
        self.console = Console()

    def display_page(self):
        # Clear previous output
        print("\033[H\033[J")
        
        # Display current page items
        start_idx = self.current_page * self.config.pagination_limit
        end_idx = min(start_idx + self.config.pagination_limit, len(self.vocab_list))
        
        scraped_vocabulary_table = Table(caption=f"Scraped Vocabulary\nPage {self.current_page + 1} of {self.total_pages}\nItems {self.current_page * self.config.pagination_limit + 1}-{min((self.current_page + 1) * self.config.pagination_limit, len(self.vocab_list))} of {len(self.vocab_list)}\nTime Taken: {self.scraper_time_elapsed}", show_lines=True)

        scraped_vocabulary_table.add_column("Vocab", justify="center", style="cyan bold")
        scraped_vocabulary_table.add_column("Furigana", style="#00ffff i")
        scraped_vocabulary_table.add_column("Tag", justify="center", style="purple")
        scraped_vocabulary_table.add_column("Meaning", justify="center", style="#00ff00 bold")

        # Enumerated vocabulary items
        for i in range(start_idx, end_idx):
            e_vocab = self.vocab_list[i]
            # Change style if vocabulary was previously copied
            if i in self.selected:
                scraped_vocabulary_table.add_row(
                    f"[blue]{i + 1}. {e_vocab['Vocab']}[/]",
                    f"[blue]{e_vocab['Furi']}[/]",
                    f"[blue]{e_vocab['Tag']}[/]",
                    f"[blue]{e_vocab['Meaning']}[/]"
                )
            else:
                scraped_vocabulary_table.add_row(
                    f"{i + 1}. {e_vocab['Vocab']}", 
                    f"{e_vocab['Furi']}", 
                    f"{e_vocab['Tag']}", 
                    f"{e_vocab['Meaning']}"
                )
        
        self.console.print(scraped_vocabulary_table)
        self.console.rule("[bold #00ff00]Separator")
        # Navigation and copy instructions
        Logger.log("\nNavigation: < (previous) | > (next) | _ (exit)")
        Logger.log("To copy a vocabulary item, enter its number")
        Logger.log(f"""Target Kanji: {self.scraper.kanji}
Onyomi: {self.scraper.kanji_data['Onyomi']}
Kunyomi: {self.scraper.kanji_data['Kunyomi']}
Meaning: {self.scraper.kanji_data['Meaning']}
Info: {self.scraper.kanji_data['Info']}
                        """)
        command = input("Enter command or number: ").strip()
        
        if command == "<":
            self.current_page = max(0, self.current_page - 1)
        elif command == ">":
            self.current_page = min(self.total_pages - 1, self.current_page + 1)
        elif command == "_":
            return False
        elif command.isdigit():
            index = int(command) - 1
            if 0 <= index < len(self.vocab_list):
                e_vocab = self.vocab_list[index]
                formatted_template = self.config.template.format(
                    KANJI=self.scraper.kanji, 
                    VOCAB=r"{{c1::"+e_vocab['Vocab']+r"}}",
                    MEANING=r"{{c2::"+str(r"<br>".join(e_vocab['Meaning']))+r"}}",
                    FURIGANA=r"{{c3::"+str(e_vocab['Furi'])+r"}}",
                    TAG=e_vocab['Tag']
                )
                # Copy to clipboard and mark as copied
                copier.copy(formatted_template)
                self.selected.add(index)
                Logger.log("Recorded to clipboard", "s")
            else:
                Logger.log("Invalid number. Enter a valid vocabulary number.", "c")
        elif command == "k" or command == "kanji":
            formatted_template = self.config.template_kanji.format(
                    KANJI=self.scraper.kanji, 
                    MEANING=self.scraper.kanji_data['Meaning'],
                    ONYOMI=" "+self.scraper.kanji_data['Onyomi'][3:],
                    KUNYOMI=" "+self.scraper.kanji_data['Kunyomi'][4:],
                    INFO=self.scraper.kanji_data['Info']
                )
                # Copy to clipboard
            copier.copy(formatted_template)
            Logger.log("Recorded to clipboard", "s")
        else:
            Logger.log("Use <, >, _ to navigate or enter a number", "c")
        return True

    def run(self):
        self.total_pages = (len(self.vocab_list) + self.config.pagination_limit - 1) // self.config.pagination_limit
        self.scraper_time_elapsed = time.time() - self.scraper.start_time
        while self.display_page():
            pass

class Kanji2Vocab:
    def __init__(self):
        self.config = Config()
        self.logger = Logger()

    def run(self, kanji, pages=20, method='s'):
        scraper = KanjiScraper(kanji, self.config)
        handler = PaginationHandler(scraper)
        
        start_time = time.time()
        if method == 'c':
            results = handler.concurrent(pages)
        else:
            results = handler.sequential(pages)
        elapsed_time = time.time() - start_time

        if not results:
            self.logger.log("No results found", 'f')
            return

        display = VocabDisplay(results, self.config, )
        display.run()

    def main(self):
        if len(sys.argv) == 2:
            if sys.argv[1] == "-c" or sys.argv[1] == "--config":
                self.modify_config()
            elif sys.argv[1] == "-h" or sys.argv[1] == "--help":
                self.show_help()
            else:
                kanji = sys.argv[1]
                self.run(kanji)
        elif len(sys.argv) == 3:
            kanji = sys.argv[1]
            pages = int(sys.argv[2])
            self.run(kanji, pages)
        elif len(sys.argv) == 4:
            kanji = sys.argv[1]
            pages = int(sys.argv[2])
            method = sys.argv[3]
            self.run(kanji, pages, method)
        else:
            kanji = self.input_kanji()
            pages = int(input("Total page: ").strip())
            self.run(kanji, pages)

    def input_kanji(self):
        while True:
            type = Console()
            kanji = type.input("[bold #00ff00]Target Kanji[/]: ").strip()

            if len(kanji) == 1 and kanji.isalpha() and not any(char.isdigit() for char in kanji):
                return kanji 
            else:
                self.logger.log("Invalid input. Enter exactly one kanji character without spaces or digits.", 'f')

    def modify_config(self):
        with open('config.json', 'r', encoding='utf-8') as f:
            current_config = json.load(f)
        
        while True:
            config_table = Table(title="Configuration (config.json)", show_header=True, header_style="bold cyan")
            config_table.add_column("Key", style="orange3", justify="right")
            config_table.add_column("Value", style="yellow")
            
            for key, value in current_config.items():
                if isinstance(value, bool):
                    formatted_value = "✓" if value else "✗"
                elif isinstance(value, list):
                    formatted_value = ", ".join(str(x) for x in value[:5]) + ("..." if len(value) > 5 else "")
                else:
                    formatted_value = str(value)
                    
                config_table.add_row(key, formatted_value)
            
            self.logger.log(config_table, "_")
            
            self.logger.log("\nOptions:", "_")
            self.logger.log("1. Edit value", "_")
            self.logger.log("2. Save & Exit", "_")
            self.logger.log("3. Exit", "_")

            choice = input("\nEnter choice (1-3): ").strip()

            if choice == "1":
                key = input("Enter key to edit: ").strip()
                if key in current_config:
                    current_value = current_config[key]
                    self.logger.log(f"Current value: {current_value}", "i")
                    
                    # Handle different value types
                    if isinstance(current_value, bool):
                        new_value = input("Enter new value (true/false): ").lower() == 'true'
                    elif isinstance(current_value, int):
                        new_value = int(input("Enter new value: "))
                    elif isinstance(current_value, list):
                        new_value = input("Enter new values (comma separated): ").split(',')
                        new_value = [v.strip() for v in new_value]
                    else:
                        new_value = input("Enter new value: ")
                    
                    current_config[key] = new_value
                    self.logger.log(f"Updated {key} to {new_value}", "s")
                else:
                    self.logger.log("Key not found", "f")

            elif choice == "2":
                # Save to file
                with open('config.json', 'w', encoding='utf-8') as f:
                    json.dump(current_config, f, indent=4, ensure_ascii=False)
                self.logger.log("Configuration saved", "s")
                break

            elif choice == "3":
                self.logger.log("Exiting without saving", "w")
                break

            else:
                self.logger.log("Invalid choice", "f")

    def show_help(self):
        self.logger.log("Command list:\n1. -c/--config | To modify config.json\n2. Kanji2Vocab.py [KANJI] [TOTAL_PAGINATION] [PAGE_SCRAPE_METHOD]\n | [KANJI] = Requires any Kanji\n | [TOTAL_PAGINATION] = Require an integer\n | [PAGE_SCRAPE_METHOD] = Either s or c, s = Sequential (one-by-one), c = Concurrent (all-together), default = s\n\nCredit:[#00ffff bold]3oFiz4[/] (Discord, Instagram)", "_")

if __name__ == "__main__":
    app = Kanji2Vocab()
    app.main()