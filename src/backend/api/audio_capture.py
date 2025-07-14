import os
import time
import threading
import queue
import numpy as np
import soundcard as sc
from datetime import datetime
import wave
from src.backend.utils.logger import CustomLog
import pythoncom
log = CustomLog()

class SystemAudioRecorder:
    def __init__(self):
        self.CHUNK = 1024
        self.CHANNELS = 1
        self.RATE = 16000

        self.audio_queue = queue.Queue(maxsize=100)
        self.text_queue = queue.Queue()
        self.audio_buffer = []
        self.buffer_lock = threading.Lock()
        self.audio_recording = False
        self.microphone = None
        self.default_speaker = None
        self.wav_filename = None
        self.start_time = None

    def get_audio_devices(self):
        try:
            mics = sc.all_microphones(include_loopback=True)
            log.info(f"Found {len(mics)} audio devices:")
            for mic in mics:
                log.info(f" - {mic.name}")

            default_speaker = sc.default_speaker().name.lower()
            default_loopback = next((mic for mic in mics if default_speaker in mic.name.lower()), None)
            if default_loopback:
                log.info(f"Selected device: {default_loopback.name}")
                return default_loopback, None

            log.warning("No match found, using default microphone.")
            return sc.default_microphone(), None
        except Exception as e:
            log.error(f"Device selection error: {e}")
            return None, None


    def system_audio_capture_thread(self):
        """Thread to capture system audio"""
        try:
            import platform
            if platform.system() == "Windows":
                import ctypes
                ctypes.windll.ole32.CoInitializeEx(0, 2)  # COINIT_APARTMENTTHREADED
        except Exception as e:
            log.warning(f"CoInitialize failed or not needed: {e}")

        log.info("Audio capture thread started.")

        try:
            log.info(f"Recording from device: {self.microphone.name}")
            with self.microphone.recorder(samplerate=self.RATE, channels=self.CHANNELS) as recorder:
                chunk_size = int(self.RATE * 0.1)

                while self.audio_recording:
                    try:
                        data = recorder.record(numframes=chunk_size)
                        if data is None or len(data) == 0:
                            continue

                        if data.dtype != np.int16:
                            data = np.clip(data * 32767, -32768, 32767).astype(np.int16)

                        if len(data.shape) > 1 and data.shape[1] > 1:
                            data = np.mean(data, axis=1).astype(np.int16)

                        with self.buffer_lock:
                            self.audio_buffer.extend(data)

                        if not self.audio_queue.full():
                            self.audio_queue.put(data.tobytes())

                    except Exception as e:
                        log.warning(f"Audio recording error: {e}")
                        time.sleep(0.1)

        except Exception as e:
            log.error(f"Audio initialization error: {e}")

    def save_audio_to_wav(self):
        """Save all buffered audio to a WAV file"""
        log.info("Saving audio to WAV file...")

        with self.buffer_lock:
            if not self.audio_buffer:
                log.warning("No audio data to save — writing silence instead.")
                self.audio_buffer = [0] * self.RATE

            audio_array = np.array(self.audio_buffer, dtype=np.int16)
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            wav_filename = f"recording_{timestamp}.wav"

            try:
                with wave.open(wav_filename, 'wb') as wf:
                    wf.setnchannels(self.CHANNELS)
                    wf.setsampwidth(2)
                    wf.setframerate(self.RATE)
                    wf.writeframes(audio_array.tobytes())

                duration = len(audio_array) / self.RATE
                log.info(f"Audio saved to {wav_filename}")
                log.info(f"Recording duration: {duration:.2f} seconds")

                return wav_filename

            except Exception as e:
                log.error(f"Error saving WAV file: {e}")
                return None

    def run(self):
        try:
             
            pythoncom.CoInitialize()  # <<< вот эта строчка важна

            mics = sc.all_microphones(include_loopback=True)
            if not mics:
                log.error("No audio devices found!")
                return

            self.microphone, self.default_speaker = self.get_audio_devices()
            if self.microphone is None:
                log.error("Failed to select audio device!")
                return

            log.info(f"Using device: {self.microphone.name}")
            log.info(f"Sample rate: {self.RATE} Hz")
            log.info(f"Channels: {self.CHANNELS}")

            self.start_time = datetime.now()
            self.audio_recording = True

            capture_thread = threading.Thread(target=self.system_audio_capture_thread, daemon=True)
            capture_thread.start()

            log.info("Recording started in background.")

        except Exception as e:
            log.error(f"Critical error: {e}")
            import traceback
            traceback.print_exc()



def main():
    try:
        import soundcard
        import speech_recognition
        log.info("All dependencies are installed.")
    except ImportError as e:
        log.error(f"Missing dependency: {e}")
        log.info("Please install: pip install soundcard speechrecognition")
        return

    log.info("=" * 60)
    log.info("  CONTINUOUS AUDIO RECORDING SYSTEM")
    log.info("=" * 60)
    log.info("• Unlimited duration recording")
    log.info("• Automatic speech recognition")
    log.info("• Save to WAV + JSON transcript")
    log.info("• Press Ctrl+C to stop")
    log.info("=" * 60)

    recorder = SystemAudioRecorder()
    recorder.run()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log.info("Recording stopped by user.")
    except Exception as e:
        log.error(f"Fatal error: {e}")
        import traceback
        traceback.print_exc()
