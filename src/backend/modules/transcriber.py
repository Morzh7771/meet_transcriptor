import aiofiles
import tiktoken
from src.backend.core.baseFacade import BaseFacade
from src.backend.prompts.promptFacade import PromptFacade
from src.backend.models.llm_models import MatchSpeakersOtput

class Transcriber(BaseFacade):
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(Transcriber, cls).__new__(cls, *args, **kwargs)
        return cls._instance

    def __init__(self):
        super().__init__()
        self.enc = tiktoken.encoding_for_model("gpt-4o")
        self.CHUNK_SIZE = 10_000

    async def transcribe(self, webm_file: str, return_segments: bool = False, language: str = None) -> str:
        self.logger.info(f" Sending file {webm_file} to Whisper API...")

        async with aiofiles.open(webm_file, 'rb') as f:
            data = await f.read()
        try:
            response = await self.audio_completion(webm_file, data, return_segments, language)
            return response
        except Exception as e:
            self.logger.error(f"❌ Whisper error: {e}")
            return ""

    async def match_transcript_speakers(self, real_time_transcript, afterwards_transcript):
        output_transcript = []

        tokens_1 = self.enc.encode(real_time_transcript)
        tokens_2 = self.enc.encode(afterwards_transcript)

        len_tokens_1 = len(tokens_1)
        len_tokens_2 = len(tokens_2)
        # print(f"Length of t1: {len_tokens_1}, of t2: {len_tokens_2}")
        proportion = len_tokens_1 / len_tokens_2
        num_chunk = len_tokens_2 // self.CHUNK_SIZE + 1
        # print(f"Number of chunks is: {num_chunk}")

        proportion_chunk_size = int(self.CHUNK_SIZE * proportion)

        history = []

        end_2 = 0
        end_1 = 0

        for i in range(num_chunk):
            start_2 = max(0, end_2)
            start_1 = max(0, end_1 - 200)

            end_2 = min(len_tokens_2, (i + 1)*self.CHUNK_SIZE)
            end_1 = min(len_tokens_1, (i + 1)*proportion_chunk_size + 100)

            text1 = self.enc.decode(tokens_1[start_1:end_1])
            text2 = self.enc.decode(tokens_2[start_2:end_2])

            messages = eval(PromptFacade.get_prompt("match_speakers",
                                            real_time_transcript=text1,
                                            post_meeting_transcript=text2))

            if not history:
                history = messages
            else:
                history.append(messages[1])

            result = await self.completion("gpt-4o",
                                        messages=history,
                                        max_tokens=16000,
                                        output_model=MatchSpeakersOtput)

            output_transcript.extend(result.transcript)
            history.append({"role": "assistant", "content": str(result)})

        return output_transcript
