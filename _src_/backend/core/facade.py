from src.backend.api.join_meet import JoinGoogleMeet
from src.backend.api.audio_capture import SystemAudioRecorder
from src.backend.llm.whisper_proc import AsyncWhisperTranscriber
from src.backend.llm.chatbot import ChatBot
from src.backend.utils.logger import CustomLog
import threading
import os
import asyncio

log = CustomLog()

class MeetAudioFacade:
    def __init__(self):
        self.meet_bot = None
        self.recorder = None
        self.audio_thread = None
        self.last_audio_file = None
        self.last_transcript = None
        self.transcriber = AsyncWhisperTranscriber()
        self.chatbot = ChatBot()

    def start(self, meet_link):
        os.environ["MEET_LINK"] = meet_link
        self.meet_bot = JoinGoogleMeet()
        self.meet_bot.join_meet()
        admitted = self.meet_bot.wait_for_admission(timeout=60)
        if admitted:
            self.start_audio_recording()
        else:
            log.error("Bot could not join the meeting — recording aborted.")

    def start_audio_recording(self):
        if self.recorder and self.recorder.audio_recording:
            log.warning("Audio is already recording.")
            return
        self.recorder = SystemAudioRecorder()
        self.recorder.audio_recording = True
        self.audio_thread = threading.Thread(target=self.recorder.run, daemon=True)
        self.audio_thread.start()
        log.info("Audio recording started.")

    def stop(self):
        if self.recorder:
            self.recorder.audio_recording = False
            self.last_audio_file = self.recorder.save_audio_to_wav()
            if self.last_audio_file:
                self.last_transcript = asyncio.run(self.transcriber.transcribe_wav_file(self.last_audio_file))
            else:
                log.warning("No audio file to transcribe.")
        if self.meet_bot and self.meet_bot.driver:
            self.meet_bot.driver.quit()
        log.info("Bot disconnected and recording stopped.")

    def ask_question(self, question: str):
        if not self.last_transcript:
            log.warning("No transcript available to use as context.")
            yield "No transcript available to use as context."
            return
        yield from self.chatbot.ask(question, self.last_transcript)
