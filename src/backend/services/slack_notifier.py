"""Send transcript summary to Slack (date, time, room, participants, transcript + audio links)."""
from typing import List, Optional

import requests

from backend.utils.configs import Config
from backend.utils.logger import CustomLog

SLACK_API = "https://slack.com/api"


class SlackNotifier:
    """Sends meeting summary to Slack via Incoming Webhook and/or Bot API DM."""

    def __init__(self):
        self._config = Config.load_config()
        self._logger = CustomLog()

    def is_configured(self) -> bool:
        return bool(self._config.slack.WEBHOOK_URL) or bool(self._config.slack.BOT_TOKEN)

    def _build_text(
        self,
        date: str,
        time_str: str,
        meet_code: str,
        participants: List[str],
        transcript_url: Optional[str],
        audio_url: Optional[str],
    ) -> str:
        transcript_link = f"<{transcript_url}|Transcript>" if transcript_url else "-"
        audio_link = f"<{audio_url}|Audio>" if audio_url else "-"
        only_self = len(participants) <= 1
        if only_self:
            return f"*Transcript:* {transcript_link} / {audio_link}"
        participants_str = ", ".join(participants)
        return (
            f"*Date:* {date}\n"
            f"*Time:* {time_str}\n"
            f"*Room:* {meet_code}\n"
            f"*Participants:* {participants_str}\n"
            f"*Transcript:* {transcript_link} / {audio_link}"
        )

    def _send_dm(self, email: str, text: str) -> bool:
        """Send a DM to a Slack user found by email using the Bot Token."""
        token = self._config.slack.BOT_TOKEN
        if not token:
            self._logger.warning("SLACK_BOT_TOKEN not configured, cannot send DM")
            return False

        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

        # Step 1: resolve email → user ID
        try:
            r = requests.get(
                f"{SLACK_API}/users.lookupByEmail",
                params={"email": email},
                headers=headers,
                timeout=10,
            )
            data = r.json()
            if not data.get("ok"):
                err = data.get("error", "unknown")
                if err == "missing_scope":
                    self._logger.error(
                        f"Slack Bot Token missing scope 'users:read.email'. "
                        f"Go to api.slack.com/apps → your app → OAuth & Permissions → "
                        f"add 'users:read.email' scope and reinstall the app."
                    )
                else:
                    self._logger.error(f"users.lookupByEmail failed: {err} (email={email})")
                return False
            user_id = data["user"]["id"]
            self._logger.info(f"Resolved Slack user: {email} → {user_id}")
        except Exception as e:
            self._logger.error(f"Slack users.lookupByEmail error: {e}", exc_info=True)
            return False

        # Step 2: open DM channel
        try:
            r = requests.post(
                f"{SLACK_API}/conversations.open",
                json={"users": user_id},
                headers=headers,
                timeout=10,
            )
            data = r.json()
            if not data.get("ok"):
                self._logger.error(f"conversations.open failed: {data.get('error')}")
                return False
            channel_id = data["channel"]["id"]
        except Exception as e:
            self._logger.error(f"Slack conversations.open error: {e}", exc_info=True)
            return False

        # Step 3: post message
        try:
            r = requests.post(
                f"{SLACK_API}/chat.postMessage",
                json={"channel": channel_id, "text": text},
                headers=headers,
                timeout=10,
            )
            data = r.json()
            if not data.get("ok"):
                self._logger.error(f"chat.postMessage failed: {data.get('error')}")
                return False
            self._logger.info(f"Slack DM sent to {email}")
            return True
        except Exception as e:
            self._logger.error(f"Slack chat.postMessage error: {e}", exc_info=True)
            return False

    def notify_transcript_ready(
        self,
        date: str,
        time_str: str,
        meet_code: str,
        participants: List[str],
        transcript_url: Optional[str],
        audio_url: Optional[str] = None,
        slack_dm_email: Optional[str] = None,
    ) -> bool:
        """Send DM if email given, otherwise send to channel via webhook."""
        text = self._build_text(date, time_str, meet_code, participants, transcript_url, audio_url)

        # Email provided → DM only, skip webhook
        if slack_dm_email:
            return self._send_dm(slack_dm_email, text)

        # No email → send to channel via webhook
        if self._config.slack.WEBHOOK_URL:
            try:
                r = requests.post(
                    self._config.slack.WEBHOOK_URL,
                    json={"text": text},
                    timeout=10,
                )
                r.raise_for_status()
                self._logger.info("Slack webhook notification sent")
                return True
            except Exception as e:
                self._logger.error(f"Slack webhook notification failed: {e}", exc_info=True)
                return False

        self._logger.info("Slack not configured, skip notification")
        return False
