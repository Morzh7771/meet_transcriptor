import aiohttp
import os
from src.backend.utils.logger import CustomLog 
log = CustomLog()
class JsPluginApi:
    def __init__(self, email: str, password: str, backend_url: str):
        self.email = email
        self.password = password
        self.backend_url = backend_url
        self.meet_sessions = {} 

    async def login(self):
        async with aiohttp.ClientSession() as session:
            log.info(" Sending request to /start-login...")
            response = await session.post(
                f"{self.backend_url}/start-login",
                json={"email": self.email, "password": self.password}
            )
            text = await response.text()
            log.info(f" Server response: {response.status} — {text}")
            await self.submit_2fa()

    async def submit_2fa(self):
        code = input("Enter the 2FA code and press Enter: ")
        async with aiohttp.ClientSession() as session:
            log.info(" Sending code to /submit-2fa...")
            response = await session.post(
                f"{self.backend_url}/submit-2fa",
                json={"code": code}
            )
            text = await response.text()
            log.info(f" Server response: {response.status} — {text}")

    async def connect(self, meet_code: str, port: int):
        async with aiohttp.ClientSession() as session:
            log.info(" Sending /start command to JS service...")
            response = await session.post(
                f"{self.backend_url}/start",
                json={
                    "email": self.email,
                    "password": self.password,
                    "meetCode": meet_code,
                    "port": port
                }
            )
            text = await response.text()
            log.info(f"Start command sent, response: {response.status} — {text}")
            try:
                data = await response.json()
                session_id = data.get("sessionId")
                if session_id:
                    self.meet_sessions[meet_code] = session_id
                    log.info(f"🆔 Session ID {session_id} stored for meet {meet_code}")
            except Exception as e:
                log.error(f"⚠️ Failed to parse JSON or store session: {e}")

    async def terminate_by_meet_code(self, meet_code: str):
        session_id = self.meet_sessions.get(meet_code)
        if not session_id:
            log.error(f"⚠️ No session ID found for meet code: {meet_code}")
            return

        async with aiohttp.ClientSession() as session:
            log.info(f" Sending /terminate for session ID {session_id}...")
            response = await session.post(
                f"{self.backend_url}/terminate",
                json={"sessionId": session_id}
            )
            text = await response.text()
            log.info(f"Terminate response: {response.status} — {text}")
            if response.status == 200:
                self.meet_sessions.pop(meet_code, None)