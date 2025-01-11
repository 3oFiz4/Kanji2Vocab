import requests, pyperclip as copier
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
from rich import box
from rich.live import Live
from rich import print as color_print

'''
To-Do:
V. Add a Tag for each Vocabulary in Pagination (e.g. N5, N4, N3, WN29, WN29-20, CMN)
O. Add a Shortener for the formatted meaning (e.g. Suru verb => (suru), Na-Adjective => (な), Adverb => (ADV))
3. Add a search system in Pagination, that able to search meaning, furigana, kanji, or even tags
4. Add a filter system that filters the tag
5. Add a Hiragana-Katakana converter if a certain Vocabulary are confirmed as by their Onyomi
6. Add an extended configuration, editable Template, editable hasLearned
7. Add a CMD GUI (ex. below)

Kanji2Vocab
1. Search Vocab (type. 1[KANJI], ex: 1何)
2. Modify configuration
3. Credit 
4. Exit

8. Add a system when a certain meaning has an example.
V. Improve Pagination system so instead of `NTH. [VOCAB] ([FURIGANA])\n=>[MEANING]` it has a table generated (Clue: Use Rich).
V. Show more logs, such as (total vocabs scraped per page)
11. Make code more readable and less messy :)
12. Improve Scrapper (optional)
13. Add an API integration with an AI Chatbot to automatically creates a Spoiler, and contextual usage of a vocabulary (optional)
14. Add stroke drawing (optional)

Minor fixes
'''

with open('config.json', 'r', encoding='utf-8') as f:
    config = json.load(f)
Kanji = ''
BaseUrl = config['BaseUrl']
hasLearned = list(config['hasLearned'])
Template = config['Template']
TemplateKanji = config['TemplateKanji']
isTemplate = config['isTemplate']
isTagShortened = config['isTagShortened']
isMeaningShortened = config['isMeaningShortened']
PaginationLimit = config['PaginationLimit']
# ----------------- P R O G R A M --------------------------------------
kanji_scraped = None
def inputKanji():
    while True:
        type = Console()
        Kanji = type.input("[bold #00ff00]Target Kanji[/]: ").strip()

        if len(Kanji) == 1 and Kanji.isalpha() and not any(char.isdigit() for char in Kanji):
            return Kanji 
        else:
            Log("Invalid input. Enter exactly one kanji character without spaces or digits.", 'f')

def Log(text, status=0):
    """ 
    A simple Log with color. (credit: Rich), see module.
    """
    if status == "f":
        color_print(f"[red bold][X]{text}[/]") 
    elif status == "s":
        color_print(f"[green bold][V]{text}[/]") 
    elif status == "c":
        color_print(f"[yellow bold][?]{text}[/]") 
    elif status == "w":
        color_print(f"[orange bold][!]{text}[/]") 
    elif status == "i":
        color_print(f"[blue]{text}[/]") 
    elif status == '_':
        color_print(text)
    else:
        color_print(f"[green bold]{text}[/]") 

def isVocab(scrVocab):
    """ 
    Require $scrVocab (scraped Vocabulary)

    Checks whether a $scrVocab pass the requirement, such that:
    1. Each Character must have Kanji or Hiragana 
    2. Each Character must have any character one or more in $hasLearned
    """
    if Kanji not in scrVocab:
        return False
    for eChar in scrVocab:
        if eChar != Kanji and eChar not in hasLearned: 
            return False 
    return True, scrVocab

def shortifyTag(Tag):
    """
    Require $Tag

    Shortify the $Tag, each Tag will be shortened (e.g. JLPT N5 => N5)
    """
    patterns = [
        (r'\bJLPT N(\d+)\b', r'N\1'), 
        (r'\bWanikani level (\d+)\b', r'WN\1'),
        (r'\bCommon word\b', 'CMN') 
    ]
    
    for pattern, replacement in patterns:
        Tag = re.sub(pattern, replacement, Tag)
    
    return Tag.strip()

def shortifyMeaning(Meaning):
    """
    Require $Meaning

    Shortify the $Meaning, each meaning label will be shortened (e.g. Noun => N.)
    """
    pattern_map = {
        'Noun': 'N.',
        'Suru verb': '(suru)',
        'Transitive verb': 'Tv',
        'Intransitive verb': 'Iv',
        'Wikipedia definition': 'Wiki',
        'Adverb (fukushi)': 'Adv.'
    }
    
    for i in range(len(Meaning)):
        meaning = Meaning[i]
        
        def replace_terms(match):
            term = match.group(1).strip()
            if term in pattern_map:
                return f"({pattern_map[term]})"
            return term

        meaning = re.sub(r'\((.*?)\)', replace_terms, meaning)
        Meaning[i] = meaning.strip()
    
    return Meaning

def toOnyomi(value, kanji):
        '''
        Convert only matching onyomi parts from hiragana to katakana
        For example: にんげん -> ニンげん (because にん matches the onyomi ニン)
        '''
        # Clean up onyomi readings - remove 'On:' prefix and get clean list
        onyomi_list = [reading.replace('On:', '').strip() for reading in kanji['Onyomi'].split('、')]
        
        result = value
        for onyomi in onyomi_list:
            # Convert onyomi to hiragana for comparison
            onyomi_hiragana = ''.join(
                chr(ord(char) - 0x60) if 'ァ' <= char <= 'ヶ' else char 
                for char in onyomi
            )
            
            # If this onyomi reading exists in hiragana form, replace it with katakana
            if onyomi_hiragana in result:
                result = result.replace(onyomi_hiragana, onyomi)
        
        return result

def scrape(Kanji, pnth):
    """
    Require $Kanji, $p(agination)

    Used to scrape one-by-one per $p of each target $Kanji, collecting below: 
    - Vocabulary
    - Furigana 
    - Meaning (shortened)
    - Tag (shortened)
    """
    global kanji_scraped
    # Session for connection pooling
    session = requests.Session()
    
    # Add timeout and headers for better reliability
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    try:
        r = requests.get(BaseUrl+f'?page={pnth}')
        r.raise_for_status()
    except requests.RequestException as e:
        Log(f"Failure.\nError: {str(e)}", "f")
        return []

    p = BeautifulSoup(r.content, 'lxml')  # lxml parser for better performance

    results = []
    totalScraped = 0

    # Check if "More Words" exist
    isNextPagination = bool(p.select_one('a.more'))

    # CSS selectors to get all elements at once
    targetElementCharacter = p.select("div.concept_light-readings.japanese.japanese_gothic > div.concept_light-representation")
    targetElementMeaning = p.select("div.meanings-wrapper") 
    targetElementTag = p.select("div.concept_light-status")

    if isNextPagination or (targetElementCharacter, targetElementMeaning, targetElementTag):
        # Regex patterns
        text_pattern = "span.text"
        furigana_pattern = "span.furigana"
        tag_pattern = ".concept_light-tag.label"

        if pnth == 1: # It is only available at first page.
            targetElementKanji = p.select_one("div.kanji_light_content")
            # Regex patterns (Kanji Only)
            kanji_onyomi_pattern = "div.on.readings" # This only returns the div header
            kanji_kunyomi_pattern = "div.kun.readings" # This only returns the div header
            kanji_meaning_pattern = "div.meanings.english.sense" # This only returns the div header
            kanji_info_pattern = "div.info.clearfix" # This only returns the div header

            # Kanji Element (they're accessed only one time, when a second loop happen *in the sense of page is non-default*, this process are ignored.)
            scrKanjiOnyomi = targetElementKanji.select_one(kanji_onyomi_pattern)
            scrKanjiKunyomi = targetElementKanji.select_one(kanji_kunyomi_pattern)
            scrKanjiMeaning = targetElementKanji.select_one(kanji_meaning_pattern)
            scrKanjiInfo = targetElementKanji.select_one(kanji_info_pattern)

            # If one of them or both exist.
            if scrKanjiOnyomi and scrKanjiKunyomi:
                # Unwrap all <a> tags within Onyomi and Kunyomi
                for onyomi, kunyomi in zip(scrKanjiOnyomi.find_all("a", recursive=True), scrKanjiKunyomi.find_all("a", recursive=True)):
                    onyomi.unwrap()
                    kunyomi.unwrap()
                kanjiOnyomi = scrKanjiOnyomi.get_text(strip=True, separator="")
                kanjiKunyomi = scrKanjiKunyomi.get_text(strip=True, separator="")
            elif scrKanjiOnyomi:
                # Unwrap all <a> tags within Onyomi
                for onyomi in scrKanjiOnyomi.find_all("a", recursive=True):
                    onyomi.unwrap()
                kanjiOnyomi = scrKanjiOnyomi.get_text(strip=True, separator="")
                kanjiKunyomi = ""
            elif scrKanjiKunyomi:
                # Unwrap all <a> tags within Kunyomi
                for kunyomi in scrKanjiKunyomi.find_all("a", recursive=True):
                    kunyomi.unwrap()
                kanjiKunyomi = scrKanjiKunyomi.get_text(strip=True, separator="")
                kanjiOnyomi = ""
            else:
                kanjiOnyomi = ""
                kanjiKunyomi = ""

            kanjiMeaning = scrKanjiMeaning.get_text(strip=True, separator="") if scrKanjiMeaning else ""
            kanjiInfo = scrKanjiInfo.get_text(strip=True, separator="") if scrKanjiInfo else ""

            kanji = {
                "Info": kanjiInfo,
                "Onyomi": kanjiOnyomi,
                "Kunyomi": kanjiKunyomi,
                "Meaning": kanjiMeaning
            }
            # Save the retrieved kanji into the global kanji_scraped
            kanji_scraped = kanji

        for eTargetElementCharacter, eTargetElementMeaning, eTargetElementTag in zip(targetElementCharacter, targetElementMeaning, targetElementTag):
            # Cache selector results
            text_elem = eTargetElementCharacter.select_one(text_pattern)
            furigana_elem = eTargetElementCharacter.select_one(furigana_pattern)
            
            scrVocab = text_elem.get_text(strip=True) if text_elem else None
            scrFuri = furigana_elem.get_text(strip=True) if furigana_elem else None
            scrTags = eTargetElementTag.select(tag_pattern)
            # Log(f"{eTargetElementCharacter},{eTargetElementMeaning},{eTargetElementTag}")
            totalScraped += 1

            if isVocab(scrVocab) and scrFuri:
                
                # Build tag contents list more efficiently
                tagContents = [tag.get_text(strip=True) for tag in scrTags if tag]
                tagContents = [content for content in tagContents if content]

                # Join tag contents into a single string
                Tag = shortifyTag(', '.join(tagContents)) if isTagShortened else ', '.join(tagContents)
                
                # Process meaning
                Meaning = shortifyMeaning(formatMeaning(eTargetElementMeaning)) if isMeaningShortened else formatMeaning(eTargetElementMeaning)
                
                results.append({
                    "Vocab": scrVocab,
                    "Furi": toOnyomi(scrFuri,kanji_scraped),
                    "Meaning": Meaning,
                    "Tag": Tag
                })

        return results, isNextPagination, totalScraped
    # Whenever you modify the return above, you should check out for PaginationHandler class and see both two methods, that handles these.
    else:
        return [], False, 0

# Had to create another utility function, to avoid messy code.
def formatMeaning(html):
    """
    Require $html

    Format the raw $HTML of a Vocabulary to be human-readable
    """
    fP = BeautifulSoup(str(html), 'html.parser')
    meanings = fP.find_all('div', class_='meaning-wrapper')
    tags = fP.find_all('div', class_='meaning-tags')

    formatted_meanings = []

    for i, meaning in enumerate(meanings):
        meaning_text = meaning.find('span', class_='meaning-meaning')
        meaning_text = meaning_text.text.strip() if meaning_text else None
        tag_text = tags[i].text.strip() if i < len(tags) else None
        if meaning_text:
            formatted_meaning = f"{meaning_text} ({tag_text})" if tag_text else meaning_text
            formatted_meanings.append(formatted_meaning)
    
    return formatted_meanings

class paginationHandler:
    # Handle pagination (Sequential)
    def Sequential(Kanji, p):
        """
        Require $Kanji, $p(agination)

        Used to handle $p for each kanji scraper
        """

        Pagination = Table()
        Pagination.add_column("Pagination Step", justify="center", style="#00ffff bold")
        Pagination.add_column("Total Scraped", justify="center", style="#ffffff bold")
        Pagination.add_column("Next Pagination", justify="center", style="#00ff00 bold")

        resultsMerge = []
        with Live(Pagination, refresh_per_second=1):
            for page in range(1, p):
                results, isNextPagination, totalScraped = scrape(Kanji, page)
                if kanji_scraped and page == 1:
                    Log(f"""Target Kanji: {Kanji}
{kanji_scraped['Onyomi']}
{kanji_scraped['Kunyomi']}
Meaning: {kanji_scraped['Meaning']}
Info: {kanji_scraped['Info']}
                        """)

                Pagination.add_row(f"{page}", f"[green]{len(results)}[/]/[red]{totalScraped}[/]", f"{isNextPagination}")
                resultsMerge.extend(results)
                if not isNextPagination:
                    break 
        return resultsMerge

    # Handle pagination (Concurrent Method) * Still Broken: Do not Use*
    def Concurrent(Kanji, p):
        """
        Require $Kanji, $p(agination)

        Used to handle $p for each kanji scraper using multi-threading
        In the prior version, this method was triggered sequentially, which took a long time.
        With concurrent method, this is highly faster than before:

        For 80V (out of 10P) target 人 it took ~17.729 seconds (Sequential Method)
        For 87V (out of 10P) target 人 it took ~3.413 seconds (Concurrent Method)
        """
        Pagination = Table()
        Pagination.add_column("Pagination Step", justify="center", style="#00ffff bold")
        Pagination.add_column("Total Scraped", justify="center", style="#ffffff bold")
        Pagination.add_column("Next Pagination", justify="center", style="#00ff00 bold")

        # Thread-safe queue to store results
        result_queue = Queue()
        stop_event = threading.Event()
        max_page = threading.Event()
        
        # Use a thread-safe list to store max page number
        max_page_num = Value('i', p)

        def scrape_page(page_num):
            if stop_event.is_set() and page_num > max_page_num.value:
                return None
            
            results, isNextPagination, totalScraped = scrape(Kanji, page_num)

            # If no next pagination, update max page number
            if not isNextPagination:
                with max_page_num.get_lock():
                    max_page_num.value = min(max_page_num.value, page_num)
                max_page.set()

            return {
                'page': page_num,
                'results': results,
                'isNextPagination': isNextPagination,
                'totalScraped': totalScraped
            }

        resultsMerge = []
        page_results = []  # Store results with page numbers for sorting
        with Live(Pagination, refresh_per_second=1):
            with ThreadPoolExecutor(max_workers=p) as executor:
                # Submit initial batch of tasks
                future_to_page = {
                    executor.submit(scrape_page, page_num): page_num 
                    for page_num in range(1, p+1)
                }

                # Process results as they complete
                for future in as_completed(future_to_page):
                    page_result = future.result()
                    if page_result is None:
                        continue

                    page = page_result['page']
                    results = page_result['results']
                    isNextPagination = page_result['isNextPagination']
                    totalScraped = page_result['totalScraped']

                    if page <= max_page_num.value:  # Only process results up to max page
                        Pagination.add_row(
                            f"{page}", 
                            f"[green]{len(results)}[/]/[red]{totalScraped}[/]", 
                            f"{isNextPagination}"
                        )
                        
                        # Store results accordingly with page number
                        page_results.append((page, results))
                    
                    # If no next pagination, set stop event
                    if not isNextPagination:
                        stop_event.set()
                        # print(f"Full Stop at pagination {page}")

        # Sort results by page number and merge
        page_results.sort(key=lambda x: x[0])  # Sort by page number
        for _, results in page_results:
            resultsMerge.extend(results)

        return resultsMerge

def run(Kanji, limit=20, method="s"):
    """
    Require $Kanji, *limit

    Scrape a Kanji, by *limit of page
    """
    # setup_console() # Fix smoe CMD unable to represent the japanese character.
    
    # List of Vocabs with limit
    
    timeStartScraper = time.time()
    if method == "c": Scraper = paginationHandler.Concurrent(Kanji, limit)  # passing limit to paginationHandler
    elif method == "s": Scraper = paginationHandler.Sequential(Kanji, limit)  # passing limit to paginationHandler
    timeEndScraper = time.time()

    scraperTimeElapsed = timeEndScraper - timeStartScraper

    if not Scraper:
        Log("Nil.", "f")
        return
    
    # Pagination settings    
    paginationLimit = PaginationLimit  # number of items per page
    total_items = len(Scraper)
    current_page = 0
    total_pages = (total_items + paginationLimit - 1) // paginationLimit
    
    while True:
        # Clear previous output
        print("\033[H\033[J")
        
        # # Show pagination info (Old Version VVV)
        # Log(f"Page {current_page + 1} of {total_pages}")
        # Log(f"Items {current_page * paginationLimit + 1}-{min((current_page + 1) * paginationLimit, total_items)} of {total_items}")
        # # Log("Scraped Vocabulary:")
        
        # Display current page items
        start_idx = current_page * paginationLimit
        end_idx = min(start_idx + paginationLimit, total_items)
        
        scrapedVocabularyTable = Table(caption=f"Scraped Vocabulary\nPage {current_page + 1} of {total_pages}\nItems {current_page * paginationLimit + 1}-{min((current_page + 1) * paginationLimit, total_items)} of {total_items}\nTime Taken: {scraperTimeElapsed}", show_lines=True)

        scrapedVocabularyTable.add_column("Vocab", justify="center", style="cyan bold")
        scrapedVocabularyTable.add_column("Furigana", style="#00ffff i")
        scrapedVocabularyTable.add_column("Tag", justify="center", style="purple")
        scrapedVocabularyTable.add_column("Meaning", justify="center", style="#00ff00 bold")

        # Enumerated vocabulary items
        for i in range(start_idx, end_idx):
            eVocab = Scraper[i]
            scrapedVocabularyTable.add_row(f"{i + 1}. {eVocab['Vocab']}", f"{eVocab['Furi']}", f"{eVocab['Tag']}", f"{eVocab['Meaning']}")
            # This is default! VVV
            # color_print(f"{i + 1}. [cyan bold]{eVocab['Vocab']}[/] ([#0ff i]{eVocab['Furi']})[/] <{eVocab['Tag']}> \n=> [#0f0 bold]{eVocab['Meaning']}[/]")
        
        scrapedVocabularyConsole = Console()
        
        scrapedVocabularyConsole.print(scrapedVocabularyTable)
        scrapedVocabularyConsole.rule("[bold #00ff00]Separator")
        # Navigation and copy instructions
        Log("\nNavigation: < (previous) | > (next) | _ (exit)")
        Log("To copy a vocabulary item, enter its number")
        Log(f"""Target Kanji: {Kanji}
Onyomi: {kanji_scraped['Onyomi']}
Kunyomi: {kanji_scraped['Kunyomi']}
Meaning: {kanji_scraped['Meaning']}
Info: {kanji_scraped['Info']}
                        """)
        command = input("Enter command or number: ").strip()
        
        if command == "<":
            current_page = max(0, current_page - 1)
        elif command == ">":
            current_page = min(total_pages - 1, current_page + 1)
        elif command == "_":
            break
        elif command.isdigit():
            index = int(command) - 1
            if 0 <= index < total_items:
                eVocab = Scraper[index]
                formatted_template = Template.format(
                    KANJI=Kanji, 
                    VOCAB=r"{{c1::"+eVocab['Vocab']+r"}}",
                    MEANING=r"{{c2::"+str(r"<br>".join(eVocab['Meaning']))+r"}}",
                    FURIGANA=r"{{c3::"+str(eVocab['Furi'])+r"}}",
                    TAG=eVocab['Tag']
                )
                # Copy to clipboard
                copier.copy(formatted_template)
                Log("Recorded to clipboard", "s")
            else:
                Log("Invalid number. Enter a valid vocabulary number.", "c")
        elif command == "k" or command == "kanji":
            formatted_template = TemplateKanji.format(
                    KANJI=Kanji, 
                    MEANING=kanji_scraped['Meaning'],
                    ONYOMI=" "+kanji_scraped['Onyomi'][3:],
                    KUNYOMI=" "+kanji_scraped['Kunyomi'][4:],
                    INFO=kanji_scraped['Info']
                )
                # Copy to clipboard
            copier.copy(formatted_template)
            Log("Recorded to clipboard", "s")
        else:
            Log("Use <, >, _ to navigate or enter a number", "c")

def main():
    global BaseUrl, Kanji
    # a1 = Kanji, a2 = Total Pagination, a3 = Method
    if len(sys.argv) == 2:
        args1 = sys.argv[1]
        Kanji = args1
        BaseUrl = config['BaseUrl'].format(Kanji=args1)
        run(args1, 20)
    elif len(sys.argv) == 3:
        args1 = sys.argv[1]
        Kanji = args1
        args2 = sys.argv[2]
        BaseUrl = config['BaseUrl'].format(Kanji=args1)
        run(args1, int(args2))
    elif len(sys.argv) == 4:
        args1 = sys.argv[1]
        Kanji = args1
        args2 = sys.argv[2]
        args3 = sys.argv[3]
        BaseUrl = config['BaseUrl'].format(Kanji=args1)
        run(args1, int(args2), args3)
    else:
        Kanji = inputKanji()
        BaseUrl = config['BaseUrl'].format(Kanji=Kanji)
        howmuch = int(input("Total page: ").strip())
        run(Kanji, howmuch)

if __name__ == "__main__":
    main()