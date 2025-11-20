# Kanji2Vocab
This is a program I made to assist me with English-Japanese Vocabulary Generator via Anki Cards. 

This program really helps me a **lot**. And in fact, is the only repo that I use a lot among other repo you can find in my GitHub. 

This program are and have NOT served for others, since I never had the intent to. This code can be understood fully by me. Additionally, this repo present here as for my drive alternative. 

I might turn this into a open-source program when I have time.

## Code Template

```.env
AI_URL = "openai end point url"
AI_MODEL = "gpt-4.1-nano"
API_KEY_0 = "q72....Zg"
API_KEY_1 = "jFn....Jw"
```

## Requirement
```
requests, pyperclip, beautifulsoup4, rich, openai, aiohttp, dotenv 
```

## To-Do
To-Do:
-[x] Add a Tag for each Vocabulary in Pagination (e.g. N5, N4, N3, WN29, WN29-20, CMN)
-[x] Add a Shortener for the formatted meaning (e.g. Suru verb => (suru), Na-Adjective => (な), Adverb => (ADV))
-[ ] Add a search system in Pagination, that able to search meaning, furigana, kanji, or even tags
-[ ] Add a filter system that filters the tag
-[ ] Add a Hiragana-Katakana converter if a certain Vocabulary are confirmed as by their Onyomi
-[ ] Add an extended configuration, editable Template, editable hasLearned
-[x] Add a CMD GUI (ex. below)
```
Kanji2Vocab
1. Search Vocab (type. 1[KANJI], ex: 1何)
2. Modify configuration
3. Credit 
4. Exit
```

-[x] Add a system when a certain meaning has an example.
-[x] Improve Pagination system so instead of `NTH. [VOCAB] ([FURIGANA])\n=>[MEANING]` it has a table generated (Clue: Use Rich).
-[x] Show more logs, such as (total vocabs scraped per page)
-[ ] Make code more readable and less messy :) (already messy btw, so whats the point?)
-[x] Improve Scrapper (optional) = Modified to use LXML, scrape Kanji also, i guess thats an improvement XD
-[x] Add an API integration with an AI Chatbot to automatically creates a Spoiler, and contextual usage of a vocabulary (optional)
-[x] Add stroke drawing (optional)
-[x] Add colored for some tags and info
-[x] Add example sentence
-[ ] Add spelling sound
-[ ] Add pitch accent marker
-[ ] Improve example

Additional Idea:
Accomodate Kanji(forgot the name ;-; ) which accomodate more examples, and kanji info.


