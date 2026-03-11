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

    @staticmethod
    def _clean_participants(participants: List[str]) -> List[str]:
        """Strip parenthetical suffixes (e.g. screen-share labels) and deduplicate."""
        import re
        seen = []
        for name in participants:
            base = re.sub(r"\s*\(.*?\)\s*$", "", name).strip()
            if base and base not in seen:
                seen.append(base)
        return seen

    def _build_text(
        self,
        date: str,
        time_str: str,
        meet_code: str,
        participants: List[str],
        transcript_url: Optional[str],
        audio_url: Optional[str],
        end_time_str: str = "",
        duration_str: str = "",
    ) -> str:
        cleaned = self._clean_participants(participants)
        participants_str = ", ".join(cleaned) if cleaned else "-"
        transcript_link = f"<{transcript_url}|Transcript>" if transcript_url else "-"
        audio_link = f"<{audio_url}|Audio>" if audio_url else "-"
        lines = [
            f"*Date:* {date}",
            f"*Start:* {time_str}",
        ]
        if end_time_str:
            lines.append(f"*End:* {end_time_str}")
        if duration_str:
            lines.append(f"*Duration:* {duration_str}")
        lines += [
            f"*Room:* {meet_code}",
            f"*Participants:* {participants_str}",
            f"*Transcript:* {transcript_link} / {audio_link}",
        ]
        return "\n".join(lines)

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
        end_time_str: str = "",
        duration_str: str = "",
        slack_dm_email: Optional[str] = None,
    ) -> bool:
        """Send DM if email given, otherwise send to channel via webhook."""
        text = self._build_text(
            date, time_str, meet_code, participants, transcript_url, audio_url,
            end_time_str=end_time_str, duration_str=duration_str,
        )

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
