import uuid 
import os
from elevenlabs.play import play
from elevenlabs import VoiceSettings
from elevenlabs.client import ElevenLabs

class AudioInteractor:
        def __init__(self):
            self.__AUDIO_API_KEY__ = os.getenv("AUDIO_API_KEY")
            self.__audioified_phrase = None
            self.file_name = f"{uuid.uuid4()}.mp3"
            self.file_path = "./AUDIO/"
            self.model_id = os.getenv("AUDIO_MODEL")
            self.voice_id = "Xb7hH8MSUJpSbSDYk0k2"

        def play(self):
            if self.__audioified_phrase is None:
                return "No audioified phrase has been given."
            play(self.__audioified_phrase)

        def phrase_to_audio(self, phrase_modified, **kwargs):
            """
            Convert a text phrase into an audio file using ElevenLabs text-to-speech.

            Sends the provided text to the ElevenLabs TTS API and generates
            an MP3 audio file using a predefined voice and model. Additional keyword
            arguments can be found in this API References: https://elevenlabs.io/docs/api-reference/text-to-speech/convert?explorer=true

            Args:
                phrase_modified (str):
                    The text content to be converted into speech.
                    The given text SHOULD be ElevenLabs template.

                **kwargs:
                    Optional keyword arguments supported by
                    `client.text_to_speech.convert`, such as `language_code`,
                    `stability`, or `similarity_boost`.

            Raises:
                TypeError:
                    If any keyword argument does not match a valid parameter accepted
                    by the ElevenLabs `convert` method.

            Returns:
                None"""

            client = ElevenLabs(
                api_key=self.__AUDIO_API_KEY__
            )  # Initialize API_KEY on Client
            self.__audioified_phrase = client.text_to_speech.convert(
                voice_id=self.voice_id,  # Voice
                output_format="mp3_22050_32",
                text=phrase_modified,
                model_id=self.model_id,
                **kwargs,  # The rest of parameter (as long as they match with corresponding API args)
            )

            full_path = self.file_path + self.file_name

            with open(full_path, "wb") as audio_file:
                for (
                    chunk
                ) in self.__audioified_phrase:  # Check chunk in __audioified_phrase
                    if chunk:  # If chunk exist, we write it.
                        audio_file.write(chunk)  # Write chunk
            return {"path": full_path, "name": self.file_name} 
