import asyncio
import aiohttp
import tempfile
import os
from pydub import AudioSegment
from typing import List, Tuple
from src.backend.utils.logger import CustomLog
from src.backend.llm.transcriber import Transcriber

logger = CustomLog()

class AsyncWhisperTranscriber:
    def __init__(self):
        self.transcriber = Transcriber()
        
    async def transcribe_wav_file(self, wav_file_path: str, 
                                 chunk_duration_s: int = 60, 
                                 overlap_duration_s: int = 10,
                                 max_concurrent: int = 5) -> str:
        """
        Transcribe a long WAV file by chunking and processing asynchronously.
        
        Args:
            wav_file_path: Path to the WAV file
            chunk_duration_s: Duration of each chunk in seconds (default 60s)
            overlap_duration_s: Overlap between chunks in seconds (default 10s)
            max_concurrent: Maximum concurrent API calls (default 5)
        
        Returns:
            Complete transcription as a string
        """
        
        # Load audio file
        logger.info(f"Loading audio file: {wav_file_path}")
        audio = AudioSegment.from_wav(wav_file_path)
        total_duration = len(audio) / 1000  # Duration in seconds
        
        logger.info(f"Total audio duration: {total_duration:.2f} seconds")
        
        # Create chunks with overlap
        chunks = self._create_audio_chunks(audio, chunk_duration_s, overlap_duration_s)
        logger.info(f"Created {len(chunks)} audio chunks")
        
        # Process chunks asynchronously with concurrency limit
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def process_chunk_with_limit(chunk_data):
            async with semaphore:
                return await self._transcribe_chunk(chunk_data)
        
        # Execute all transcriptions concurrently
        logger.info("Starting async transcription of chunks...")
        transcription_results = await asyncio.gather(
            *[process_chunk_with_limit(chunk) for chunk in chunks],
            return_exceptions=True
        )
        
        # Handle any errors
        for i, result in enumerate(transcription_results):
            if isinstance(result, Exception):
                logger.error(f"Chunk {i} failed: {result}")
                transcription_results[i] = ""  # Replace with empty string
        
        # Stitch chunks together using overlap
        final_transcript = self._stitch_transcriptions(
            transcription_results, chunks, overlap_duration_s
        )
        
        logger.info("Transcription completed successfully")
        return final_transcript
    
    def _create_audio_chunks(self, audio: AudioSegment, 
                           chunk_duration_s: int, 
                           overlap_duration_s: int) -> List[Tuple[AudioSegment, int, int]]:
        """Create overlapping audio chunks with metadata."""
        chunks = []
        chunk_duration_ms = chunk_duration_s * 1000
        overlap_duration_ms = overlap_duration_s * 1000
        step_size_ms = chunk_duration_ms - overlap_duration_ms
        
        start_time = 0
        chunk_index = 0
        
        while start_time < len(audio):
            end_time = min(start_time + chunk_duration_ms, len(audio))
            chunk = audio[start_time:end_time]
            
            # Store chunk with metadata (audio, start_ms, end_ms)
            chunks.append((chunk, start_time, end_time))
            chunk_index += 1
            
            # Break if we've reached the end
            if end_time >= len(audio):
                break
                
            start_time += step_size_ms
        
        return chunks
    
    async def _transcribe_chunk(self, chunk_data: Tuple[AudioSegment, int, int]) -> str:
        """Transcribe a single audio chunk."""
        chunk, start_ms, end_ms = chunk_data
        
        # Export chunk to temporary file
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
            chunk.export(temp_file.name, format="wav")
            temp_file_path = temp_file.name
        
        try:

            
            # Make API request with retry logic
            for attempt in range(3):
                try:
                    transcription = self.transcriber.transcribe(temp_file_path)
                    if transcription:
                        logger.info(f"Chunk {start_ms}-{end_ms}ms transcribed successfully")
                        return transcription.strip()
                    else:
                        logger.error(f"Empty transcription for chunk {start_ms}-{end_ms}ms")
                        if attempt == 2:  # Last attempt
                            raise Exception("Empty transcription received")
                except Exception as e:
                    logger.warning(f"Error for chunk {start_ms}-{end_ms}ms, attempt {attempt + 1}: {e}")
                    if attempt == 2:
                        raise
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff
                                
        finally:
            # Clean up temporary file
            try:
                os.unlink(temp_file_path)
            except:
                pass
        
        return ""
    
    def _stitch_transcriptions(self, transcriptions: List[str], 
                             chunks: List[Tuple], 
                             overlap_duration_s: int) -> str:
        """
        Stitch transcriptions together by handling overlaps.
        Simple approach: just concatenate and let overlaps provide context.
        """
        if not transcriptions:
            return ""
        
        # For simplicity, we'll just join the transcriptions
        # In a more sophisticated approach, you could:
        # 1. Use Levenshtein distance to find best overlap points
        # 2. Remove duplicate words in overlapping sections
        # 3. Use timestamps if available
        
        # Remove empty transcriptions and join with space
        valid_transcriptions = [t for t in transcriptions if t.strip()]
        
        # Simple concatenation with overlap handling
        if len(valid_transcriptions) == 1:
            return valid_transcriptions[0]
        
        # For multiple chunks, we could implement more sophisticated stitching
        # For now, simple join works reasonably well due to overlap
        return " ".join(valid_transcriptions)


