import aiohttp
import os
from src.backend.utils.logger import CustomLog 
log = CustomLog()
class JsPluginApi:
    def __init__(self, email: str, password: str, backend_url: str):
        self.email = email
        self.password = password
        self.backend_url = backend_url

    async def login(self):
        async with aiohttp.ClientSession() as session:
            log.info("🔐 Sending request to /start-login...")
            response = await session.post(
                f"{self.backend_url}/start-login",
                json={"email": self.email, "password": self.password}
            )
            text = await response.text()
            log.info(f"📨 Server response: {response.status} — {text}")
            await self.submit_2fa()

    async def submit_2fa(self):
        code = input("Enter the 2FA code and press Enter: ")
        async with aiohttp.ClientSession() as session:
            log.info("🔐 Sending code to /submit-2fa...")
            response = await session.post(
                f"{self.backend_url}/submit-2fa",
                json={"code": code}
            )
            text = await response.text()
            log.info(f"📨 Server response: {response.status} — {text}")

    async def connect(self, meet_code: str, duration_sec: int, port: int):
        async with aiohttp.ClientSession() as session:
            log.info("🚀 Sending /start command to JS service...")
            response = await session.post(
                f"{self.backend_url}/start",
                json={
                    "email": self.email,
                    "password": self.password,
                    "meetCode": meet_code,
                    "duration": duration_sec,
                    "port": port
                }
            )
            text = await response.text()
            log.info(f"▶️ Start command sent, response: {response.status} — {text}")
