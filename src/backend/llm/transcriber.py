# from openai import OpenAI
# from openai import AsyncOpenAI
# from dotenv import load_dotenv
# import aiofiles
# import os
# from src.backend.utils.logger import CustomLog
# import tiktoken
# from typing import List

# log = CustomLog()

# # Load keys from .env
# load_dotenv()

# class Transcriber:
#     def __init__(self):
#         api_key = os.getenv("OPENAI_API_KEY")
#         if not api_key:
#             raise ValueError("OPENAI_API_KEY is missing in .env")
#         self.client = OpenAI(api_key=api_key)

#     async def transcribe(self, webm_file: str, return_segments: bool = False, language: str = "en") -> str:
#         log.info(f" Sending file {webm_file} to Whisper API...")
#         client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

#         async with aiofiles.open(webm_file, 'rb') as f:
#             data = await f.read()
#         try:
#             response = await client.audio.transcriptions.create(
#                 model="whisper-1",
#                 file=(webm_file, data),
#                 response_format="verbose_json" if return_segments else "text",
#                 language=language
#             )
#             if return_segments:
#                 return {
#                     "text": response.text,
#                     "segments": [
#                         {
#                             "start": s.start,
#                             "end": s.end,
#                             "text": s.text
#                         } for s in response.segments
#                     ]
#                 }
#             return response
#         except Exception as e:
#             log.error(f"❌ Whisper error: {e}")
#             return ""

#     def __split_transcript_tokenwise(self, transcript: str,
#                                    model_name: str = "gpt-4o",
#                                    chunk_token_limit: int = 3000,
#                                    overlap_tokens: int = 300) -> List[str]:

#         encoding = tiktoken.encoding_for_model(model_name)
#         tokens = encoding.encode(transcript)
        
#         chunks = []
#         start = 0
#         while start < len(tokens):
#             end = min(start + chunk_token_limit, len(tokens))
#             chunk_tokens = tokens[start:end]
#             chunk_text = encoding.decode(chunk_tokens)
#             chunks.append(chunk_text)
#             start += chunk_token_limit - overlap_tokens
#         return chunks

    
#     async def match_transcript_speakers(self, real_time_transcript, afterwards_transcript):
#         transcript = ""
        
#         return transcript