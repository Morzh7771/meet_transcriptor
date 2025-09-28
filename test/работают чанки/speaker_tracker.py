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
            
            # Track unique speakers
            for speaker_name in speakers_dict.keys():
                if speaker_name and speaker_name.strip():  # Only valid names
                    self.unique_speakers.add(speaker_name.strip())
            
            # Update current states and log changes
            self._update_current_states(speakers_dict, timestamp)
            
            self.logger.info(f"Added speaker event at {timestamp}: {len([s for s, active in speakers_dict.items() if active])} active speakers")
            
        except Exception as e:
            self.logger.error(f"Error adding speaker event: {e}")

    def _update_current_states(self, new_speakers_dict, timestamp):
        """Update current speaker states and log changes"""
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
                        changes.append(f"{speaker_name} started speaking")
                    else:
                        changes.append(f"{speaker_name} stopped speaking")
                
                self.current_speaker_states[speaker_name] = is_speaking
            
            # Log changes if any
            if changes:
                self.logger.info(f"Speaker changes at {timestamp}: {', '.join(changes)}")
            
            # Log current active speakers
            active_speakers = [name for name, active in self.current_speaker_states.items() if active]
            if active_speakers:
                self.logger.info(f"Currently speaking: {', '.join(active_speakers)}")
            
            self.last_event_time = timestamp
            
        except Exception as e:
            self.logger.error(f"Error updating current states: {e}")

    def get_unique_speakers(self):
        """Return list of all unique speakers encountered"""
        speakers_list = list(self.unique_speakers)
        self.logger.info(f"Total unique speakers: {len(speakers_list)} - {speakers_list}")
        return speakers_list

    def get_current_active_speakers(self):
        """Return list of currently active speakers"""
        return [name for name, active in self.current_speaker_states.items() if active]

    def get_speaker_stats(self):
        """Return statistics about speaker activity"""
        if not self.events:
            return {}
        
        stats = {}
        
        # Count how often each speaker was active
        for event in self.events:
            speakers_dict = event.get("speakers", {})
            for speaker_name, is_active in speakers_dict.items():
                if not speaker_name:
                    continue
                    
                if speaker_name not in stats:
                    stats[speaker_name] = {"active_count": 0, "total_count": 0}
                
                stats[speaker_name]["total_count"] += 1
                if is_active:
                    stats[speaker_name]["active_count"] += 1
        
        # Calculate percentages
        for speaker_name in stats:
            total = stats[speaker_name]["total_count"]
            active = stats[speaker_name]["active_count"]
            stats[speaker_name]["active_percentage"] = (active / total * 100) if total > 0 else 0
        
        return stats

    def save_buffer(self, timestamp):
        """Save current buffer to file"""
        if not self.buffer:
            self.logger.info("No speaker events in buffer to save")
            return

        try:
            file_path = os.path.join(self.paths["transcripts"], f"chunk_{timestamp}_speakers.json")
            
            # Save with additional metadata
            data_to_save = {
                "timestamp": timestamp,
                "events_count": len(self.buffer),
                "unique_speakers_in_chunk": list(set([
                    speaker for event in self.buffer 
                    for speaker in event.get("speakers", {}).keys() 
                    if speaker and speaker.strip()
                ])),
                "events": self.buffer
            }
            
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data_to_save, f, ensure_ascii=False, indent=2)
                
            self.logger.info(f"Speaker buffer saved: {file_path} ({len(self.buffer)} events)")
            self.buffer.clear()
            
        except Exception as e:
            self.logger.error(f"Error saving speaker buffer: {e}")

    def save_timeline(self):
        """Save complete timeline and statistics"""
        if not self.events:
            self.logger.info("No speaker events to save in timeline")
            return

        try:
            # Save main timeline
            timeline_path = os.path.join(self.paths["full"], "speaker_timeline.json")
            timeline_data = {
                "total_events": len(self.events),
                "session_duration_ms": self._calculate_session_duration(),
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
                "speakers": self.get_unique_speakers()
            }
            
            with open(speakers_file_path, "w", encoding="utf-8") as f:
                json.dump(speakers_data, f, ensure_ascii=False, indent=2)
            self.logger.info(f"Unique speakers saved: {speakers_file_path}")
            
            # Save speaker statistics
            stats_path = os.path.join(self.paths["full"], "speaker_statistics.json")
            stats_data = {
                "speaker_stats": self.get_speaker_stats(),
                "session_summary": {
                    "total_events": len(self.events),
                    "unique_speakers_count": len(self.unique_speakers),
                    "session_duration_ms": self._calculate_session_duration(),
                    "final_states": self.current_speaker_states
                }
            }
            
            with open(stats_path, "w", encoding="utf-8") as f:
                json.dump(stats_data, f, ensure_ascii=False, indent=2)
            self.logger.info(f"Speaker statistics saved: {stats_path}")
            
        except Exception as e:
            self.logger.error(f"Error saving speaker timeline: {e}")

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
        """Get current session information"""
        return {
            "unique_speakers": list(self.unique_speakers),
            "current_active": self.get_current_active_speakers(),
            "total_events": len(self.events),
            "last_event_time": self.last_event_time,
            "session_duration_ms": self._calculate_session_duration()
        }