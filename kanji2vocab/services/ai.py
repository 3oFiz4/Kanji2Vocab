# file: kanji2vocab/services/ai.py
import os
import asyncio
import openai

from .logger import Logger

"""
What you got API Error? That's because you forgot to initialize your API config in .env!

Let me show you:
1. Create .env
2. Copy and Paste this
```
AI_URL = "https://ermm.yesss"
AI_MODEL = "assistant"
API_KEY_1 = "lUCGJx-..."
API_KEY_2 = "sdk3S-..."
API_KEY_n = "thri@-..."
```
"""
class APIKeyRotator:
    """Cycles through a list of API keys stored in environment variables."""
    def __init__(self, key_prefixes: list[int], logger: Logger, key_format: str = "API_KEY_{}") -> None:
        # Store logger for warnings.
        self.logger = logger
        # Build a list of available keys.
        keys = [] # This is not where you put your keys.
        for prefix in key_prefixes:
            key_name = key_format.format(prefix)
            key_value = os.getenv(key_name)
            if key_value:
                keys.append(key_value)
            else:
                self.logger.log(f"Warning: Environment variable {key_name} not found.", "w")

        # Raise if no keys are available.
        if not keys:
            raise ValueError("No valid API keys were loaded.")

        # Store key list and index.
        self.keys = keys
        self.index = 0

    def rotate(self) -> str:
        """Rotate to the next key and return it."""
        # Move index in a circular fashion.
        self.index = (self.index + 1) % len(self.keys)
        return self.keys[self.index]

    def current(self) -> str:
        """Return the current active key."""
        # Return key at the current index.
        return self.keys[self.index]


class AIClient:
    """Handles AI chat requests with key rotation support."""
    def __init__(self, key_rotator: APIKeyRotator, base_url: str | None, model: str | None, logger: Logger) -> None:
        # Store dependencies and config.
        self.key_rotator = key_rotator
        self.base_url = base_url
        self.model = model or ""
        self.logger = logger

    def rotate_key(self) -> str:
        """Rotate API key and return the new key."""
        # Rotate and return.
        return self.key_rotator.rotate()

    async def request_chat(self, input_text: str, prompt: str = "") -> str | Exception:
        """Send a chat completion request to the AI model."""
        # Return early if input is empty.
        if input_text == "":
            return "No input given"

        # Build the final input with optional prompt.
        final_input = f"{prompt}\n---\n{input_text}" if prompt else input_text

        # Build the OpenAI client creation parameters.
        client_kwargs = {"api_key": self.key_rotator.current()}
        if self.base_url:
            client_kwargs["base_url"] = self.base_url

        # Execute the request in a background thread.
        def _call():
            client = openai.OpenAI(**client_kwargs)
            chat = client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": final_input}],
            )
            return chat.choices[0].message.content

        try:
            # Run the request in a thread to avoid blocking.
            return await asyncio.to_thread(_call)
        except Exception as e:
            # Return the exception object for upstream handling.
            return e