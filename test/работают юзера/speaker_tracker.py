import os
import json
from src.backend.utils.logger import CustomLog

class SpeakerTracker():
    def __init__(self):
        super().__init__()
        self.events = []
        self.buffer = []
        self.paths = None
        self.logger = CustomLog()
        self.unique_speakers = set()
        self.current_speaker_states = {}  # Track current states {name: bool}
        self.last_event_time = None

    def set_paths(self, paths):
        self.paths = paths

    def add_event(self, data):
        """
        Add speaker event with improved handling for boolean states
        Expected data format: {
            "time": timestamp,
            "speakers": {"User1": true, "User2": false, "User3": false}
        }
        """
        try:
            timestamp = data.get("time")
            speakers_dict = data.get("speakers", {})
            
            if not timestamp or not isinstance(speakers_dict, dict):
                self.logger.warning(f"Invalid speaker event data: {data}")
                return
            
            # Store raw event for timeline
            event = {
                "time_raw": timestamp, 
                "speakers": speakers_dict
            }
            self.events.append(event)
            self.buffer.append(event)
            
            # Track unique speakers with better name handling
            for speaker_name in speakers_dict.keys():
                if speaker_name and speaker_name.strip():  # Only valid names
                    clean_name = speaker_name.strip()
                    self.unique_speakers.add(clean_name)
                    self.logger.info(f"Added speaker to unique set: '{clean_name}'")
            
            # Update current states and log changes
            self._update_current_states(speakers_dict, timestamp)
            
            # Log event details
            active_speakers = [name for name, active in speakers_dict.items() if active]
            self.logger.info(f"Added speaker event at {timestamp}: {len(active_speakers)} active speakers - {active_speakers}")
            
        except Exception as e:
            self.logger.error(f"Error adding speaker event: {e}")
            import traceback
            self.logger.error(f"Traceback: {traceback.format_exc()}")

    def _update_current_states(self, new_speakers_dict, timestamp):
        """Update current speaker states and log changes with enhanced tracking"""
        try:
            # Track what changed
            changes = []
            
            for speaker_name, is_speaking in new_speakers_dict.items():
                if not speaker_name or not speaker_name.strip():
                    continue
                    
                speaker_name = speaker_name.strip()
                previous_state = self.current_speaker_states.get(speaker_name, False)
                
                if previous_state != is_speaking:
                    if is_speaking:
                        changes.append(f"'{speaker_name}' started speaking")
                    else:
                        changes.append(f"'{speaker_name}' stopped speaking")
                
                self.current_speaker_states[speaker_name] = is_speaking
            
            # Log changes if any
            if changes:
                self.logger.info(f"Speaker changes at {timestamp}: {', '.join(changes)}")
            
            # Log current active speakers with more detail
            active_speakers = [name for name, active in self.current_speaker_states.items() if active]
            if active_speakers:
                self.logger.info(f"Currently speaking: {', '.join(active_speakers)}")
            else:
                self.logger.info("No speakers currently active")
            
            self.last_event_time = timestamp
            
        except Exception as e:
            self.logger.error(f"Error updating current states: {e}")

    def get_unique_speakers(self):
        """Return list of all unique speakers encountered with validation"""
        speakers_list = list(self.unique_speakers)
        
        # Filter out any invalid speaker names
        valid_speakers = []
        for speaker in speakers_list:
            if speaker and speaker.strip() and len(speaker.strip()) > 0:
                valid_speakers.append(speaker.strip())
        
        self.logger.info(f"Total unique speakers: {len(valid_speakers)} - {valid_speakers}")
        return valid_speakers

    def get_current_active_speakers(self):
        """Return list of currently active speakers"""
        active = [name for name, active in self.current_speaker_states.items() if active]
        self.logger.info(f"Current active speakers: {active}")
        return active

    def get_speaker_stats(self):
        """Return statistics about speaker activity with enhanced metrics"""
        if not self.events:
            return {}
        
        stats = {}
        total_events = 0
        
        # Count how often each speaker was active
        for event in self.events:
            speakers_dict = event.get("speakers", {})
            total_events += 1
            
            for speaker_name, is_active in speakers_dict.items():
                if not speaker_name or not speaker_name.strip():
                    continue
                    
                clean_name = speaker_name.strip()
                if clean_name not in stats:
                    stats[clean_name] = {
                        "active_count": 0, 
                        "total_count": 0,
                        "first_seen": event.get("time_raw"),
                        "last_seen": event.get("time_raw")
                    }
                
                stats[clean_name]["total_count"] += 1
                stats[clean_name]["last_seen"] = event.get("time_raw")
                
                if is_active:
                    stats[clean_name]["active_count"] += 1
        
        # Calculate percentages and durations
        for speaker_name in stats:
            total = stats[speaker_name]["total_count"]
            active = stats[speaker_name]["active_count"]
            stats[speaker_name]["active_percentage"] = (active / total * 100) if total > 0 else 0
            
            # Calculate presence duration
            first_seen = stats[speaker_name]["first_seen"]
            last_seen = stats[speaker_name]["last_seen"]
            if first_seen and last_seen:
                stats[speaker_name]["presence_duration_ms"] = last_seen - first_seen
            else:
                stats[speaker_name]["presence_duration_ms"] = 0
        
        self.logger.info(f"Generated stats for {len(stats)} speakers")
        return stats

    def save_buffer(self, timestamp):
        """Save current buffer to file with enhanced metadata"""
        if not self.buffer:
            self.logger.info("No speaker events in buffer to save")
            return

        try:
            file_path = os.path.join(self.paths["transcripts"], f"chunk_{timestamp}_speakers.json")
            
            # Extract unique speakers from this chunk
            chunk_speakers = set()
            for event in self.buffer:
                speakers_dict = event.get("speakers", {})
                for speaker_name in speakers_dict.keys():
                    if speaker_name and speaker_name.strip():
                        chunk_speakers.add(speaker_name.strip())
            
            # Save with additional metadata
            data_to_save = {
                "timestamp": timestamp,
                "events_count": len(self.buffer),
                "unique_speakers_in_chunk": list(chunk_speakers),
                "chunk_duration_ms": self._calculate_chunk_duration(),
                "active_speakers_summary": self._get_chunk_summary(),
                "events": self.buffer
            }
            
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data_to_save, f, ensure_ascii=False, indent=2)
                
            self.logger.info(f"Speaker buffer saved: {file_path} ({len(self.buffer)} events, {len(chunk_speakers)} unique speakers)")
            
            # Clear buffer after saving
            self.buffer.clear()
            
        except Exception as e:
            self.logger.error(f"Error saving speaker buffer: {e}")

    def _calculate_chunk_duration(self):
        """Calculate duration of current chunk"""
        if len(self.buffer) < 2:
            return 0
        
        try:
            first_time = self.buffer[0].get("time_raw", 0)
            last_time = self.buffer[-1].get("time_raw", 0)
            return last_time - first_time
        except Exception:
            return 0

    def _get_chunk_summary(self):
        """Get summary of speaker activity in current chunk"""
        summary = {}
        
        for event in self.buffer:
            speakers_dict = event.get("speakers", {})
            for speaker_name, is_active in speakers_dict.items():
                if not speaker_name or not speaker_name.strip():
                    continue
                
                clean_name = speaker_name.strip()
                if clean_name not in summary:
                    summary[clean_name] = {"active_events": 0, "total_events": 0}
                
                summary[clean_name]["total_events"] += 1
                if is_active:
                    summary[clean_name]["active_events"] += 1
        
        return summary

    def save_timeline(self):
        """Save complete timeline and statistics with enhanced data"""
        if not self.events:
            self.logger.info("No speaker events to save in timeline")
            return

        try:
            # Save main timeline
            timeline_path = os.path.join(self.paths["full"], "speaker_timeline.json")
            timeline_data = {
                "metadata": {
                    "total_events": len(self.events),
                    "session_duration_ms": self._calculate_session_duration(),
                    "unique_speakers_count": len(self.unique_speakers),
                    "first_event_time": self.events[0].get("time_raw") if self.events else None,
                    "last_event_time": self.events[-1].get("time_raw") if self.events else None,
                    "generated_at": self.last_event_time
                },
                "unique_speakers": self.get_unique_speakers(),
                "events": self.events
            }
            
            with open(timeline_path, "w", encoding="utf-8") as f:
                json.dump(timeline_data, f, ensure_ascii=False, indent=2)
            self.logger.info(f"Speaker timeline saved: {timeline_path}")
            
            # Save unique speakers list
            speakers_file_path = os.path.join(self.paths["full"], "unique_speakers.json")
            speakers_data = {
                "count": len(self.unique_speakers),
                "speakers": self.get_unique_speakers(),
                "generated_at": self.last_event_time
            }
            
            with open(speakers_file_path, "w", encoding="utf-8") as f:
                json.dump(speakers_data, f, ensure_ascii=False, indent=2)
            self.logger.info(f"Unique speakers saved: {speakers_file_path}")
            
            # Save enhanced speaker statistics
            stats_path = os.path.join(self.paths["full"], "speaker_statistics.json")
            stats_data = {
                "speaker_stats": self.get_speaker_stats(),
                "session_summary": {
                    "total_events": len(self.events),
                    "unique_speakers_count": len(self.unique_speakers),
                    "session_duration_ms": self._calculate_session_duration(),
                    "final_states": self.current_speaker_states,
                    "session_start": self.events[0].get("time_raw") if self.events else None,
                    "session_end": self.events[-1].get("time_raw") if self.events else None
                },
                "speaking_patterns": self._analyze_speaking_patterns()
            }
            
            with open(stats_path, "w", encoding="utf-8") as f:
                json.dump(stats_data, f, ensure_ascii=False, indent=2)
            self.logger.info(f"Speaker statistics saved: {stats_path}")
            
        except Exception as e:
            self.logger.error(f"Error saving speaker timeline: {e}")

    def _analyze_speaking_patterns(self):
        """Analyze speaking patterns for insights"""
        if not self.events:
            return {}
        
        patterns = {
            "overlapping_speech_events": 0,
            "silence_periods": 0,
            "speaker_transitions": []
        }
        
        prev_active_speakers = set()
        
        for event in self.events:
            speakers_dict = event.get("speakers", {})
            current_active = set(name for name, active in speakers_dict.items() if active and name)
            
            # Count overlapping speech
            if len(current_active) > 1:
                patterns["overlapping_speech_events"] += 1
            
            # Count silence
            if len(current_active) == 0:
                patterns["silence_periods"] += 1
            
            # Track transitions
            if prev_active_speakers != current_active and prev_active_speakers:
                patterns["speaker_transitions"].append({
                    "time": event.get("time_raw"),
                    "from": list(prev_active_speakers),
                    "to": list(current_active)
                })
            
            prev_active_speakers = current_active
        
        return patterns

    def _calculate_session_duration(self):
        """Calculate session duration from first to last event"""
        if len(self.events) < 2:
            return 0
        
        try:
            first_time = self.events[0].get("time_raw", 0)
            last_time = self.events[-1].get("time_raw", 0)
            return last_time - first_time
        except Exception:
            return 0

    def reset_speakers(self):
        """Reset all speaker tracking data"""
        self.unique_speakers.clear()
        self.current_speaker_states.clear()
        self.events.clear()
        self.buffer.clear()
        self.last_event_time = None
        self.logger.info("Speaker tracker reset - all data cleared")

    def get_session_info(self):
        """Get current session information with enhanced details"""
        return {
            "unique_speakers": list(self.unique_speakers),
            "unique_speakers_count": len(self.unique_speakers),
            "current_active": self.get_current_active_speakers(),
            "total_events": len(self.events),
            "last_event_time": self.last_event_time,
            "session_duration_ms": self._calculate_session_duration(),
            "current_speaker_states": dict(self.current_speaker_states),
            "buffer_size": len(self.buffer)
        }

    def get_speaker_ranges_for_transcript(self):
        """
        Generate speaker ranges optimized for transcript processing
        Returns list of {speaker, start_ms, end_ms} dictionaries
        """
        speaker_ranges = []
        if not self.events:
            self.logger.warning("No speaker events available for range generation")
            return speaker_ranges

        self.logger.info(f"Generating speaker ranges from {len(self.events)} events")

        # Track when each speaker starts/stops speaking
        speaker_sessions = {}  # {speaker_name: {"start": time, "active": bool}}

        for i, event in enumerate(self.events):
            timestamp = event.get("time_raw")
            speakers_dict = event.get("speakers", {})

            if timestamp is None or not isinstance(speakers_dict, dict):
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
                    self.logger.info(f"Speaker '{speaker_name}' started at {timestamp}")

                # Speaker stopped speaking
                elif not is_speaking and prev_active:
                    start_time = speaker_sessions[speaker_name]["start"]
                    if start_time is not None:
                        speaker_ranges.append({
                            "speaker": speaker_name,
                            "start_ms": start_time,
                            "end_ms": timestamp
                        })
                        self.logger.info(f"Speaker '{speaker_name}' range: {start_time} - {timestamp}")
                    
                    speaker_sessions[speaker_name]["active"] = False
                    speaker_sessions[speaker_name]["start"] = None

        # Handle speakers still speaking at the end
        last_timestamp = self.events[-1].get("time_raw") if self.events else None
        
        if last_timestamp:
            for speaker_name, session in speaker_sessions.items():
                if session["active"] and session["start"] is not None:
                    speaker_ranges.append({
                        "speaker": speaker_name,
                        "start_ms": session["start"],
                        "end_ms": last_timestamp
                    })
                    self.logger.info(f"Speaker '{speaker_name}' final range: {session['start']} - {last_timestamp}")

        self.logger.info(f"Generated {len(speaker_ranges)} speaker ranges")
        return speaker_ranges