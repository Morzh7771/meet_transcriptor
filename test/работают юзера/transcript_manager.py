import os
import subprocess
from glob import glob
import json
import time
from pydub import AudioSegment
import tempfile
import math
from src.backend.modules.transcriber import Transcriber
from src.backend.core.baseFacade import BaseFacade
from src.backend.db.dbFacade import DBFacade
from src.backend.models.db_models import MeetUpdate
from src.backend.modules.meetingAnalizer import MeetingAnalizer

class TranscriptManager(BaseFacade):
    def __init__(self):
        super().__init__()
        self.transcriber = Transcriber()
        self.db = DBFacade()
        self.paths = None
        self.full_transcript_buffer = None
        self.MAX_CHUNK_DURATION_SEC = 290
        self.CHUNK_EXTENSION = ".webm"
        self.meeting_analizer = MeetingAnalizer()
        self.audio_start_time = None

    def set_paths(self, paths):
        self.paths = paths

    def reset_transcript_buffer(self):
        self.full_transcript_buffer = []

    def get_transcript(self):
        return "\n".join(self.full_transcript_buffer)

    def merge_speaker_ranges(self, speaker_ranges):
        """Merge consecutive ranges from the same speaker with enhanced logic"""
        if not speaker_ranges:
            return []

        merged_ranges = []
        current_range = None

        # Sort by start time
        sorted_ranges = sorted(speaker_ranges, key=lambda x: x["start_ms"])
        
        for range_item in sorted_ranges:
            if current_range is None:
                current_range = range_item.copy()
            elif (current_range["speaker"] == range_item["speaker"] and 
                  abs(current_range["end_ms"] - range_item["start_ms"]) <= 2000):  # Increased tolerance to 2 seconds
                # Merge ranges from same speaker if they're close
                current_range["end_ms"] = max(current_range["end_ms"], range_item["end_ms"])
                self.logger.info(f"Merged ranges for '{current_range['speaker']}': extended to {current_range['end_ms']}")
            else:
                # Save current range and start new one
                merged_ranges.append(current_range)
                current_range = range_item.copy()

        if current_range:
            merged_ranges.append(current_range)

        self.logger.info(f"Merged {len(speaker_ranges)} ranges into {len(merged_ranges)} consolidated ranges")
        return merged_ranges

    def get_speaker_ranges(self, speaker_events):
        """
        Convert speaker events to time ranges with improved processing
        Handle the boolean-based speaker states from extension
        """
        speaker_ranges = []
        if not speaker_events:
            self.logger.warning("No speaker events provided for range generation")
            return speaker_ranges

        self.logger.info(f"Processing {len(speaker_events)} speaker events for range generation")

        # Track when each speaker starts/stops speaking
        speaker_sessions = {}  # {speaker_name: {"start": time, "active": bool}}

        for i, event in enumerate(speaker_events):
            # Handle different event formats
            if isinstance(event, dict) and "events" in event:
                # Handle wrapped format from save_buffer
                events_list = event["events"]
                self.logger.info(f"Processing wrapped event with {len(events_list)} sub-events")
            else:
                events_list = [event] if isinstance(event, dict) else []

            for event_item in events_list:
                timestamp = event_item.get("time_raw")
                speakers_dict = event_item.get("speakers", {})

                if timestamp is None or not isinstance(speakers_dict, dict):
                    self.logger.info(f"Skipping invalid event item: timestamp={timestamp}, speakers={type(speakers_dict)}")
                    continue

                # Process each speaker's state
                for speaker_name, is_speaking in speakers_dict.items():
                    if not speaker_name or not speaker_name.strip():
                        continue

                    speaker_name = speaker_name.strip()

                    # Initialize speaker session if not exists
                    if speaker_name not in speaker_sessions:
                        speaker_sessions[speaker_name] = {"start": None, "active": False}

                    prev_active = speaker_sessions[speaker_name]["active"]

                    # Speaker started speaking
                    if is_speaking and not prev_active:
                        speaker_sessions[speaker_name]["start"] = timestamp
                        speaker_sessions[speaker_name]["active"] = True
                        self.logger.info(f"Speaker '{speaker_name}' started speaking at {timestamp}")

                    # Speaker stopped speaking
                    elif not is_speaking and prev_active:
                        start_time = speaker_sessions[speaker_name]["start"]
                        if start_time is not None:
                            duration = timestamp - start_time
                            speaker_ranges.append({
                                "speaker": speaker_name,
                                "start_ms": start_time,
                                "end_ms": timestamp,
                                "duration_ms": duration
                            })
                            self.logger.info(f"Speaker '{speaker_name}' spoke from {start_time} to {timestamp} (duration: {duration}ms)")
                        
                        speaker_sessions[speaker_name]["active"] = False
                        speaker_sessions[speaker_name]["start"] = None

        # Handle speakers still speaking at the end
        last_timestamp = None
        if speaker_events:
            # Find the last valid timestamp
            for event in reversed(speaker_events):
                events_list = event.get("events", [event]) if isinstance(event, dict) else [event]
                for event_item in reversed(events_list):
                    if event_item.get("time_raw"):
                        last_timestamp = event_item["time_raw"]
                        break
                if last_timestamp:
                    break

        if last_timestamp:
            for speaker_name, session in speaker_sessions.items():
                if session["active"] and session["start"] is not None:
                    duration = last_timestamp - session["start"]
                    speaker_ranges.append({
                        "speaker": speaker_name,
                        "start_ms": session["start"],
                        "end_ms": last_timestamp,
                        "duration_ms": duration
                    })
                    self.logger.info(f"Speaker '{speaker_name}' final range: {session['start']} to {last_timestamp} (duration: {duration}ms)")

        # Merge consecutive ranges and return
        merged_ranges = self.merge_speaker_ranges(speaker_ranges)
        
        # Log summary
        for range_item in merged_ranges[:5]:  # Log first 5 ranges
            self.logger.info(f"Range: '{range_item['speaker']}' from {range_item['start_ms']} to {range_item['end_ms']}")
        
        if len(merged_ranges) > 5:
            self.logger.info(f"... and {len(merged_ranges) - 5} more ranges")
        
        return merged_ranges

    def find_active_speaker(self, seg_start, seg_end, speaker_ranges):
        """Find the speaker most active during a transcript segment with improved accuracy"""
        TOLERANCE_MS = 500  # Increased tolerance for better matching
        best_speaker = "Unknown"
        best_overlap = 0
        best_percentage = 0

        segment_duration = seg_end - seg_start
        self.logger.info(f"Finding speaker for segment {seg_start}-{seg_end} (duration: {segment_duration}ms)")

        for range_item in speaker_ranges:
            if range_item["start_ms"] is None or range_item["end_ms"] is None:
                continue
                
            # Add tolerance to speaker ranges for better matching
            range_start = range_item["start_ms"] - TOLERANCE_MS
            range_end = range_item["end_ms"] + TOLERANCE_MS

            # Calculate overlap
            overlap_start = max(seg_start, range_start)
            overlap_end = min(seg_end, range_end)
            overlap = max(0, overlap_end - overlap_start)
            
            # Calculate overlap percentage
            overlap_percentage = (overlap / segment_duration * 100) if segment_duration > 0 else 0
            
            self.logger.info(f"Speaker '{range_item['speaker']}': overlap={overlap}ms ({overlap_percentage:.1f}%)")
            
            # Prefer higher overlap, but also consider percentage
            if overlap > best_overlap or (overlap == best_overlap and overlap_percentage > best_percentage):
                best_overlap = overlap
                best_percentage = overlap_percentage
                best_speaker = range_item["speaker"]

        if best_overlap > 0:
            self.logger.info(f"Selected speaker: '{best_speaker}' (overlap: {best_overlap}ms, {best_percentage:.1f}%)")
        else:
            self.logger.info(f"No speaker found for segment, using: '{best_speaker}'")
            
        return best_speaker

    async def transcribe_chunk(self, webm_path, timestamp, chunk_start_time, language):
        """Transcribe a single chunk with enhanced speaker attribution"""
        self.logger.info(f"Starting transcription of chunk: {webm_path}")
        
        try:
            # Set audio start time if not set
            if not self.audio_start_time:
                self.audio_start_time = chunk_start_time
                self.logger.info(f"Set audio start time: {self.audio_start_time}")
            elif chunk_start_time - self.audio_start_time > 50_000:
                self.logger.warning(f"Large time gap detected: chunk={chunk_start_time}, start={self.audio_start_time}")
                self.audio_start_time = chunk_start_time

            # Validate webm file
            if not os.path.exists(webm_path):
                self.logger.error(f"Webm file not found: {webm_path}")
                return
                
            file_size = os.path.getsize(webm_path)
            if file_size < 1024:
                self.logger.warning(f"Webm file very small ({file_size} bytes), may be silent: {webm_path}")

            # Get transcription from Whisper
            self.logger.info("Sending to Whisper for transcription...")
            result = await self.transcriber.transcribe(webm_path, return_segments=True, language=language)
            
            if not result:
                self.logger.warning("Whisper returned empty result")
                return

            # Load speaker events for this chunk
            speaker_meta_path = os.path.join(self.paths["transcripts"], f"chunk_{timestamp}_speakers.json")
            
            if not os.path.exists(speaker_meta_path):
                self.logger.warning(f"No speaker metadata found: {speaker_meta_path}")
                # Try to transcribe without speaker attribution
                await self._transcribe_without_speakers(result, chunk_start_time)
                return
            
            with open(speaker_meta_path, "r", encoding="utf-8") as f:
                speaker_data = json.load(f)
            
            # Extract events (handle both old and new format)
            if isinstance(speaker_data, dict) and "events" in speaker_data:
                speaker_events = speaker_data["events"]
                self.logger.info(f"Loaded speaker data with {len(speaker_events)} events from chunk metadata")
            else:
                speaker_events = speaker_data if isinstance(speaker_data, list) else []
                self.logger.info(f"Loaded {len(speaker_events)} speaker events (legacy format)")

            # Convert speaker events to ranges
            speaker_ranges = self.get_speaker_ranges(speaker_events)
            
            if not speaker_ranges:
                self.logger.warning("No speaker ranges generated for this chunk")
                await self._transcribe_without_speakers(result, chunk_start_time)
                return

            # Parse Whisper result
            if isinstance(result, str):
                try:
                    result = json.loads(result)
                except json.JSONDecodeError:
                    self.logger.error("Could not parse Whisper response as JSON")
                    return
            
            if not isinstance(result, dict) or "segments" not in result:
                self.logger.error("Invalid Whisper result format")
                return

            # Process segments with speaker attribution
            text_lines = []
            seg_starting_point = int((chunk_start_time - self.audio_start_time) // 1000)

            self.logger.info(f"Processing {len(result['segments'])} transcript segments")

            for seg_idx, seg in enumerate(result["segments"]):
                # Calculate absolute timestamps (for speaker matching)
                seg_abs_start = chunk_start_time + seg["start"] * 1000
                seg_abs_end = chunk_start_time + seg["end"] * 1000
                
                # Calculate relative timestamps (for display)
                seg_rel_start = seg_starting_point + seg["start"]
                seg_rel_end = seg_starting_point + seg["end"]
                
                # Find active speaker for this segment
                speaker = self.find_active_speaker(seg_abs_start, seg_abs_end, speaker_ranges)
                
                # Only add non-empty text
                text_content = seg["text"].strip()
                if speaker and text_content:
                    # Format timestamp
                    start_h = int(seg_rel_start // 3600)
                    start_m = int((seg_rel_start % 3600) // 60)
                    start_s = int(seg_rel_start % 60)

                    end_h = int(seg_rel_end // 3600)
                    end_m = int((seg_rel_end % 3600) // 60)
                    end_s = int(seg_rel_end % 60)
                    
                    formatted_line = f"({start_h:02d}:{start_m:02d}:{start_s:02d}-{end_h:02d}:{end_m:02d}:{end_s:02d}) {speaker}: {text_content}"
                    text_lines.append(formatted_line)
                    
                    self.logger.info(f"Segment {seg_idx}: '{speaker}' at {seg_rel_start:.1f}s said: {text_content[:50]}...")

            if text_lines:
                # Add to buffer
                self.full_transcript_buffer.extend(text_lines)
                self.logger.info(f"Added {len(text_lines)} transcript lines to buffer")
                
                # Log sample for verification
                sample_lines = text_lines[:3]
                for line in sample_lines:
                    self.logger.info(f"Sample: {line}")
                    
            else:
                self.logger.warning("No transcript lines generated for this chunk")

        except Exception as e:
            self.logger.error(f"Transcription error: {e}")
            import traceback
            self.logger.error(f"Traceback: {traceback.format_exc()}")

    async def _transcribe_without_speakers(self, result, chunk_start_time):
        """Fallback transcription without speaker attribution"""
        self.logger.info("Performing transcription without speaker attribution")
        
        if isinstance(result, str):
            try:
                result = json.loads(result)
            except json.JSONDecodeError:
                return
        
        if not isinstance(result, dict) or "segments" not in result:
            return

        text_lines = []
        seg_starting_point = int((chunk_start_time - self.audio_start_time) // 1000) if self.audio_start_time else 0

        for seg in result["segments"]:
            text_content = seg["text"].strip()
            if text_content:
                seg_rel_start = seg_starting_point + seg["start"]
                seg_rel_end = seg_starting_point + seg["end"]
                
                start_h = int(seg_rel_start // 3600)
                start_m = int((seg_rel_start % 3600) // 60)
                start_s = int(seg_rel_start % 60)

                end_h = int(seg_rel_end // 3600)
                end_m = int((seg_rel_end % 3600) // 60)
                end_s = int(seg_rel_end % 60)
                
                formatted_line = f"({start_h:02d}:{start_m:02d}:{start_s:02d}-{end_h:02d}:{end_m:02d}:{end_s:02d}) Unknown Speaker: {text_content}"
                text_lines.append(formatted_line)

        if text_lines:
            self.full_transcript_buffer.extend(text_lines)
            self.logger.info(f"Added {len(text_lines)} lines without speaker attribution")

    async def transcribe_and_save_full_recording(self, webm_path, language, meet_id, participants):
        """Transcribe full recording and save results with enhanced processing"""
        if not webm_path or not os.path.exists(webm_path):
            self.logger.error("Nothing to transcribe: audio path is empty or file doesn't exist")
            return

        self.logger.info("Starting enhanced full recording transcription")

        try:
            # Validate audio file
            audio = AudioSegment.from_file(webm_path)
            duration_sec = len(audio) / 1000
            self.logger.info(f"Full audio length: {duration_sec:.2f} seconds")

            if duration_sec < 1:
                self.logger.error("Audio file too short for transcription")
                return

            # Split into manageable chunks for processing
            num_chunks = math.ceil(duration_sec / self.MAX_CHUNK_DURATION_SEC)
            self.logger.info(f"Splitting into {num_chunks} chunks (≤ {self.MAX_CHUNK_DURATION_SEC} sec each)")

            all_text = []

            for i in range(num_chunks):
                start_ms = max(i * self.MAX_CHUNK_DURATION_SEC * 1000 - 1000, 0)  # 1s overlap
                end_ms = min((i + 1) * self.MAX_CHUNK_DURATION_SEC * 1000 + 1000, len(audio))
                chunk = audio[start_ms:end_ms]

                with tempfile.NamedTemporaryFile(suffix=self.CHUNK_EXTENSION, delete=False) as tmp_file:
                    chunk.export(tmp_file.name, format="webm")
                    chunk_path = tmp_file.name

                try:
                    self.logger.info(f"Transcribing full audio chunk {i+1}/{num_chunks}")
                    result = await self.transcriber.transcribe(chunk_path, language=language)
                    if result and result.strip():
                        all_text.append(result.strip())
                    else:
                        self.logger.warning(f"Empty result for chunk {i+1}")
                except Exception as e:
                    self.logger.error(f"Error transcribing chunk {i+1}: {e}")

                # Clean up temporary file
                try:
                    os.remove(chunk_path)
                except:
                    pass

            full_transcript_raw = "\n".join(all_text)

            # Save the raw full transcript
            raw_file_path = os.path.join(self.paths["full"], "full_transcript_from_full_audio.txt")
            with open(raw_file_path, "w", encoding="utf-8") as f:
                f.write(full_transcript_raw)

            self.logger.info(f"Raw full transcript saved to: {raw_file_path}")

            # Process with LLM for speaker matching if we have chunk transcript
            chunk_transcript = "\n".join(self.full_transcript_buffer)
            
            if chunk_transcript.strip():
                self.logger.info("Processing transcript with speaker matching...")
                full_transcript = await self.transcriber.match_transcript_speakers(chunk_transcript, full_transcript_raw)
                full_transcript_text = "\n".join([f"{segment.speaker}: {segment.text}" for segment in full_transcript])
            else:
                self.logger.warning("No chunk transcript available, using raw transcript")
                full_transcript_text = full_transcript_raw
            
            self.logger.info(f"Final transcript with speakers: {len(full_transcript_text)} characters")

            # Generate meeting analysis
            self.logger.info("Generating meeting analysis...")
            
            overview = await self.meeting_analizer.generate_overview(full_transcript_text)
            overview = overview.overview
            
            summary_and_tags = await self.meeting_analizer.summarize(full_transcript_text)
            summary = summary_and_tags.summary
            tags = summary_and_tags.tags
            
            notes = await self.meeting_analizer.generate_notes(full_transcript_text)
            notes = notes.notes
            
            action_items = await self.meeting_analizer.generate_action_items(full_transcript_text)
            action_items = action_items.action_items
            
            self.logger.info(f"Generated analysis - Summary: {len(summary)} chars, Notes: {len(notes)} items, Actions: {len(action_items)} items")
            
            # Update database
            await self.db.update_meet(meet_id, MeetUpdate(
                transcript=full_transcript_text, 
                overview="\n".join(overview),
                summary=summary,
                duration=math.ceil(duration_sec),
                tags=",".join(tags),
                action_items=action_items,
                participants=participants,
                notes=notes))
            
            # Save final transcript with speakers
            final_transcript_path = os.path.join(self.paths["full"], "full_final_transcript.txt")
            with open(final_transcript_path, "w", encoding="utf-8") as f:
                f.write(full_transcript_text)
            
            self.logger.info(f"Final transcript saved to: {final_transcript_path}")
            
            # Reset buffer
            self.reset_transcript_buffer()
            self.logger.info("Enhanced full recording transcription completed successfully")

        except Exception as e:
            self.logger.error(f"Failed to process full recording: {e}")
            import traceback
            self.logger.error(f"Traceback: {traceback.format_exc()}")

    def save_full_transcript(self):
        """Save current transcript buffer with validation"""
        if not self.full_transcript_buffer:
            self.logger.error("Nothing to save: transcript buffer is empty")
            return

        file_path = os.path.join(self.paths["full"], "full_transcript.txt")
        transcript_content = "\n".join(self.full_transcript_buffer)
        
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(transcript_content)

        self.logger.info(f"Full transcript saved to: {file_path} ({len(self.full_transcript_buffer)} lines, {len(transcript_content)} chars)")

    def save_full(self):
        """Save transcript and merge audio with enhanced validation"""
        self.save_full_transcript()
        output_file = self._merge_audio()
        return output_file

    def _merge_audio(self):
        """Merge all audio chunks into single file with improved error handling"""
        webm_files = sorted(glob(os.path.join(self.paths["audio"], "chunk_*.webm")))
        
        if not webm_files:
            self.logger.error("No webm files found for merging")
            return None
            
        # Filter valid files
        valid_files = []
        total_size = 0
        
        for f in webm_files:
            size = os.path.getsize(f)
            if size > 1024:  # At least 1KB
                valid_files.append(f)
                total_size += size
            else:
                self.logger.warning(f"Skipping small file: {f} ({size} bytes)")
        
        self.logger.info(f"Found {len(webm_files)} webm files, {len(valid_files)} valid (total: {total_size} bytes)")
        
        if not valid_files:
            self.logger.error("No valid audio chunks for merging")
            return None

        concat_file = os.path.join(self.paths["full"], "concat_list.txt")
        output_file = os.path.join(self.paths["full"], "full_audio.webm")

        # Create concatenation list
        with open(concat_file, "w", encoding="utf-8") as f:
            for path in valid_files:
                f.write(f"file '{os.path.abspath(path)}'\n")

        # Merge using FFmpeg
        try:
            cmd = [
                "ffmpeg", "-f", "concat", "-safe", "0", "-i", concat_file, 
                "-c", "copy", "-y", output_file
            ]
            
            self.logger.info(f"Running FFmpeg merge: {' '.join(cmd)}")
            
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            
            if os.path.exists(output_file):
                final_size = os.path.getsize(output_file)
                self.logger.info(f"Audio merge successful: {output_file} ({final_size} bytes)")
                return output_file
            else:
                self.logger.error("Merged file not created")
                return None
                
        except subprocess.CalledProcessError as e:
            self.logger.error(f"FFmpeg merge error: {e}")
            self.logger.error(f"FFmpeg stderr: {e.stderr}")
            return None
        except Exception as e:
            self.logger.error(f"Unexpected error during audio merge: {e}")
            return None