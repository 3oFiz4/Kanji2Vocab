# file: kanji2vocab/services/anki.py
import asyncio
import requests
import os
import base64
from .logger import Logger


class AnkiInteractor:
    """Low-level AnkiConnect interactor."""
    def __init__(self, url: str = "http://localhost:8765", logger: Logger | None = None) -> None:
        # Store URL and create a session for reuse.
        self.url = url
        self.session = requests.Session()
        # Store logger for error reporting.
        self.logger = logger
        # self.error_handler = ErrorHandler(logger) # TODO: Refer to error/anki and test out all possible error and give all possible soltuins.
    
    async def invoke(self, action: str, **params):
        """Send an action to AnkiConnect asynchronously."""
        # Build the payload for AnkiConnect.
        payload = {
            "action": action,
            "version": 6,
            "params": params,
        }

        # Perform the HTTP request in a background thread.
        def _post():
            response = self.session.post(self.url, json=payload)
            if response.status_code != 200:
                raise Exception(f"Anki::HTTP [ERR]: {response.status_code} when {response.text}")
            data = response.json()
            if "error" in data and data["error"] is not None:
                raise Exception(f"Anki::Interactor [ERR]: {data['error']}")
            return data["result"]

        return await asyncio.to_thread(_post)


class AnkiClient:
    """High-level Anki note creation helper."""
    def __init__(self, interactor: AnkiInteractor, deck_name: str, logger: Logger) -> None:
        # Store dependencies and deck name.
        self.interactor = interactor
        self.deck_name = deck_name
        self.logger = logger

    def update_deck(self, deck_name: str) -> None:
        """Update the target deck name."""
        # Assign new deck name.
        self.deck_name = deck_name

    async def add_note(self, fields: dict, model: str, audio_path=None, audio_field=None, tags: list[str] | None = None) -> bool:
        """Create a note in Anki using AnkiConnect."""
        # Validate fields presence.
        if not fields:
            raise ValueError("Should at least contain one field.")

        # Original Code from: kanji2Immersion/request.py:
        # ---- AUDIO HANDLING ----
        if audio_path:
            if not os.path.isfile(audio_path):
                raise FileNotFoundError(f"Invalid audio file: {audio_path}")

            filename = os.path.basename(audio_path)

            with open(audio_path, "rb") as f:
                audio_base64 = base64.b64encode(f.read()).decode("utf-8")

            media_result = await self.anki_connect.invoke(
                "storeMediaFile",
                filename=filename,
                data=audio_base64,
            )

            print("MEDIA RESULT:", media_result)

            fields[audio_field] = f"[sound:{filename}]"

        # Build note payload.
        note = {
            "deckName": self.deck_name,
            "modelName": model,
            "fields": fields,
            "tags": tags or ["Kanji2VocabCreation"],
            "options": {"allowDuplicate": False},
        }

        try:
            # Invoke AnkiConnect addNote.
            result = await self.interactor.invoke("addNote", note=note)
            # Return True if result exists.
            return result is not None
        except Exception as e:
            # Log error and return False.
            self.logger.log(f"An error occurred: {str(e)}", "f")
            return False