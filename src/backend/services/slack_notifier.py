"""Send transcript summary to Slack (date, time, room, participants, transcript + audio links)."""
from typing import List, Optional

import requests

from src.backend.utils.configs import Config
from src.backend.utils.logger import CustomLog


class SlackNotifier:
    """Sends meeting summary to Slack via Incoming Webhook."""

    def __init__(self):
        self._config = Config.load_config()
        self._logger = CustomLog()

    def is_configured(self) -> bool:
        return bool(self._config.slack.WEBHOOK_URL)

    def notify_transcript_ready(
        self,
        date: str,
        time_str: str,
        meet_code: str,
        participants: List[str],
        transcript_url: Optional[str],
        audio_url: Optional[str] = None,
    ) -> bool:
        """Send message: date, time, room, participants, transcript link, audio link."""
        if not self.is_configured():
            self._logger.info("Slack not configured, skip notification")
            return False
        participants_str = ", ".join(participants) if participants else "-"
        transcript_link = f"<{transcript_url}|Transcript>" if transcript_url else "-"
        audio_link = f"<{audio_url}|Audio>" if audio_url else "-"
        text = (
            f"*Date:* {date}\n"
            f"*Time:* {time_str}\n"
            f"*Room:* {meet_code}\n"
            f"*Participants:* {participants_str}\n"
            f"*Transcript:* {transcript_link} / {audio_link}"
        )
        payload = {"text": text}
        try:
            r = requests.post(
                self._config.slack.WEBHOOK_URL,
                json=payload,
                timeout=10,
            )
            r.raise_for_status()
            self._logger.info("Slack notification sent")
            return True
        except Exception as e:
            self._logger.error(f"Slack notification failed: {e}", exc_info=True)
            return False
