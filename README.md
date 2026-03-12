# Kanji2Vocab
This is a program I made to assist me with English-Japanese Vocabulary Generator via Anki Cards. 

This program really helps me a **lot**. And in fact, is the only repo that I use a lot among other repo you can find in my GitHub. 

This program are and have NOT served for others, since I never had the intent to. This code can be understood fully by me. Additionally, this repo present here as for my drive alternative. 

I might turn this into a open-source program when I have time.

## Code Diagram
<details>
  <summary>
    File Graph
  </summary>
  <img width="1335" height="560" alt="image" src="https://github.com/user-attachments/assets/572fd4f1-4e21-4516-b4a9-1f8506d461b3" />
</details>
<details>
  <summary>
    Architecture
  </summary>
  <img width="1881" height="702" alt="image" src="https://github.com/user-attachments/assets/95eff571-255c-4a8f-b192-e868050dff5d" />
</details>
<details>
  <summary>
    Architecture (LLM Generated):
  </summary>
The system is primarily a monolithic application structured into distinct layers:

- **Presentation Layer** (Console UI)
- **Application Logic Layer**** (Controller, Services)
- **Data Layer** (Models, Configurations)
- **External Integrations** (Web scraping, AI, Anki)

The core components communicate via dependency injection, with clear boundaries between data, logic, and I/O.
---
## 1. Major Containers and Their Responsibilities
### 1. **CLI and Entry Point**
- **`__main__.py`**: Initializes environment, dependencies, and orchestrates the startup.
- **`Kanji2Vocab.py`**: Entry point that runs the main async function.
- **`cli.py`**: Parses command-line arguments into structured actions (`CLIArgs`).
### 2. **Configuration Management**
- **`config.json`**: Persistent configuration storage.
- **`ConfigManager`**: Reads, writes, and updates configuration, maintaining unknown keys for flexibility.
- **`AppConfig`** (Data Model): Encapsulates configuration parameters, including user preferences and learned kanji.
### 3. **Core Application Controller**
- **`AppController`**: Central orchestrator that manages workflows:
  - Loads and applies configuration.
  - Coordinates data scraping, formatting, AI interactions, and UI.
  - Manages state updates (e.g., learned kanji).
  - Handles user commands and batch operations.
### 4. **Services Layer**
- **Web Scraping**
  - **`JishoScraper`**: Scrapes vocabulary and kanji metadata from Jisho.org.
  - **`StrokeScraper`**: Fetches SVG stroke diagrams for kanji.
- **Data Processing & Formatting**
  - **`Formatter`**: Converts raw HTML/JSON into formatted, colorized, and concise strings.
  - **`VocabFilter`**: Filters vocabulary based on learned characters.
- **External APIs & Integrations**
  - **`AIClient`**: Sends prompts to OpenAI API, manages API keys rotation.
  - **`AnkiClient`**: Interfaces with Anki via AnkiConnect API for note creation.
- **UI & Interaction**
  - **`ConsoleUI`**: Handles all console I/O, including prompts, menus, and paginated selection.
- **Utilities**
  - **`utils.py`**: Helper functions for environment loading, Unicode conversions, string normalization.
### 5. **External Dependencies & APIs**
- **OpenAI API**: For generating explanations, clues, or contextual data.
- **AnkiConnect API**: For creating and managing flashcards.
- **Jisho.org**: The primary source for vocabulary and kanji data.
- **SVG Stroke Diagrams**: For visual kanji stroke order.
---
## 2. Core Components and Their Internal Structure
### **`AppController`**
- Acts as the main orchestrator.
- Maintains application state (`config`, learned kanji).
- Applies configuration dynamically to dependent modules.
- Dispatches user commands to workflows (scraping, formatting, AI, Anki).
### **`ConfigManager`**
- Reads/writes `config.json`.
- Preserves unknown keys for forward compatibility.
- Supports updating learned kanji list.
### **`JishoScraper`**
- Builds URLs based on templates and kanji.
- Performs HTTP GET requests with randomized user agents.
- Parses HTML with BeautifulSoup.
- Extracts vocabulary, furigana, meanings, tags, and kanji metadata.
- Supports pagination and detects next page availability.
- Filters vocabulary based on learned characters and target kanji.
### **`StrokeScraper`**
- Fetches SVG stroke diagrams asynchronously.
- Modifies SVG styles for visual clarity.
- Uses Unicode codepoints for URL construction.
### **`Formatter`**
- Converts HTML snippets into plain text or rich markup.
- Shortens tags and meanings.
- Colorizes furigana based on kanji readings.
- Formats meanings with semantic, contextual, and component explanations.
- Cleans up AI responses for consistency.
### **`VocabFilter`**
- Filters vocabulary entries to include only those with learned characters.
- Ensures target kanji is present.
### **`AIClient`**
- Manages API key rotation.
- Sends chat prompts asynchronously.
- Handles quota errors and retries with different keys.
- Builds prompts based on vocab lists and formatting templates.
### **`AnkiClient`**
- Wraps AnkiConnect API.
- Creates notes with specified models and decks.
- Supports asynchronous note creation.
### **`ConsoleUI`**
- Provides interactive prompts for:
  - Kanji input.
  - Config editing.
  - Vocabulary selection with pagination.
- Uses `rich` for styled output.
- Supports navigation, multi-selection, and detailed info display.
### **`PaginationHandler`**
- Supports sequential and concurrent scraping of multiple pages.
- Uses `rich.Live` for real-time progress.
- Implements retries and cancellation for robustness.
- Merges results into a unified list.
---
## 3. External Dependencies and External Systems
- **Web scraping** relies on `requests` and `BeautifulSoup`.
- **SVG fetching** uses `aiohttp` for asynchronous requests.
- **AI interactions** via `openai` SDK, with key rotation.
- **Anki** via `requests` to local `AnkiConnect`.
- **Configuration** via JSON files, with environment variables for API keys.
- **Console output** managed through `rich`, enabling styled, dynamic, and paginated displays.
---
## 4. Data Flow and Control Flow
### Initialization
- Environment variables loaded (`load_env()`).
- Configuration loaded (`ConfigManager`).
- Dependencies instantiated (`Formatter`, `Logger`, `UI`, `Scraper`, `AIClient`, `AnkiClient`).
- `AppController` initialized with dependencies and initial config.
### User Interaction
- CLI args parsed (`parse_cli()`).
- Based on command, `AppController.dispatch()` triggers workflows:
  - **Scraping**: Fetch pages sequentially or concurrently, filter, format, and display vocab.
  - **AI**: Generate explanations or clues, clean responses.
  - **Anki**: Create flashcards.
  - **Config**: Edit settings interactively.
  - **Selection**: Paginate vocab, select items, and process in batch.
### Data Processing
- Scraped data is filtered (`VocabFilter`), formatted (`Formatter`), and stored.
- User selections are managed via paginated tables.
- AI prompts are generated from vocab lists, responses cleaned, and validated.
- New vocab or kanji info can be added to learned set and persisted.
### External Communication
- HTTP requests for scraping and SVG fetching.
- Asynchronous API calls for AI and Anki.
- API key rotation ensures continuous operation despite quota limits.
---
## 5. Missing or Uncertain Details
- The exact internal logic of some modules (e.g., detailed AI prompt construction, specific formatting rules) is inferred from code snippets but not exhaustively detailed.
- The precise structure of the `config.json` is known, but the runtime defaults or user modifications are not fully specified.
- The full extent of the user interaction flow (e.g., error handling, retries) is complex but follows standard patterns.
---
## 6. Summary of Architectural Patterns
- **Layered Architecture**: Clear separation between data models, services, and controllers.
- **Dependency Injection**: Components are passed dependencies explicitly, facilitating testing and modularity.
- **Modular Micro-Containers**: Each container (UI, scraper, formatter, API clients) encapsulates specific responsibilities.
- **Asynchronous and Concurrent Processing**: Heavy I/O operations (scraping, API calls) are async or threaded for efficiency.
- **Extensibility**: Preserved unknown config keys, pluggable components, and flexible API integrations.
</details>

## Code Template
**This is important! Or else you'll get a bug where the code repeatedly trying to rotate API keys! Because there's null! So no point of trying**
```.env
AI_URL = "openai end point url"
AI_MODEL = "gpt-4.1-nano"
API_KEY_0 = "q72....Zg"
API_KEY_1 = "jFn....Jw"
```

<details>
  <summary>
    Recommendation regarding AI Model:
  </summary>
  Since the prompt being used is lengthy. It is recomemnded to use LLM Model with high IF (Instruction Following) score. Therefore, you are unlikely to see the program repeating by itself trying to align the prompt position. Avoid using gpt-4.1-nano. Use something likw gpt-5-mini-high, gpt-5.3-instant, or gpt-5-nano-high
</details>

## Requirement
```
requests pyperclip beautifulsoup4 rich openai aiohttp dotenv 
```

## Changelog
- [x] <RECENT> The whole program is revamped into OOP version for clear structure (unfinished, but can be used otherwise.)
- [x] Add a Tag for each Vocabulary in Pagination (e.g. N5, N4, N3, WN29, WN29-20, CMN)
- [x] Add a Shortener for the formatted meaning (e.g. Suru verb => (suru), Na-Adjective => (な), Adverb => (ADV))
- [x] Improve Scrapper (optional) = Modified to use LXML, scrape Kanji also, i guess thats an improvement XD
- [x] Add an API integration with an AI Chatbot to automatically creates a Spoiler, and contextual usage of a vocabulary (optional)
- [x] Add stroke drawing (optional)
- [x] Add colored for some tags and info
- [x] Add example sentence
- [x] Add a CMD GUI (ex. below)
- [x] Add a system when a certain meaning has an example.
- [x] Improve Pagination system so instead of `NTH. [VOCAB] ([FURIGANA])\n=>[MEANING]` it has a table generated (Clue: Use Rich).
- [x] Show more logs, such as (total vocabs scraped per page)
```
Kanji2Vocab
1. Search Vocab (type. 1[KANJI], ex: 1何)
2. Modify configuration
3. Credit 
4. Exit
```

**To-Dos:**
- [ ] <RECENT> Make more elaborating comment and structure diagram to explain OOP structure.
- [ ] Make code more readable and less messy :) (already messy btw, so whats the point?)
- [ ] Add spelling sound
- [ ] Add pitch accent marker
- [ ] Improve example
- [ ] Add a search system in Pagination, that able to search meaning, furigana, kanji, or even tags
- [ ] Add a filter system that filters the tag
- [ ] Add a Hiragana-Katakana converter if a certain Vocabulary are confirmed as by their Onyomi
- [ ] Add an extended configuration, editable Template, editable hasLearned


