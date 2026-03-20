from typing import Type
from .anki import translate_anki_error
def deferErrorTo(error_type: Type[Exception]):
    def decorator(method):
        async def wrapper(self, *args, **kwargs):
            try:
                return await method(self, *args, **kwargs)

            except error_type as e:
                self.error_handler.handle(e)
                return None

            except Exception as e:
                # Defer translation OUTSIDE
                translated = translate_anki_error(e)
                self.error_handler.handle(translated)
                return None

        return wrapper
    return decorator