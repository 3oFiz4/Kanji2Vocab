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
import openai
import aiohttp as aio
import asyncio as io
from itertools import cycle
import os
from dotenv import load_dotenv
load_dotenv()

'''
To-Do:
V. Add a Tag for each Vocabulary in Pagination (e.g. N5, N4, N3, WN29, WN29-20, CMN)
O. Add a Shortener for the formatted meaning (e.g. Suru verb => (suru), Na-Adjective => (な), Adverb => (ADV))
3. Add a search system in Pagination, that able to search meaning, furigana, kanji, or even tags
4. Add a filter system that filters the tag
V. Add a Hiragana-Katakana converter if a certain Vocabulary are confirmed as by their Onyomi
O. Add an extended configuration, editable Template, editable hasLearned
V. Add a CMD GUI (ex. below)

Kanji2Vocab
1. Search Vocab (type. 1[KANJI], ex: 1何)
2. Modify configuration
3. Credit 
4. Exit

V. Add a system when a certain meaning has an example.
V. Improve Pagination system so instead of `NTH. [VOCAB] ([FURIGANA])\n=>[MEANING]` it has a table generated (Clue: Use Rich).
V. Show more logs, such as (total vocabs scraped per page)
11. Make code more readable and less messy :) (already messy btw, so whats the point?)
V. Improve Scrapper (optional) = Modified to use LXML, scrape Kanji also, i guess thats an improvement XD
13. Add an API integration with an AI Chatbot to automatically creates a Spoiler, and contextual usage of a vocabulary (optional)
V. Add stroke drawing (optional)
V. Add colored for some tags and info
V. Add example sentence

Credit: 3oFiz4

Additional Idea:
Accomodate Kanji(forgot the name ;-; ) which accomodate more examples, and kanji info.
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
AnkiDeck = config['AnkiDeck']
AnkiModelVocabulary = config['AnkiModelVocabulary']
AnkiModelKanji = config['AnkiModelKanji']
VocabularyMethod = config['VocabularyMethod']
isColored = config['isColored']
isAutomatic = config['isAutomatic']
# ----------------- P R O G R A M --------------------------------------
kanji_scraped = None
raw_svg = None
class Anki:
    class Interactor:
        def __init__(self, url="http://localhost:8765"): # Assuming the user did not change the port.
            self.url = url
            self.session = requests.Session()

        async def invoke(self, action, **params):
            """
            Sends a request to the AnkiConnect API asynchronously and returns the result.
            """
            payload = {
                "action": action,
                "version": 6,
                "params": params,
            }
            response = self.session.post(self.url, json=payload)
            if response.status_code != 200:
                raise Exception(f"Anki::HTTP [ERR]: {response.status_code} when {response.text}")
            response_data = response.json()
            if "error" in response_data and response_data["error"] is not None:
                raise Exception(f"Anki::Interactor [ERR]: {response_data['error']}")
            return response_data["result"]
    
    class POST:
        def __init__(self, anki_connect):
            self.anki_connect = anki_connect

        # Testing purpose.
        # def Specify(self, deck_name):
        #     """
        #     Ensures the specified deck exists. Creates it if not.
        #     """
        #     decks = self.anki_connect.invoke("deckNames")
        #     if deck_name not in decks:
        #         Log(f"Deck '{deck_name}' not found.", "f")
        #     else:
        #         Log(f"Found Deck '{deck_name}'.")

        async def NoteCreate(self, value, model):
            """
            Creates a note in the specified deck with the provided fields.
            """
            # Ensure the note_fields dict contains the necessary field names
            if not value:
                raise ValueError("Should at least contain one field.")
            
            note = {
                "deckName": AnkiDeck,
                "modelName": model,
                "fields": value,
                "tags": ["Kanji2VocabCreation"],
                "options": {
                    "allowDuplicate": False
                }
            }

            try:
                result = await self.anki_connect.invoke("addNote", note=note)
                print(result)
                if result is not None:
                    return True
                else:
                    return False
            except Exception as e:
                Log(f"An error occurred: {str(e)}", 'f')

# AnkiConnect Initialization
anki_interact = Anki.Interactor()
anki = Anki.POST(anki_interact)
if anki_interact and anki:
    print("AnkiAPI Connected")

class APIKey:
    """
    continuously cycle through a list of API keys.
    """
    def __init__(self, key_prefixes: list, key_format="API_KEY_{}"):
        """
        Works by fetching key values from environment variables.
        
        Args:
            key_prefixes: A list of indices or identifiers (e.g., [0, 1, 2]). -> This means there is API_KEY_0, API_KEY_1, API_KEY_2
            key_format: The format string for the environment variable name.
        """
        # Build the list of actual key values by looking them up in os.environ
        key_list = []
        for prefix in key_prefixes:
            key_name = key_format.format(prefix)
            key_value = os.getenv(key_name)
            if key_value:
                key_list.append(key_value)
            else:
                Log(f"Warning: Environment variable {key_name} not found.", "e")

        if not key_list:
            raise ValueError("No valid API keys were loaded.")

        # Create a cycling iterator that will rotate through the keys indefinitely
        self.keys = cycle(key_list)
        # Store the current key for easy access
        self.current_key = next(self.keys)

    def rotate(self) -> str:
        """
        Rotates to next key in the sequence and returns it.
        """
        self.current_key = next(self.keys)
        return self.current_key

    def this(self) -> str:
        """
        Returns the current active key.
        """
        return self.current_key
ai_key = APIKey([0, 1])

def ResponseAI(input, prompt=""):
    if input == "":
        return "No input given"
    final_input = f"""{prompt}\n---\n{input}""" if prompt else input
    client = openai.OpenAI(
    api_key=ai_key.this(),
    base_url=os.getenv("AI_URL"),)
    
    try:
        chat = client.chat.completions.create(
            model=os.getenv("AI_MODEL"),
            messages=[{"role": "user", "content": final_input}],
        )
    except Exception as e:
        return e 
    return chat.choices[0].message.content


def update_kanji(kanji_char):
    global hasLearned, config
    if kanji_char not in hasLearned:
        hasLearned.append(kanji_char)
        config['hasLearned'] = ''.join(hasLearned)
        with open('config.json', 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=4, ensure_ascii=False)

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
        color_print(f"[red bold][X] {text}[/]") 
    elif status == "s":
        color_print(f"[green bold][V] {text}[/]") 
    elif status == "c":
        color_print(f"[yellow bold][?] {text}[/]") 
    elif status == "w":
        color_print(f"[orange bold][!] {text}[/]") 
    elif status == "i":
        color_print(f"[blue]{text}[/]") 
    elif status == '_':
        color_print(text)
    else:
        color_print(f"[green bold][V] {text}[/]") 

def _c(text, hex_color):
    x = f'<span id="k2v-colored" style="color:#{hex_color}">{text}</span>'  # Non-BaseConsole version
    return x

def c_(text):
    pattern = r'<span id="k2v-colored" style="color:#(\w{6})">(.*?)<\/span>'
    transformed_text = re.sub(pattern, r'[#\1]\2[/]', text,  flags=re.DOTALL | re.IGNORECASE)
    return transformed_text

# These two functions above is brothers. _c is used for output. c_ is used for console. The color that appears in output and console are different. c_ simply converting them.

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
    # First replace semicolons with commas
    Meaning = [m.replace(';', ',') for m in Meaning]
    
    # Replace specific patterns
    pattern_map = {
        'Adverb (fukushi)': _c("adv", "00ff7f"),
        'Noun which may take the genitive case particle \'no\'': 'adjの',
        'Noun': 'n',
        'Suru verb': _c('vする', '216bd6'),
        'Transitive verb': 'vt', 
        'Intransitive verb': 'vi',
        'Ichidan verb': _c('v1', "ff0000"),
        'Godan verb': _c('v5', '00ffff'),
        'Na-adjective (keiyodoshi)': _c('adjな', 'ff00ff'),
        'I-adjective (keiyoushi)': _c('adjい', '00ff00'),
        'Wikipedia definition': _c("wk", "c0c0c0"),
        'Expressions (phrases, clauses, etc.)': _c("exp", "6a5acd"),
        '(Other forms)': _c("alt", "708090"),
        'Conjunction': 'conj',
        '------': '-------', 
        'Usually written using kana alone , usu. as': _c("KANA usu. AS:", "ff1493"),
        'Usually written using kana alone , as': _c("KANA AS:", "ff1493"),
        'Usually written using kana alone': _c("KANA", "ff1493"),
        'Antonym:': 'ANT:',
        'esp.': 'ESP:',
        'Auxiliary verb': _c('v-AUX', "ff0094"),
        'after the -masu stem of a verb': _c('v-ます', "ff0094"),
        'after the -te form of a verb': _c('v-て', "ff0094")
    }
    

    processed = []
    for i, meaning in enumerate(Meaning, 1):
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

def parseColor(value, kanji):
    '''
    Convert matching onyomi parts from hiragana to katakana with one color,
    and kunyomi parts with another color.
    For example: にんげん -> ニンげん (because にん matches the onyomi ニン)
    '''
    # Initialize onyomi and kunyomi lists if they exist
    onyomi_list = []
    kunyomi_list = []

    if kanji.get('Onyomi'):
        # Clean up onyomi readings - remove 'On:' prefix and get clean list
        onyomi_list = [reading.replace('On:', '').strip() for reading in kanji['Onyomi'].split('、')]

    if kanji.get('Kunyomi'):
        # Clean up kunyomi readings - remove 'Kun:' prefix and '-' characters, then get clean list
        kunyomi_list = [reading.replace('Kun:', '').replace('-', '').strip() for reading in kanji['Kunyomi'].split('、')]

    result = value

    for onyomi in onyomi_list:
        # Convert onyomi to hiragana for comparison
        onyomi_hiragana = ''.join(
            chr(ord(char) - 0x60) if 'ァ' <= char <= 'ヶ' else char 
            for char in onyomi
        )
        
        # If this onyomi reading exists in hiragana form, replace it with katakana
        if onyomi_hiragana in result:
            result = result.replace(onyomi_hiragana, f"[#00aaff]{onyomi}[/]")

    for kunyomi in kunyomi_list:
        # Same thing like above but for Kunyomi
        kunyomi_hiragana = ''.join(
            chr(ord(char) - 0x60) if 'ァ' <= char <= 'ヶ' else char 
            for char in kunyomi
        )
    
        if kunyomi_hiragana in result:
            result = result.replace(kunyomi_hiragana, f"[#ffff00]{kunyomi}[/]")

    return result


def uni(text):
    '''
    Gets the unicode of a $:text
    '''
    unicode = None
    for char in text:
        unicode_number = ord(char)
        unicode = f"{unicode_number:05X}"  # Changed to 5 digits to ensure leading 0
    return unicode


async def kanjiStrokeScrape(Kanji):
    async with aio.ClientSession() as session:
        URL = f"https://www.lemoda.net/kvg/{uni(Kanji).lower()}.svg" # Why lower()? Because the URL only accepts it when the word is lowercase, ant not uppercase.
        async with session.get(URL) as response:
            if response.status == 200:
                svg_content = await response.text()
                start_index = svg_content.find('<svg')
                end_index = svg_content.find('</svg>', start_index) + len('</svg>')
                first_svg_element = svg_content[start_index:end_index]
                
                soup = BeautifulSoup(first_svg_element, 'xml')
                g_element = soup.find('g', id=lambda x: x and x.startswith('kvg:StrokePaths'))
                if g_element:
                    g_element['style'] = 'stroke:#fff; background:#000'
                modified_svg = str(soup)
                return modified_svg

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
        r = requests.get(BaseUrl+f'?page={pnth}', headers=headers)
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
                    "Furi": parseColor(scrFuri,kanji_scraped),
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

    # Only applies when filtering the meaning!
    # 1. Striped away the PARENT element tag.
    # 2. Striped away the CHILD element tag EXCEPT <a href>
    def Filter(raw):
        result = []
        for elem in raw.descendants:
            if isinstance(elem, str):  
                result.append(elem.strip())  # Keep text
            elif elem.name == "a" and elem.has_attr("href"):
                result.append(str(elem))  # Keep <a> tag with href
                
        return " ".join(result).strip()
    
    def Process(sentence):
        # Convert soup to string
        sentence_html = str(sentence)
        
        # Handle cases where the kanji is inside <span class="hit">
        def replacer(match):
            furigana = match.group('f')
            kanji = match.group('k_hit') or match.group('k_normal')  # Use <span class="hit"> if available, else normal kanji
            return f"{kanji}[{furigana}]"

        pattern = re.compile(
            r'<li class="clearfix">\s*'
            r'<span class="furigana">(?P<f>.*?)</span>\s*'
            r'<span class="unlinked">(?:<span class="hit">(?P<k_hit>.*?)</span>|(?P<k_normal>.*?))</span>\s*'
            r'</li>',
            re.DOTALL
        )

        # Apply regex substitution
        sentence_html = re.sub(pattern, replacer, sentence_html)

        # Parse back to BeautifulSoup and extract plain text
        sentence_soup = BeautifulSoup(sentence_html, 'html.parser')
        return sentence_soup.get_text(separator=" ", strip=True)

    for i, meaning in enumerate(meanings):
        meaning_text = meaning.find('span', class_='meaning-meaning') # Raw HTML
        meaning_text = Filter(meaning_text) if meaning_text else None
        meaning_info = meaning.find('span', class_='supplemental_info')
        meaning_info = Filter(meaning_info) if meaning_info else None
        meaning_ex = meaning.find('div', class_='sentence')
        meaning_ex = Process(meaning_ex) if meaning_ex else None
        ex_exist = _c(f"\n「{meaning_ex}」", "424242") if meaning_ex else ""
        info_exist = _c(f"\n【 ", "e39a0c") + meaning_info + _c(f"】", "e39a0c") if meaning_info else ""

        tag_text = tags[i].text.strip() if i < len(tags) else None
        if meaning_text:
            formatted_meaning = f"{meaning_text} ({tag_text}){info_exist}{ex_exist}" if tag_text else meaning_text
            formatted_meanings.append(formatted_meaning)
    
    return formatted_meanings

def cvHTML(meaning):
    # Regex untuk mendeteksi pola [#xxxxxx]text[/]
    pattern = r'\[#([0-9A-Fa-f]{6})\](.*?)\[/\]'
    # Mengganti pola tersebut dengan tag HTML
    return re.sub(pattern, r'<span style="color:#\1">\2</span>', meaning)

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

    # Handle pagination (Concurrent)
    def Concurrent(Kanji, p, max_workers=10):
        """
        Require $Kanji, $p(agination)

        Used to handle $p for each kanji scraper using multi-threading and retries if a certain page returns timeout.
        In the prior version, this method was triggered sequentially, which took a long time.
        With concurrent method, this is highly faster than before:

        For 80V (out of 10P) target 人 it took ~17.729 seconds (Sequential Method)
        For 87V (out of 10P) target 人 it took ~3.413 seconds (Concurrent Method)

        Thanks to ChatGPT for the retry idea: When I wrote this function, I was stuck on thinking... How may I avoid persistent timeout? Then ChatGPT goes, here fam.
        """
        
        Pagination = Table()
        Pagination.add_column("Pagination Step", justify="center", style="#00ffff bold")
        Pagination.add_column("Total Scraped", justify="center", style="#ffffff bold")
        Pagination.add_column("Next Pagination", justify="center", style="#00ff00 bold")

        # Thread-safe
        lock = Lock()

        resultsMerge = []
        stop_event = threading.Event()

        def scrape_page(page, retries=3, backoff_factor=1):
            """
            Wrapper for the scrape function to handle each page with retries.

            Thanks to ChatGPT for the retry idea: When I wrote this function, I was stuck on thinking... 
            How may I avoid persistent timeout? Then ChatGPT goes, here fam.
            """
            for attempt in range(retries):
                try:
                    results, isNextPagination, totalScraped = scrape(Kanji, page)
                    return (page, results, isNextPagination, totalScraped)
                except Exception as e:
                    if attempt < retries - 1:
                        time.sleep(backoff_factor * (2 ** attempt))  # Exponential backoff, Credit:ChatGPT.
                    else:
                        return (page, None, None, f"Timeout after {retries} attempts!")

        with Live(Pagination, refresh_per_second=2):
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                # Futures thread for each page
                future_to_page = {executor.submit(scrape_page, page): page for page in range(1, p + 1)}

                for future in concurrent.futures.as_completed(future_to_page):
                    page = future_to_page[future]
                    try:
                        result = future.result()
                        if result is None:
                            continue  # If after many tries, page is still Timeout, then skip.
                        page_num, results, isNextPagination, totalScraped = result

                        # Acquire lock and update shared resources
                        with lock:
                            if results is not None:
                                # Update the table
                                Pagination.add_row(
                                    str(page_num),
                                    f"[green]{len(results)}[/]/[red]{totalScraped}[/]",
                                    "Yes" if isNextPagination else "No"
                                )

                                resultsMerge.extend(results)

                                # If there is no next pagination, set the stop_event
                                if not isNextPagination:
                                    stop_event.set()
                                    # For any remaining futures, is cancelled
                                    for future in future_to_page:
                                        future.cancel()
                            else:
                                # Update the table ONLY if return NULL
                                Pagination.add_row(
                                    str(page_num),
                                    f"[red]Timeout![/]",
                                    "Yes" if isNextPagination else "No"
                                )
                    except Exception as exc:
                        with lock:
                            Pagination.add_row(
                                str(page_num),
                                f"[red]Timeout![/]",
                                "Yes" if isNextPagination else "No"
                            )
                            stop_event.set()
                            # For any remaining futures, is cancelled
                            for future in future_to_page:
                                future.cancel()

        # Make sure all pages up to the last successful page are scraped
        # There is a bug where a certain number are succesfully scraped, but the number below are unsuccesfully scraped.
        last_page = max(future_to_page.values())
        for page in range(1, last_page + 1):
            if page not in [future_to_page[future] for future in future_to_page if future.done()]:
                # Retry fn:scrape() for missing pages.
                result = scrape_page(page)
                if result:
                    page_num, results, isNextPagination, totalScraped = result
                    if results is not None:
                        resultsMerge.extend(results)

        return resultsMerge

    # BROKEN: Handle pagination (Concurrent Method) *This is an old version of fn:Concurrent that I left here.*
    def OldConcurrent(Kanji, p):
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
def normalize_jp(s):
    # remove HTML tags
    s = re.sub(r'<[^>]+>', '', s)
    # remove bracketed furigana [お]
    s = re.sub(r'\[[^\]]+\]', '', s)
    # remove spaces between Japanese chars
    s = re.sub(r'(?<=\w)\s+(?=\w)', '', s)
    # collapse newlines
    s = s.replace("\n", "")
    return s
async def run(Kanji, limit=20, method="c"):
    """
    Require $Kanji, *limit

    Scrape a Kanji by *limit of pages, allow the user to select vocabulary items,
    then batch-process the selected ones by requesting extra Kanji explanations via an API.
    """
    timeStartScraper = time.time()
    if method == "c":
        Scraper = paginationHandler.Concurrent(Kanji, limit)
    elif method == "s":
        Scraper = paginationHandler.Sequential(Kanji, limit)
    timeEndScraper = time.time()
    scraperTimeElapsed = timeEndScraper - timeStartScraper

    if not Scraper:
        Log("Nil.", "f")
        return

    # Pagination settings    
    paginationLimit = PaginationLimit
    # Detect duplicates and remove them.
    # (im not even sure why the vocab contain duplicate...)
    seen_vocabs = set()
    unique_scraper = []
    for item in Scraper:
        vocab = item.get('Vocab')
        if vocab and vocab not in seen_vocabs:
            unique_scraper.append(item)
            seen_vocabs.add(vocab)
    Scraper = unique_scraper
    total_items = len(Scraper)
    current_page = 0
    total_pages = (total_items + paginationLimit - 1) // paginationLimit

    # Set to store selected vocabulary
    selectedVocabulary = set()
    
    #  AUTOMATIC MODE: Select all items and skip UI. Much faster since code assumes EVERY VOCABULARY.
    if isAutomatic:
        selectedVocabulary = set(range(total_items))
    # INTERACTIVE MODE: Select items manually, does not skip UI. Much slower since you ARE deciding.
    else:
        while True:
            # Display current page items
            start_idx = current_page * paginationLimit
            end_idx = min(start_idx + paginationLimit, total_items)

            scrapedVocabularyTable = Table(
                caption=(f"Scraped Vocabulary\nPage {current_page + 1} of {total_pages}"
                         f"\nItems {start_idx + 1}-{end_idx} of {total_items}"
                         f"\nTime Taken: {scraperTimeElapsed}"),
                show_lines=True
            )
            scrapedVocabularyTable.add_column("Vocab", justify="center", style="cyan bold")
            scrapedVocabularyTable.add_column("Furigana", style="#00ffff i")
            scrapedVocabularyTable.add_column("Tag", justify="center", style="purple")
            scrapedVocabularyTable.add_column("Meaning", justify="center", style="#00ff00 bold")

            # List vocabulary
            for i in range(start_idx, end_idx):
                eVocab = Scraper[i]
                if i in selectedVocabulary:
                    scrapedVocabularyTable.add_row(
                        f"[blue]{i + 1}. {eVocab['Vocab']}[/]",
                        f"[blue]{eVocab['Furi']}[/]",
                        f"[blue]{eVocab['Tag']}[/]",
                        f"[blue]{c_(eVocab['Meaning'])}[/]"
                    )
                else:
                    scrapedVocabularyTable.add_row(
                        f"{i + 1}. {eVocab['Vocab']}",
                        f"{eVocab['Furi']}",
                        f"{eVocab['Tag']}",
                        f"{c_(eVocab['Meaning'])}"
                    )

            scrapedVocabularyConsole = Console()
            scrapedVocabularyConsole.print(scrapedVocabularyTable)
            scrapedVocabularyConsole.rule("[bold #00ff00]Separator")

            # Navigation
            Log("\nNavigation: < (previous) | > (next) | _ (finish selection)", "_")
            Log("To select a vocabulary item for batch processing, enter its number", "i")
            Log(f"""Target Kanji: {Kanji}
Onyomi: {kanji_scraped['Onyomi']}
Kunyomi: {kanji_scraped['Kunyomi']}
Meaning: {kanji_scraped['Meaning']}
Info: {kanji_scraped['Info']}
""", "_")

            command = input("Enter command or number: ").strip()
            # Back
            if command == "<":
                current_page = max(0, current_page - 1)
            # Next
            elif command == ">":
                current_page = min(total_pages - 1, current_page + 1)
            # Kanji Form
            elif command.lower() in ["k", "kanji"]:
                formatted_template = TemplateKanji.format(
                    KANJI=Kanji,
                    MEANING=kanji_scraped['Meaning'],
                    ONYOMI=" " + kanji_scraped['Onyomi'][3:],
                    KUNYOMI=" " + kanji_scraped['Kunyomi'][4:],
                    INFO=kanji_scraped['Info']
                )
                if VocabularyMethod == "m":
                    copier.copy(formatted_template)
                    Log("Recorded to clipboard", "s")
                else:
                    io.create_task(anki.NoteCreate({
                        "Kanji": Kanji,
                        "Keyword": kanji_scraped['Meaning'].replace(f"({Kanji})", ""),
                        "Story": formatted_template,
                    }, AnkiModelKanji))
                    Log("Recorded to Anki (AnkiConnect)", "s")
            # Exit 
            elif command == "_":
                break
            # Select All, and Exit.
            elif command == "." or command == "all":
                selectedVocabulary = set(range(total_items))
                break
            # Select vocab by index.
            elif command.isdigit():
                index = int(command) - 1
                if 0 <= index < total_items:
                    selectedVocabulary.add(index)
                    Log(f"Vocabulary {index + 1} selected for batch processing", "s")
                else:
                    Log("Invalid number. Enter a valid vocabulary number.", "c")
            # Non-command
            else:
                Log("Use <, >, _ to navigate or enter a number", "c")

    # AFTER SELECTION → Batch Processing
    if not selectedVocabulary:
        Log("No vocabulary selected. Exiting.", "c")
        return

    # Build a list of kanji (using the 'Vocab' from each selected item) separated by ###
    sorted_indices = sorted(selectedVocabulary)
    selected_kanji_list = [Scraper[i]['Vocab'] for i in sorted_indices]
    joined_kanji = "#".join(selected_kanji_list)

    # Construct the prompt for the API request
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
    "Vocabulary list: " + joined_kanji
    )
    
    # [Test Log]
    # Log(f"[#aaaaaa][LOG] {prompt_text}[/]", "_")
    # return
    
    c = Console()
    # Error Detection Pattern and Fix.
    with Live(console=c, screen=False) as LogL:
        while True:
            api_response = ResponseAI(joined_kanji, prompt=prompt_text)
            if "402" in str(api_response):
                retry = 0
                Log(f"[#f00][API ERROR] (0 Kuota). Rotating to next key...[/]")
                ai_key.rotate()
                retry += 1
                continue
            elif str(api_response).startswith("?!"):
                Log(f"[#f00][FATAL API ERROR]:\n{api_response}\n---[/]")
            # ERROR CHECKING. This error orginates from the model itself.
            VBX_OUTLIER = re.findall(r"===(.+)", api_response, flags=re.MULTILINE) # Checks if outlier gets in as well.
            VBX_OUTLIER_2 = re.findall(r"{(.+)", api_response, flags=re.MULTILINE) # Checks if outlier gets in as well.
            useless_label = r"<(?:Vocabulary\s*)+(.+?)>"
            VBX_USELESS_LABEL = re.findall(useless_label, api_response, flags=re.MULTILINE)
            LogL.update("Output checking...")
            if VBX_USELESS_LABEL or re.search(r"Vocabulary\s+.+?", api_response):
                api_response = re.sub(r"<(?:Vocabulary\s*)+(.+?)>", r"\1", api_response, flags=re.DOTALL) 
                api_response = re.sub(r"^(?:Vocabulary\s*)+(.+?)$", r"\1", api_response, flags=re.MULTILINE)
                LogL.update(api_response)
                Log(f"[#af0][MODEL CORRECTION]: Removing useless label.[/]")
            if VBX_OUTLIER or VBX_OUTLIER_2: 
                api_response = re.sub(r"===(.+)", "", api_response, flags=re.DOTALL) # Clean.
                api_response = re.sub(r" {(.+)", "", api_response, flags=re.DOTALL) # Clean. 
                LogL.update(api_response)
                Log(f"[#af0][MODEL CORRECTION]: Outlier.[/]")
            VBX_ALIGN = re.findall(r"^#\s*([^\n]+)", api_response, flags=re.MULTILINE) # Checks if each vocabulary in '#' aligned.
            VBX_EXPECTED = joined_kanji.split('#') # Vocabulary in given prompt
            if VBX_ALIGN == VBX_EXPECTED: 
                LogL.update(f"\n\n[#0f0] Error Fixed.[/]", refresh=True)
                break
            else:
                LogL.update(f"\n\n[#f00][FATAL ERROR]: Disaligned. (Expecting {VBX_EXPECTED} got {VBX_ALIGN} instead[/])")
    Log(api_response)
    Log(f"If there is something wrong with the AI response, quickly press <C-c> to disband and reset AI response, else ignore.\nProgram will continue in 3 seconds")
    time.sleep(5)
    # Parse the API response assuming explanations are separated by ###
    explanation_list = [piece.strip() for piece in api_response.split("#") if piece.strip()]
    
    # For each selected vocabulary, append the API explanation to its Meaning and send to Anki
    for idx, explanation in zip(sorted_indices, explanation_list):
        eVocab = Scraper[idx]
        htmlReadable = cvHTML(eVocab['Furi'])
        formatted_meaning = re.sub(r'(\d+\.)', r'<br>\1', eVocab['Meaning'])
        original_vocab = eVocab['Vocab']

        # Format 1: Re-format [Semantic] part to Red Color 
        explanation = re.sub(r'(\[Semantic\])\s+(.+)', r'<p style="color:red;text-shadow: #ff0000aa 0 0 25px">\1<br>\2</p>', explanation, flags=re.DOTALL)
        # Format 2: Re-format [Context] part to Purple Color
        explanation = re.sub(r'(\[Context\])\s+(.+)', r'<p style="color:#ff00ff;text-shadow: #ff00ffaa 0 0 25px">\1<br>\2</p>', explanation, flags=re.DOTALL)
        # Format 3: Re-format [Component] part to Lime Color 
        explanation = re.sub(r'(\[Component\])\s+(.+)', r'<p style="color:lime;text-shadow: #00ff00aa 0 0 25px">\1<br>\2</p>', explanation, flags=re.DOTALL)
        updated_meaning = formatted_meaning + "<br><br>" + explanation
        # Format: Replace @Kanji in Meaning, with XYZ
        # Censor original_vocab in updated_meaning with as many letters from 'XYZ...' as the vocab's length
        vocab_len = len(original_vocab)
        censor_letters = "XYZABCDEFGHIJKLMNOPQRSTUVW"[0:vocab_len]
        updated_meaning = re.sub(re.escape(original_vocab), censor_letters, updated_meaning)
        # --- find the last parenthetical group (if any) and check for v5 / v1 ---
        parens = re.findall(r'\(([^)]*)\)', formatted_meaning)
        last_par = parens[-1] if parens else ""
        colored_vocab = ""
        if re.search(r'v5', last_par, re.IGNORECASE):
            # color last char cyan
            if original_vocab:
                colored_vocab = original_vocab[:-1] + f'<span style="color:cyan">{original_vocab[-1]}</span>'
            else:
                colored_vocab = original_vocab
        elif re.search(r'v1', last_par, re.IGNORECASE):
            # color last char red
            if original_vocab:
                colored_vocab = original_vocab[:-1] + f'<span style="color:red">{original_vocab[-1]}</span>'
            else:
                colored_vocab = original_vocab
        else:
            colored_vocab = original_vocab
        formatted_template = Template.format(
        KANJI=Kanji,
        KANJI_ONYOMI=" " + kanji_scraped['Onyomi'][3:],
        KANJI_KUNYOMI=" " + kanji_scraped['Kunyomi'][4:],
        KANJI_MEANING=kanji_scraped['Meaning'],
        VOCAB=r"{{c1::" + colored_vocab + r"}}",
        MEANING=r"{{c2::" + updated_meaning + r"}}",
        FURIGANA=r"{{c1::" + htmlReadable + r"}}",
        TAG=eVocab['Tag'],
        STROKE=raw_svg
        )

        vbx_number = str(idx)

        if VocabularyMethod == "m":
            copier.copy(formatted_template)
            Log(f"VBX #{vbx_number} COPIED successfully (Confirmed)", "s")
        else:
            io.create_task(anki.NoteCreate({
                "Content": formatted_template,
            }, AnkiModelVocabulary))
            Log(f"VBX #{idx + 1} recorded", "s")

async def main():
    global BaseUrl, Kanji, raw_svg
    # a1 = Kanji, a2 = Total Pagination, a3 = Method
    if len(sys.argv) == 2:
        if sys.argv[1] == "-c" or sys.argv[1] == "--config":
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
                
                Log(config_table, "_")
                
                Log("\nOptions:", "_")
                Log("1. Edit value", "_")
                Log("2. Add new key-value (dev only)", "_") # Only Dev-Purpose
                Log("3. Remove key-value (dev only)", "_") # Only Dev-Purpose
                Log("4. Save & Exit", "_")
                Log("5. Exit", "_")

                choice = input("\nEnter choice (1-3): ").strip()

                if choice == "1":
                    key = input("Enter key to edit: ").strip()
                    if key in current_config:
                        current_value = current_config[key]
                        Log(f"Current value: {current_value}", "i")
                        
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
                        Log(f"Updated {key} to {new_value}", "s")
                    else:
                        Log("Key not found", "f")

                elif choice == "2":
                    key = input("Enter new key: ").strip()
                    if key not in current_config:
                        value = input("Enter value: ")
                        try:
                            # Try to evaluate as Python literal
                            value = eval(value)
                        except:
                            # If not a literal, keep as string
                            pass
                        current_config[key] = value
                        Log(f"Added {key}: {value}", "s")
                    else:
                        Log("Key already exists", "f")

                elif choice == "3":
                    key = input("Enter key to remove: ").strip()
                    if key in current_config:
                        del current_config[key]
                        Log(f"Removed {key}", "s")
                    else:
                        Log("Key not found", "f")

                elif choice == "4":
                    # Save to file
                    with open('config.json', 'w', encoding='utf-8') as f:
                        json.dump(current_config, f, indent=4, ensure_ascii=False)
                    Log("Configuration saved", "s")
                    break

                elif choice == "5":
                    Log("Exiting without saving", "w")
                    break

                else:
                    Log("Invalid choice", "f")
        if sys.argv[1] == "-h" or sys.argv[1] == "--help":
            Log("Command list:\n1. -c/--config | To modify config.json\n2. Kanji2Vocab.py [KANJI] [TOTAL_PAGINATION] [PAGE_SCRAPE_METHOD]\n | [KANJI] = Requires any Kanji\n | [TOTAL_PAGINATION] = Require an integer\n | [PAGE_SCRAPE_METHOD] = Either s or c, s = Sequential (one-by-one), c = Concurrent (all-together), default = s\n\nCredit:[#00ffff bold]3oFiz4[/] (Discord, Instagram)", "_")
        else:
            chars = sys.argv[1]

            for Kanji in chars:
                update_kanji(Kanji)
                BaseUrl = config['BaseUrl'].format(Kanji=Kanji)
                raw_svg = await kanjiStrokeScrape(Kanji)
                await run(Kanji, 20)
    elif len(sys.argv) == 3:
        Kanji = sys.argv[1]
        update_kanji(Kanji)
        Total = sys.argv[2]
        BaseUrl = config['BaseUrl'].format(Kanji=Kanji)
        raw_svg = await kanjiStrokeScrape(Kanji)
        await run(Kanji, int(Total))
    elif len(sys.argv) == 4:
        Kanji = sys.argv[1]
        update_kanji(Kanji)
        Total = sys.argv[2]
        Method = sys.argv[3]
        BaseUrl = config['BaseUrl'].format(Kanji=Kanji)
        raw_svg = await kanjiStrokeScrape(Kanji)
        await run(Kanji, int(Total), Method)
    else:
        Kanji = inputKanji()
        update_kanji(Kanji)
        BaseUrl = config['BaseUrl'].format(Kanji=Kanji)
        howmuch = int(input("Total page: ").strip())
        raw_svg = await kanjiStrokeScrape(Kanji)
        await run(Kanji, howmuch)
        

if __name__ == "__main__":
    io.run(main())
    
