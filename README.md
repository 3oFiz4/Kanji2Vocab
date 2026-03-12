# Kanji2Vocab
This is a program I made to assist me with English-Japanese Vocabulary Generator via Anki Cards. 

This program really helps me a **lot**. And in fact, is the only repo that I use a lot among other repo you can find in my GitHub. 

This program are and have NOT served for others, since I never had the intent to. This code can be understood fully by me. Additionally, this repo present here as for my drive alternative. 

I might turn this into a open-source program when I have time.

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


